# Appliance AI v2 — Technician RAG Chatbot

## Overview

Appliance AI v2 is an internal chatbot for appliance repair technicians. It uses retrieval-augmented generation (RAG) over PDF service manuals so technicians can ask natural-language questions and receive grounded answers with manual context. The solution now uses Microsoft Foundry for chat orchestration and Foundry IQ for retrieval, with Azure AI Search underneath as the knowledge source.

## Architecture

- **Azure Container Apps** hosts the FastAPI backend and static web UI.
- **Microsoft Foundry** hosts the project and agent that handle chat orchestration.
- **Foundry IQ** provides the knowledge base and retrieval flow for service manuals.
- **Azure AI Search** stores the manual index that backs the Foundry IQ knowledge base.
- **Azure AI Services** provides the model deployments used by the Foundry agent.
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

### 4. Bootstrap Foundry IQ

After `terraform apply` and after the search index exists, create the Foundry knowledge source, knowledge base, and project connection:

```powershell
$projectResourceId = terraform output -raw foundry_project_resource_id
$aiServicesEndpoint = terraform output -raw ai_services_endpoint
python ai\scripts\create_knowledge_base.py `
  --search-endpoint $searchEndpoint `
  --ai-services-endpoint $aiServicesEndpoint `
  --project-resource-id $projectResourceId `
  --model-deployment gpt-4-1-mini `
  --model-name gpt-4.1-mini
```

### 5. Upload PDFs and ingest

```powershell
Set-Location infra\terraform
$storageAccount = terraform output -raw storage_account_name
Set-Location ..\..
az storage blob upload-batch -d manuals -s .\pdfs --account-name $storageAccount --auth-mode login
python ai\scripts\ingest_manuals.py --search-endpoint $searchEndpoint --storage-account $storageAccount
```

### 6. Build and deploy the app

```powershell
Set-Location infra\terraform
terraform apply -var-file="environments\dev\dev.tfvars"
$registryServer = terraform output -raw container_registry_login_server
$resourceGroup = terraform output -raw resource_group_name
$registryName = $registryServer.Split('.')[0]
Set-Location ..\..
pip install -r ai\app\requirements.txt
az acr login --name $registryName
docker build -t appliance-ai-chat:latest .\ai\app
docker tag appliance-ai-chat:latest $registryServer/appliance-ai-chat:latest
docker push $registryServer/appliance-ai-chat:latest
az containerapp update --name ca-appliance-ai-dev --resource-group $resourceGroup --image $registryServer/appliance-ai-chat:latest
```

### 7. Update Entra ID redirect URI

After the Container App is deployed, update the Entra ID app registration redirect URI with the live Container App URL.

### 8. Restrict access to the allowed Entra group

Terraform creates a security group named `Appliance AI Allowed Users (<env>)` and seeds it with your signed-in account. Add any other allowed users to that group, then redeploy so the app picks up the group ID in `ENTRA_ALLOWED_GROUP_ID`.

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
| Azure AI Services / Foundry | Light dev/test usage | $5 - $15 |
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
│       ├── create_knowledge_base.py
│       ├── ingest_manuals.py
│       └── requirements.txt
└── infra
    └── terraform
        └── environments
            └── dev
```

## Day 2 Operations

## Deployment Validation

### Pre-deploy citation/manual smoke checks

Before this feature is deployed, these checks will fail or are not yet possible:

```powershell
# 1. Citation cards should no longer show mcp://searchindex URLs
# 2. /documents/resolve should require auth and return a short-lived URL
# 3. Desktop preview should keep chat visible
# 4. Small-screen fallback should still allow opening the document
```

Confirm the current Container App revision is still missing the preview-related configuration before rollout:

```powershell
az containerapp show -g rg-appliance-ai-dev -n ca-appliance-ai-dev --query "properties.template.containers[0].env[].name" -o tsv
```

Expected before deploy: `AZURE_STORAGE_ACCOUNT_NAME`, `AZURE_STORAGE_CONTAINER_NAME`, and `SEARCH_INDEX_NAME` are not present.

### Post-deploy validation

After applying Terraform and pushing the updated app image, validate the infrastructure and live app:

```powershell
Set-Location infra\terraform
terraform validate
Set-Location ..\..
Invoke-WebRequest -UseBasicParsing https://ca-appliance-ai-dev.nicesand-7a91f96a.centralus.azurecontainerapps.io/health
```

Expected results:

- `terraform validate` returns `Success! The configuration is valid.`
- `/health` returns `200 OK`

Manual browser validation:

1. Sign in as an allowed user.
2. Ask a question with a known manual-backed answer.
3. Confirm citation labels show the PDF filename and actual page number.
4. Confirm **Preview** opens the PDF in the right pane on desktop.
5. Confirm **Open in new tab** opens the same document without losing the chat tab.
6. Confirm the raw `【...†source】` marker no longer appears in the answer body.

### Add new manuals

1. Upload new PDF files into the `manuals` blob container.
2. Re-run the ingestion script to extract, chunk, embed, and index the new content.

```powershell
az storage blob upload-batch -d manuals -s .\pdfs --account-name $storageAccount --auth-mode login
python ai\scripts\ingest_manuals.py --search-endpoint $searchEndpoint --openai-endpoint $openAiEndpoint --storage-account $storageAccount
```

### Use citations to open manuals

- Each answer citation offers **Preview** and **Open in new tab**.
- Preview keeps chat visible on desktop while loading the cited PDF page.
- The backend issues short-lived document links using managed identity; no permanent blob URLs are exposed to the browser.

### Update the model deployment

- Update the Foundry agent or Azure AI Services model deployment used by the application.
- Redeploy the Container App image after changing app configuration.
- Re-run ingestion if you switch to a different embedding model or vector dimension.

### Scale up for production

- Move Azure AI Search to a higher SKU with additional partitions and replicas.
- Increase Azure Container Apps minimum and maximum replicas.
- Expand monitoring, diagnostics retention, and operational alerting.
- Review Blob Storage redundancy and backup requirements for production workloads.
