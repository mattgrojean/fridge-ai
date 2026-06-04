"""Vision model integration for OCR extraction from appliance images.

Field technicians photograph model-number plates, error codes, or part
labels.  This module sends the image to a vision-capable model deployment
and returns the extracted text so it can be used as context in a RAG query.
"""

import base64
import logging

from config import FOUNDRY_VISION_MODEL_DEPLOYMENT
from search import get_openai_client

logger = logging.getLogger(__name__)

OCR_SYSTEM_PROMPT = (
    "You are an OCR extraction tool for appliance repair. "
    "Extract any model numbers, serial numbers, error codes, part numbers, "
    "and identifying text from the image. "
    "Return ONLY the extracted text, one item per line. "
    "Do not add commentary, explanations, or markdown formatting. "
    "If no text is visible, return an empty response."
)


def extract_text_from_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
    """Send an image to the vision model and return extracted text.

    Args:
        image_bytes: Raw image bytes (JPEG, PNG, etc.).
        mime_type: MIME type of the image (default ``image/jpeg``).

    Returns:
        The extracted text, or an empty string if nothing was found.
    """
    client = get_openai_client()
    data_uri = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"

    try:
        response = client.chat.completions.create(
            model=FOUNDRY_VISION_MODEL_DEPLOYMENT,
            messages=[
                {"role": "system", "content": OCR_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": data_uri, "detail": "auto"},
                        },
                        {
                            "type": "text",
                            "text": "Extract all visible text from this image.",
                        },
                    ],
                },
            ],
            max_tokens=500,
            temperature=0,
        )
    except Exception:
        logger.warning("Vision model call failed", exc_info=True)
        return ""

    text = (response.choices[0].message.content or "").strip()
    logger.info("OCR extracted %d characters from image", len(text))
    return text
