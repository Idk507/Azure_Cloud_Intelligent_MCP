# Self-Hosted Quick Start

Use this path when you want Azure requests to run as your own Azure identity. You do not need the repository publisher to host anything or provide credentials.

## Prerequisites

- Python 3.11 or later, or Docker.
- Azure CLI authenticated as the user who should access Azure: `az login`.
- A ChatGPT workspace/plan that supports custom MCP apps if connecting through ChatGPT.

## Run with Python

```powershell
git clone <YOUR_FORK_OR_REPOSITORY_URL>
cd azure_cloud_intelligent_mcp
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
az login
$env:AZURE_SUBSCRIPTION_ID = '<your-subscription-id>'
python -m src.app
```

The service listens on `http://127.0.0.1:8000`; its health endpoint is `/health` and its MCP endpoint is `/mcp`.

When using an HTTPS tunnel, set `MCP_ALLOWED_HOSTS` to the tunnel hostname (without `https://` or `/mcp`) before starting the service. For example: `MCP_ALLOWED_HOSTS=my-tunnel.ngrok-free.dev`.

If you do not know the subscription ID, start the service without `AZURE_SUBSCRIPTION_ID`, call `list_accessible_subscriptions`, then restart the service with the explicitly selected subscription ID. The server never chooses a subscription automatically.

## Run with Docker

Docker containers cannot use a host Azure CLI session automatically. For a container, use a managed identity when deployed to Azure, or configure a non-interactive Azure Identity credential through the container runtime's secret manager. Do not put credentials in an image, Dockerfile, git repository, or ChatGPT message.

```powershell
docker build --tag azure-cloud-intelligence-mcp:local .
docker run --rm -p 8000:8000 `
  -e AZURE_SUBSCRIPTION_ID='<your-subscription-id>' `
  azure-cloud-intelligence-mcp:local
```

Before connecting any MCP client, verify `http://127.0.0.1:8000/health` and run a read-only tool first.
