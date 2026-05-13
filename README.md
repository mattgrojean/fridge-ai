# Appliance AI v2 — Technician RAG Chatbot

## Overview

Appliance AI v2 is an internal chatbot for appliance repair technicians. It uses retrieval-augmented generation (RAG) over PDF service manuals so technicians can ask natural-language questions and receive grounded answers with manual context. The solution uses GPT-4.1-mini for chat responses and Azure AI Search hybrid retrieval to combine vector similarity, keyword matching, and semantic reranking.

## Architecture

- **Azure Container Apps** hosts the FastAPI backend and static web UI.
- **Azure OpenAI** provides GPT-4.1-mini for chat completions and `text-embedding-3-small` for document embeddings.
- **Azure AI Search** stores manual chunks and supports hybrid retrieval with vector search, keyword search, and semantic ranking.
- **Azure Blob Storage** stores the source PDF manuals.
- **Microsoft Entra ID** provides SSO authentication for technicians.
- **Managed identity** is used end-to-end for Azure authentication so no API keys are required.

## Prerequisites

- Azure subscription with permission to deploy Azure resources
- Terraform 1.5 or later
- Python 3.12 or later
- Docker
- Azure CLI authenticated to the target tenant and subscription

## Quick Start

### 1. Clone and configure

```powershell
Set-Location appliance-ai\v2\infra\terraform
Copy-Item environments\dev\dev.tfvars.example environments\dev\dev.tfvars
# Edit environments\dev\dev.tfvars and set your subscription ID
```

### 2. Deploy infrastructure

```powershell
terraform init -backend-config="environments\dev\dev-backend-config.json"
terraform plan -var-file="environments\dev\dev.tfvars"
terraform apply -var-file="environments\dev\dev.tfvars"
```

### 3. Create the search index

```powershell
$searchEndpoint = terraform output -raw search_endpoint
Set-Location ..\..
pip install -r ai\scripts\requirements.txt
python ai\scripts\create_index.py --search-endpoint $searchEndpoint
```

### 4. Upload PDFs and ingest

```powershell
Set-Location infra\terraform
$openAiEndpoint = terraform output -raw openai_endpoint
$storageAccount = terraform output -raw storage_account_name
Set-Location ..\..
az storage blob upload-batch -d manuals -s .\pdfs --account-name $storageAccount --auth-mode login
python ai\scripts\ingest_manuals.py --search-endpoint $searchEndpoint --openai-endpoint $openAiEndpoint --storage-account $storageAccount
```

### 5. Build and deploy the app

```powershell
Set-Location infra\terraform
$registryServer = terraform output -raw container_registry_login_server
$resourceGroup = terraform output -raw resource_group_name
$registryName = $registryServer.Split('.')[0]
Set-Location ..\..
az acr login --name $registryName
docker build -t appliance-ai-chat:latest .\ai\app
docker tag appliance-ai-chat:latest $registryServer/appliance-ai-chat:latest
docker push $registryServer/appliance-ai-chat:latest
az containerapp update --name ca-appliance-ai-dev --resource-group $resourceGroup --image $registryServer/appliance-ai-chat:latest
```

### 6. Update Entra ID redirect URI

After the Container App is deployed, update the Entra ID app registration redirect URI with the live Container App URL.

## Local Development

```powershell
Set-Location ai\app
Copy-Item .env.sample .env
# Set ENTRA_CLIENT_ID=dev-skip-auth in .env to skip auth locally
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

## Cost Estimate

Approximate monthly development cost for a small shared environment:

| Service | Assumption | Approx. Monthly Cost |
| --- | --- | ---: |
| Azure Container Apps | Low-volume app with 1 small revision | $20 |
| Azure AI Search | Basic tier | $75 |
| Azure Blob Storage | Small PDF corpus | $2 |
| Azure OpenAI | Light dev/test usage | $5 - $15 |
| Azure Container Registry + Log Analytics | Minimal usage | $3 - $8 |
| **Estimated total** |  | **$85 - $100** |

## Project Structure

```text
appliance-ai\v2
├── README.md
├── .gitignore
├── ai
│   ├── app
│   │   └── static
│   └── scripts
│       ├── create_index.py
│       ├── ingest_manuals.py
│       └── requirements.txt
└── infra
    └── terraform
        └── environments
            └── dev
```

## Day 2 Operations

### Add new manuals

1. Upload new PDF files into the `manuals` blob container.
2. Re-run the ingestion script to extract, chunk, embed, and index the new content.

```powershell
az storage blob upload-batch -d manuals -s .\pdfs --account-name $storageAccount --auth-mode login
python ai\scripts\ingest_manuals.py --search-endpoint $searchEndpoint --openai-endpoint $openAiEndpoint --storage-account $storageAccount
```

### Update the model deployment

- Update the Azure OpenAI deployment names or model configuration used by the application.
- Redeploy the Container App image after changing app configuration.
- Re-run ingestion if you switch to a different embedding model or vector dimension.

### Scale up for production

- Move Azure AI Search to a higher SKU with additional partitions and replicas.
- Increase Azure Container Apps minimum and maximum replicas.
- Expand monitoring, diagnostics retention, and operational alerting.
- Review Blob Storage redundancy and backup requirements for production workloads.
