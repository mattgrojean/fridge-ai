from __future__ import annotations

import argparse
import hashlib
import logging
from pathlib import Path, PurePosixPath
from typing import Iterable

import openai
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from azure.storage.blob import BlobServiceClient
from pypdf import PdfReader

LOGGER = logging.getLogger("ingest_manuals")
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_BATCH_SIZE = 16
UPLOAD_BATCH_SIZE = 100


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest appliance manuals from Azure Blob Storage into Azure AI Search."
    )
    parser.add_argument("--search-endpoint", required=True, help="Azure AI Search endpoint URL")
    parser.add_argument("--openai-endpoint", required=True, help="Azure OpenAI endpoint URL")
    parser.add_argument("--storage-account", required=True, help="Azure Storage account name")
    parser.add_argument("--container", default="manuals", help="Blob container with PDF manuals")
    parser.add_argument("--index-name", default="manuals-index", help="Search index name")
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=500,
        help="Approximate chunk size in tokens (converted to characters by multiplying by 4)",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=100,
        help="Approximate chunk overlap in tokens (converted to characters by multiplying by 4)",
    )
    return parser.parse_args()


def iter_pdf_blob_names(blob_service: BlobServiceClient, container_name: str) -> list[str]:
    container_client = blob_service.get_container_client(container_name)
    return [
        blob.name
        for blob in container_client.list_blobs()
        if blob.name.lower().endswith(".pdf")
    ]


def build_download_path(temp_root: Path, blob_name: str) -> Path:
    safe_stem = PurePosixPath(blob_name).stem or "manual"
    digest = hashlib.sha256(blob_name.encode("utf-8")).hexdigest()[:12]
    safe_name = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in safe_stem)
    return temp_root / f"{safe_name}_{digest}.pdf"


def download_blob(blob_service: BlobServiceClient, container_name: str, blob_name: str, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    blob_client = blob_service.get_blob_client(container=container_name, blob=blob_name)
    with target_path.open("wb") as file_handle:
        download_stream = blob_client.download_blob()
        file_handle.write(download_stream.readall())


def extract_page_texts(pdf_path: Path) -> list[tuple[int, str]]:
    reader = PdfReader(str(pdf_path))
    page_texts: list[tuple[int, str]] = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            page_texts.append((page_number, text))
    return page_texts


def split_text(text: str, chunk_chars: int, overlap_chars: int) -> list[str]:
    cleaned = "\n".join(line.rstrip() for line in text.splitlines()).strip()
    if not cleaned:
        return []

    if chunk_chars <= 0:
        raise ValueError("chunk size must be greater than zero")

    overlap_chars = max(0, min(overlap_chars, chunk_chars - 1))
    chunks: list[str] = []
    start = 0
    text_length = len(cleaned)

    while start < text_length:
        end = min(start + chunk_chars, text_length)
        chunk = cleaned[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= text_length:
            break
        start = max(end - overlap_chars, start + 1)

    return chunks


def build_documents(blob_name: str, page_texts: list[tuple[int, str]], chunk_size: int, chunk_overlap: int) -> list[dict]:
    chunk_chars = chunk_size * 4
    overlap_chars = chunk_overlap * 4
    default_title = PurePosixPath(blob_name).name or blob_name
    documents: list[dict] = []

    for page_number, page_text in page_texts:
        chunks = split_text(page_text, chunk_chars=chunk_chars, overlap_chars=overlap_chars)
        for chunk_index, chunk in enumerate(chunks):
            raw_title = next((line.strip() for line in chunk.splitlines() if line.strip()), default_title)
            document_id = hashlib.sha256(
                f"{blob_name}:{page_number}:{chunk_index}".encode("utf-8")
            ).hexdigest()
            documents.append(
                {
                    "id": document_id,
                    "content": chunk,
                    "source_file": blob_name,
                    "page_number": page_number,
                    "title": raw_title[:100] or default_title[:100],
                }
            )

    return documents


def batched(items: list, batch_size: int) -> Iterable[list]:
    for start in range(0, len(items), batch_size):
        yield items[start : start + batch_size]


def add_embeddings(client: openai.AzureOpenAI, documents: list[dict]) -> None:
    for batch in batched(documents, EMBEDDING_BATCH_SIZE):
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=[document["content"] for document in batch],
        )
        ordered_embeddings = sorted(response.data, key=lambda item: item.index)
        for document, embedding in zip(batch, ordered_embeddings, strict=True):
            document["content_vector"] = embedding.embedding


def upload_documents(search_client: SearchClient, documents: list[dict]) -> int:
    indexed_count = 0
    for batch in batched(documents, UPLOAD_BATCH_SIZE):
        results = search_client.upload_documents(documents=batch)
        succeeded = sum(1 for result in results if result.succeeded)
        failed = len(batch) - succeeded
        indexed_count += succeeded
        if failed:
            LOGGER.warning("%s documents failed to upload in the current batch.", failed)
    return indexed_count


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args()

    credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(
        credential,
        "https://cognitiveservices.azure.com/.default",
    )
    openai_client = openai.AzureOpenAI(
        azure_endpoint=args.openai_endpoint.rstrip("/"),
        azure_ad_token_provider=token_provider,
        api_version="2024-12-01-preview",
    )
    blob_service = BlobServiceClient(
        account_url=f"https://{args.storage_account}.blob.core.windows.net",
        credential=credential,
    )
    search_client = SearchClient(
        endpoint=args.search_endpoint.rstrip("/"),
        index_name=args.index_name,
        credential=credential,
    )

    script_dir = Path(__file__).resolve().parent
    temp_root = script_dir / ".tmp_downloads"
    processed_files = 0
    indexed_chunks = 0

    try:
        blob_names = iter_pdf_blob_names(blob_service, args.container)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to list PDFs in container '{args.container}': {exc}"
        ) from exc

    if not blob_names:
        print(f"No PDF files found in container '{args.container}'.")
        return

    LOGGER.info("Found %s PDF file(s) in container '%s'.", len(blob_names), args.container)

    for blob_name in blob_names:
        temp_path = build_download_path(temp_root, blob_name)
        try:
            LOGGER.info("Processing %s", blob_name)
            download_blob(blob_service, args.container, blob_name, temp_path)
            page_texts = extract_page_texts(temp_path)
            if not page_texts:
                LOGGER.warning("Skipping %s because no extractable text was found.", blob_name)
                continue

            documents = build_documents(
                blob_name=blob_name,
                page_texts=page_texts,
                chunk_size=args.chunk_size,
                chunk_overlap=args.chunk_overlap,
            )
            if not documents:
                LOGGER.warning("Skipping %s because no chunks were generated.", blob_name)
                continue

            add_embeddings(openai_client, documents)
            indexed_for_file = upload_documents(search_client, documents)
            processed_files += 1
            indexed_chunks += indexed_for_file
            LOGGER.info(
                "Indexed %s chunk(s) from %s.",
                indexed_for_file,
                blob_name,
            )
        except Exception as exc:
            LOGGER.warning("Skipping %s due to error: %s", blob_name, exc)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    if temp_root.exists() and not any(temp_root.iterdir()):
        temp_root.rmdir()

    print(f"{processed_files} files processed, {indexed_chunks} chunks indexed")


if __name__ == "__main__":
    main()
