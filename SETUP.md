# Azure Cloud Intelligence MCP — Complete Setup

This guide is the single setup path for a fresh clone on Windows. It uses your own Azure identity and subscription. No repository publisher credentials are required.

## What you need

- Windows PowerShell
- Python 3.11 or newer
- Azure CLI
- An Azure account with permission to read the subscription you select
- Codex or ChatGPT Developer Mode
- ngrok only when connecting through the Codex plugin UI or ChatGPT

## 1. Clone and install

```powershell
git clone https://github.com/Idk507/Azure_Cloud_Intelligent_MCP
cd azure_cloud_intelligent_mcp
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, run this once in the current terminal and retry the activation command:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## 2. Sign in to Azure and choose a subscription

```powershell
az login
az account list --output table
```

Copy the ID of the subscription you intend to use, then set it only for this terminal session:

```powershell
$env:AZURE_SUBSCRIPTION_ID = '<YOUR-SUBSCRIPTION-ID>'
```

Do not use a subscription ID belonging to another person or organization without authorization.

## 3. Verify dependencies

```powershell
python scripts/check_environment.py
python -m pytest -q
```

The dependency check must report no missing packages. The tests should pass; one intentionally skipped test is expected.

## 4. Choose how to connect

### A. Use the server locally

Start the server:

```powershell
python -m uvicorn src.app:http_app --host 127.0.0.1 --port 8000
```

In a second PowerShell window, verify it:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Expected result:

```json
{"status":"ok"}
```

### B. Run locally with Docker (optional)

Docker avoids a Python installation, but it cannot automatically use the `az login` session from
your Windows host. Use it with a service principal configured with the Azure RBAC permissions you
need, or with a managed identity after deploying the container to Azure.

```powershell
docker build --tag azure-cloud-intelligence-mcp:local .
$env:AZURE_TENANT_ID = '<YOUR-TENANT-ID>'
$env:AZURE_CLIENT_ID = '<YOUR-SERVICE-PRINCIPAL-CLIENT-ID>'
$env:AZURE_CLIENT_SECRET = '<YOUR-SERVICE-PRINCIPAL-SECRET>'

docker run --rm -p 8000:8000 `
  -e AZURE_SUBSCRIPTION_ID -e AZURE_TENANT_ID -e AZURE_CLIENT_ID -e AZURE_CLIENT_SECRET `
  azure-cloud-intelligence-mcp:local
```

Do not place these values in the Dockerfile, image, repository, or a committed `.env` file. For a
personal Azure CLI login, use option A instead.

### C. Create an HTTPS tunnel for Codex plugin UI or ChatGPT

The plugin UI shown in Codex and ChatGPT needs a public HTTPS endpoint; it cannot use `127.0.0.1` directly.

In a separate PowerShell window, start ngrok:

```powershell
ngrok http 8000
```

It displays a forwarding URL similar to:

```text
https://example.ngrok-free.dev -> http://localhost:8000
```

Copy only the hostname, such as `example.ngrok-free.dev`. Stop the local MCP server, set this additional safety variable, and start it again:

```powershell
$env:MCP_ALLOWED_HOSTS = 'example.ngrok-free.dev'
python -m uvicorn src.app:http_app --host 127.0.0.1 --port 8000
```

Your MCP endpoint is now:

```text
https://example.ngrok-free.dev/mcp
```

Keep the ngrok and MCP-server windows open. A free ngrok URL changes after restart; when it changes, update `MCP_ALLOWED_HOSTS` and restart the MCP server.

## 5. Add the plugin in Codex

1. Open **Customize** → **Plugins**.
2. Click **Add** → **Create MCP App**.
3. Choose the **Server URL** tab.
4. Enter a name, for example `Azure Cloud Intelligence`.
5. Enter the complete HTTPS endpoint ending in `/mcp`.
6. Choose **No authentication** for this personal, local-tunnel setup.
7. Read and tick the custom-server warning.
8. Click **Create**, then scan tools if prompted.
9. In a new Codex chat, ask: `List my accessible Azure subscriptions.`

## 6. Add the app in ChatGPT

1. Open ChatGPT on the web.
2. Go to **Settings** → **Apps** → **Advanced settings** and enable **Developer mode**. Your workspace plan and administrator permissions must support it.
3. Go to **Apps** → **Create**.
4. Enter the same HTTPS endpoint ending in `/mcp`.
5. Choose **No authentication** for the personal local-tunnel setup.
6. Click **Scan tools**, then **Create**.
7. Start a new chat, select the app from the tools menu, and ask: `List my accessible Azure subscriptions.`

ChatGPT custom MCP apps connect to remote endpoints. For organization-wide deployment, use the separate Entra OAuth/OBO configuration described in [docs/portable-plugin-architecture.md](docs/portable-plugin-architecture.md).

## 7. Safe first actions

Start with read-only tools:

```text
list_accessible_subscriptions
list_resource_groups
list_azure_resources
```

For any create, update, delete, start, or stop action, call the matching `plan_*` tool first. Review the target and payload, then use the returned one-time `approval_id` only with the matching execution tool.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `Couldn't create MCP app` | Ensure the endpoint uses `https://.../mcp`, not `http://127.0.0.1:8000/mcp`. |
| ngrok shows `GET / 404` | Expected. The root path is not an MCP endpoint; use `/mcp`. |
| `Invalid Host header` | Set `MCP_ALLOWED_HOSTS` to the ngrok hostname, then restart the MCP server. |
| Azure authentication error | Run `az login` again and restart the MCP server. |
| Azure authorization error | Your Azure identity needs the relevant least-privilege RBAC role; see [docs/security-rbac.md](docs/security-rbac.md). |
| ChatGPT cannot add the app | Confirm Developer Mode is enabled and your account/workspace supports custom MCP apps. |

## Production note

An ngrok tunnel is suitable for personal development only. Do not use it as a permanent public endpoint. Use the hosted Entra OAuth/OBO architecture for a multi-user or organization-wide deployment.
