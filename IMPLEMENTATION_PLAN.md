# Azure Cloud Intelligence MCP Server — Implementation Plan

> Companion document to [scope.md](scope.md). This plan turns the scope specification into an
> actionable, phase-by-phase execution roadmap: what gets built, in what order, with what files,
> against what exit criteria. Each phase is meant to be completed and validated before starting
> the next one.

## How to use this document

- Work top to bottom, one phase at a time. Do not start Phase N+1 until Phase N's "Exit Criteria"
  are met.
- Each phase lists: **Goals**, **Tasks**, **Files touched/created**, **Tools implemented**,
  **Verification**, and **Exit Criteria**.
- Update the `Status` line at the top of each phase as work progresses (`Not started` →
  `In progress` → `Done`).

---

## Phase 0 — Environment & Repository Setup

**Status:** In progress (this document + git init being created now)

### Goals
Get the repository, tooling, and local Azure access into a known-good state before any server
code is written.

### Tasks
1. Initialize git in `azure_cloud_intelligent_mcp/` with a `.gitignore` and an initial commit.
2. Create the target repository skeleton (empty placeholder files/dirs so structure is visible
   from day one):
   ```
   azure-cloud-intelligence-mcp/
   ├── docs/
   │   ├── architecture.md
   │   ├── tools.md
   │   ├── security.md
   │   ├── deployment.md
   │   └── tunnel-options.md
   ├── src/
   │   ├── app.py
   │   ├── tools/
   │   ├── auth.py
   │   ├── azure_clients.py
   │   ├── config.py
   │   ├── monitor.py
   │   ├── utils/
   │   └── __init__.py
   ├── tests/
   │   ├── test_tools.py
   │   └── test_server.py
   ├── requirements.txt
   ├── Dockerfile
   ├── .env.example
   ├── .github/workflows/
   └── README.md
   ```
3. Pin the local Python toolchain: create a dedicated virtual environment for this project
   (`python -m venv .venv`) rather than relying on the ambient `pip` (observed to resolve to a
   separate Miniconda Python 3.13 install while `python` resolves to 3.11.9 — mixing these will
   cause dependency/version confusion). Target **Python 3.11+**.
4. Confirm Azure CLI access: `az login`, then `az account set --subscription "<id>"`,
   `az account show` to confirm the active subscription/tenant.
5. Decide and record (in `.env.example`) which auth mode Phase 1 will use for local dev
   (`DefaultAzureCredential` via `az login` is the default per scope.md).
6. Create an Azure AD App Registration / Service Principal for later phases (Phase 1 can start
   with `az login`-based `DefaultAzureCredential`; the SPN is only strictly required once we move
   off a developer's local machine in Phase 4). Record `AZURE_TENANT_ID`, `AZURE_CLIENT_ID` in
   `.env.example` (never commit real secrets).

### Files created
- `.gitignore`
- `IMPLEMENTATION_PLAN.md` (this file)

### Verification
- `git log` shows an initial commit.
- `git status` is clean.
- `az account show` returns the intended subscription.

### Exit Criteria
- Repo is under version control.
- Local Python 3.11 venv works (`python -m venv .venv && .venv\Scripts\activate` on Windows).
- `az login` succeeds and the correct subscription is active.

---

## Phase 1 — Core Infrastructure (MVP)

**Status:** Not started

### Goals
Stand up the minimal MCP server skeleton, wire up Azure authentication, implement three
read-only tools, and prove the full path end-to-end: ChatGPT Desktop → tunnel → MCP server →
Azure API → back to ChatGPT.

### Tasks
1. **Dependencies** — add to `requirements.txt`:
   `mcp` (or `fastmcp`), `uvicorn`, `azure-identity`, `azure-mgmt-resource`,
   `azure-mgmt-compute`, `azure-mgmt-storage`, `python-dotenv`, `pydantic`.
2. **`src/config.py`** — load and validate environment variables
   (`AZURE_SUBSCRIPTION_ID`, `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`,
   `DEFAULT_LOCATION`, `LOG_LEVEL`) with clear startup errors if required values are missing.
3. **`src/auth.py`** — credential factory:
   - If `AZURE_CLIENT_ID` + `AZURE_CLIENT_SECRET` + `AZURE_TENANT_ID` are all set →
     `ClientSecretCredential`.
   - Otherwise → `DefaultAzureCredential()` (falls back to `az login` session, then managed
     identity when deployed).
4. **`src/azure_clients.py`** — instantiate shared, reusable clients:
   `ResourceManagementClient`, `ComputeManagementClient`, `StorageManagementClient`, built once
   at import time using the credential from `auth.py` and `AZURE_SUBSCRIPTION_ID`.
5. **`src/tools/resource_mgmt.py`** — implement:
   - `list_resource_groups()` → `Reader` at subscription scope.
6. **`src/tools/compute.py`** — implement:
   - `list_virtual_machines(resource_group)` → `Reader`/`Virtual Machine Contributor`.
7. **`src/tools/storage.py`** — implement:
   - `list_storage_accounts(resource_group)` → `Reader`/`Storage Account Contributor`.
   - Every tool function: type-hinted args, docstring (used as the MCP tool description),
     try/except around Azure SDK calls translating `ResourceNotFoundError`/`HttpResponseError`
     into user-friendly messages.
8. **`src/app.py`** — the MCP server entrypoint:
   ```python
   from mcp.server.fastmcp import FastMCP
   mcp = FastMCP("Azure Cloud Intelligence")
   # import tool modules so @mcp.tool() decorators register
   if __name__ == "__main__":
       mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)
   ```
   Endpoint will be reachable at `http://localhost:8000/mcp`. Add a plain `/health` route for
   container/load-balancer checks later (via the ASGI-mount variant if needed).
9. **Local protocol test** — use the MCP Inspector (or a small Python `mcp` client) to send
   `initialize` → `tools/list` → `tools/call` against `http://localhost:8000/mcp` and confirm the
   three tools appear with correct schemas and return real data.
10. **Expose publicly for ChatGPT Desktop testing** — two documented options
    (write both into `docs/tunnel-options.md`):
    - **ngrok (default for Phase 1):** `ngrok http 8000` → copy the `https://*.ngrok.app` URL →
      use `<url>/mcp` as the connector endpoint in ChatGPT Desktop with "No Authentication".
    - **OpenAI Secure MCP Tunnel (documented alternative):** requires an OpenAI Platform
      organization with Tunnel permissions (most reliable with a linked ChatGPT
      Business/Enterprise workspace — personal accounts have reported
      `tenant context missing / fallback_missing_entry` errors). Flow: create a tunnel in
      Platform → `tunnel-client init --tunnel-id <id> --mcp-server-url http://127.0.0.1:8000/mcp`
      → `tunnel-client run` → in ChatGPT connector settings choose **Connection: Tunnel** and
      select the tunnel. Keep `tunnel-client run` alive for the whole session.
11. **ChatGPT Desktop connector setup** (per scope.md's step-by-step):
    Settings → Advanced → Developer Mode → Connectors → Create → paste endpoint → Scan Tools →
    Create. Test with prompts like "list my resource groups" and "show VMs in resource group X".

### Files touched/created
`requirements.txt`, `.env.example`, `src/config.py`, `src/auth.py`, `src/azure_clients.py`,
`src/tools/__init__.py`, `src/tools/resource_mgmt.py`, `src/tools/compute.py`,
`src/tools/storage.py`, `src/app.py`, `docs/tunnel-options.md`.

### Tools implemented
`list_resource_groups`, `list_virtual_machines`, `list_storage_accounts`.

### Verification
- MCP Inspector round-trip succeeds locally.
- ChatGPT Desktop "Scan Tools" lists all three tools with non-empty descriptions.
- A live chat correctly lists real resource groups/VMs/storage accounts from your subscription.

### Exit Criteria
- End-to-end natural-language query works through at least one tunnel method.
- No secrets committed to git; `.env` is gitignored, `.env.example` has placeholders only.

---

## Phase 2 — Expand Azure Services

**Status:** Not started

### Goals
Broaden tool coverage to full CRUD across core domains, add monitoring/cost visibility, and put
real error-handling, retry, and confirmation-flow infrastructure in place so later phases don't
have to retrofit it.

### Tasks
1. **Compute** (`src/tools/compute.py`): `get_vm_status`, `start_vm`, `stop_vm`, `create_vm`.
2. **Storage** (`src/tools/storage.py`): `create_storage_account`, `upload_blob`,
   `download_blob`.
3. **Networking** (`src/tools/networking.py`): `list_virtual_networks`,
   `create_network_security_group`, `list_public_ips`.
4. **Key Vault** (`src/tools/keyvault.py`): `list_secrets`, `get_secret` (mask/redact by
   default per scope.md's data-protection guidance), `set_secret`.
5. **Monitoring** (`src/tools/monitoring.py`): `query_log_analytics`, `list_metrics`.
6. **Cost Management** (`src/tools/cost.py`): `get_cost_summary`, `get_advisor_recommendations`.
7. **Azure OpenAI** (`src/tools/openai_service.py`): `list_openai_models`,
   `deploy_openai_model`.
8. **AI Foundry** (`src/tools/ai_foundry.py`): `list_ai_agents`, `start_ai_agent`.
9. **Cross-cutting infrastructure:**
   - `src/utils/errors.py` — shared exception-to-message translation helpers.
   - Configure Azure SDK `RetryPolicy` (exponential backoff for 429/5xx) on all management
     clients in `azure_clients.py`.
   - `src/monitor.py` — structured JSON logging (`python-json-logger`), one log line per tool
     call: timestamp, tool name, args (secrets redacted), status, duration_ms.
   - Add a `requires_confirmation: bool` convention/decorator for all write tools (create/update/
     delete), matching scope.md's "Confirmation Flows" security goal.
   - Build (or update) an **RBAC-to-tool mapping table** in `docs/security.md` mirroring
     scope.md's RBAC table, and assign the minimum roles to the dev/test SPN or MI accordingly.
10. **Unit tests** (`tests/test_tools.py`): mock every Azure SDK client with `unittest.mock`/
    `pytest` fixtures; cover happy path + at least one error path (e.g. `ResourceNotFoundError`)
    per tool.

### Tools implemented (cumulative)
All rows from scope.md's Tool Inventory table for Compute, Storage, Networking, Key Vault,
Monitoring, Cost Mgmt, Azure OpenAI, and AI Foundry.

### Verification
- `pytest` passes with meaningful coverage on `src/tools/`.
- Manually exercise at least one write tool (e.g. `create_storage_account`) through ChatGPT and
  confirm the approval/confirmation prompt appears before execution.
- Confirm retries kick in under simulated throttling (mock a 429 response).

### Exit Criteria
- All Phase 2 tools implemented, unit-tested, and RBAC-documented.
- Structured logs are being emitted for every tool call.

---

## Phase 3 — Advanced Logic & Agents

**Status:** Not started

### Goals
Round out the remaining Azure domains, add cross-service intelligence (the "why is X broken"
class of queries), and harden security for broader/multi-tenant usage.

### Tasks
1. **AKS** (`src/tools/aks.py`): `list_aks_clusters`, `get_aks_pods`.
2. **Functions** (`src/tools/functions.py`): `list_functions`, `get_function_logs`.
3. **SQL** (`src/tools/sql.py`): `list_sql_databases`, `query_sql_db`.
4. **Cosmos DB** (`src/tools/cosmos.py`): `list_cosmos_containers`, `run_cosmos_query`.
5. **Machine Learning** (`src/tools/ml.py`): `list_ml_models`, `run_ml_pipeline`.
6. **Cross-service diagnostic tool(s)**: e.g. `diagnose_vm_issue(resource_group, vm_name)` that
   internally calls Monitor (metrics/logs) + Advisor + VM state, and returns a synthesized
   root-cause summary — demonstrating the "interactive insights" functional goal from scope.md.
7. **Security hardening:**
   - Evaluate whether OAuth2 token validation is needed (multi-tenant / shared server scenario)
     per OpenAI's developer-mode MCP auth guidance; implement if required.
   - Wire audit logs (tool name, args, outcome, timestamp) into Azure Log Analytics for
     compliance retention.
8. Extend unit tests to cover all new tools and the diagnostic tool's aggregation logic.

### Verification
- `diagnose_vm_issue` (or equivalent) returns a coherent, correct summary against a real or
  simulated unhealthy VM.
- Audit log entries are queryable in Log Analytics.

### Exit Criteria
- Full tool inventory from scope.md is implemented across all documented domains.
- Audit trail is verifiable end-to-end for both read and write tool calls.

---

## Phase 4 — Productionization

**Status:** Not started

### Goals
Move from "runs on a laptop with ngrok" to a scalable, observable, CI/CD-managed production
deployment, and switch the primary ChatGPT connection to the Secure MCP Tunnel or a stable HTTPS
endpoint.

### Tasks
1. **Containerization** — multi-stage `Dockerfile` (`python:3.12-slim` base), non-root user,
   `/health` endpoint, minimal final image size.
2. **CI pipeline** (`.github/workflows/ci.yml`): on push/PR — install deps, run `ruff`/`mypy`,
   run `pytest`, build the Docker image.
3. **CD pipeline** (`.github/workflows/deploy.yml`): on merge to `main` — push image to Azure
   Container Registry (ACR), deploy to **Azure Container Apps** using a **Managed Identity**
   (no stored client secrets), with autoscaling rules (e.g. scale out at CPU > 60%).
4. **Observability:**
   - Integrate OpenTelemetry tracing/metrics; export to Application Insights.
   - Container Insights / Log Analytics for logs.
   - Dashboards + alerts for error-rate spikes and latency in Azure Monitor.
5. **Load testing** — locust (or k6) scripted concurrent MCP sessions; validate the server holds
   up and streaming responses behave under load; tune replica counts / stateless HTTP mode.
6. **Production connector** — finalize the OpenAI Secure MCP Tunnel setup (or a stable HTTPS
   endpoint with a real TLS cert / Application Gateway) as the long-term ChatGPT connection path,
   retiring ngrok for anything beyond local dev.
7. Update `docs/deployment.md` with the full runbook (build → push → deploy → verify).

### Verification
- CI is green on a test PR.
- A deploy from `main` lands in Container Apps automatically.
- Dashboards show live request metrics; alert fires correctly on a simulated failure spike.
- ChatGPT connector works against the production endpoint without ngrok running.

### Exit Criteria
- Fully automated build → test → deploy pipeline.
- Production endpoint is stable, observable, and scales under load.

---

## Phase 5 — Future Enhancements (Backlog)

**Status:** Not scheduled — captured for future planning only.

- **Multi-Cloud:** extend the same tool/connector pattern to AWS/GCP.
- **Policy Checks:** validate proposed actions against Azure Policy before execution.
- **Infrastructure-as-Code:** auto-generate Bicep/ARM for requested changes and require
  explicit approval before applying.
- **Autonomous Actions:** guarded, pre-approved automated actions triggered on schedules/events
  (e.g. scale down dev VMs on weekends).
- **Plugin Ecosystem:** a pluggable interface for third-party tool modules (GitHub, Jira, etc.)
  that can reference Azure context.

---

## Cross-Phase Reference

### Tunnel Options Summary

| Option | Best for | Requirements | Notes |
|---|---|---|---|
| ngrok | Phase 1 local dev/testing | Free ngrok account | Fastest to set up; public URL exposes local port while running |
| OpenAI Secure MCP Tunnel | Phase 4 production / enterprise | OpenAI Platform org with Tunnel permissions; most reliable with linked ChatGPT Business/Enterprise workspace | No public inbound exposure; run `tunnel-client` as a long-lived daemon |

### Repository Structure (target end-state)

See Phase 0, Task 2 above for the full tree; it matches scope.md's "Repository Structure"
section exactly.

### Definition of Done for the Overall Project

- All tool inventory rows from scope.md implemented, tested, and RBAC-documented.
- Security goals met: least-privilege roles, confirmation flows on writes, audit logging, no
  secrets in code/logs.
- Runs in production on Azure Container Apps (or AKS) with observability and autoscaling.
- Documented and reproducible developer setup (local → tunnel → production).
