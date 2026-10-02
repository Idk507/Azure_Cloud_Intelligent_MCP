from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

REQUIRED = {
    "fastapi": "fastapi",
    "mcp": "mcp",
    "pydantic": "pydantic",
    "uvicorn": "uvicorn",
    "pytest": "pytest",
    "pytest_cov": "pytest_cov",
    "azure.core": "azure.core",
    "azure.identity": "azure.identity",
    "jwt": "jwt",
    "azure.mgmt.compute": "azure.mgmt.compute",
    "azure.mgmt.resource": "azure.mgmt.resource",
    "azure.mgmt.authorization": "azure.mgmt.authorization",
    "azure.mgmt.appcontainers": "azure.mgmt.appcontainers",
    "azure.mgmt.advisor": "azure.mgmt.advisor",
    "azure.mgmt.containerservice": "azure.mgmt.containerservice",
    "azure.mgmt.cognitiveservices": "azure.mgmt.cognitiveservices",
    "azure.mgmt.costmanagement": "azure.mgmt.costmanagement",
    "azure.mgmt.keyvault": "azure.mgmt.keyvault",
    "azure.mgmt.network": "azure.mgmt.network",
    "azure.mgmt.policyinsights": "azure.mgmt.policyinsights",
    "azure.mgmt.resourcegraph": "azure.mgmt.resourcegraph",
    "azure.mgmt.storage": "azure.mgmt.storage",
    "azure.mgmt.web": "azure.mgmt.web",
    "azure.keyvault.secrets": "azure.keyvault.secrets",
    "azure.monitor.query": "azure.monitor.query",
    "azure.storage.blob": "azure.storage.blob",
    "azure.ai.projects": "azure.ai.projects",
    "opentelemetry.sdk": "opentelemetry.sdk",
    "opentelemetry.exporter.otlp.proto.http": "opentelemetry.exporter.otlp.proto.http",
}


def has_module(name: str) -> bool:
    try:
        return bool(importlib.util.find_spec(name))
    except Exception:
        return False


def main() -> int:
    results = {k: has_module(v) for k, v in REQUIRED.items()}
    missing = [name for name, present in results.items() if not present]

    payload = {
        "python": sys.version,
        "results": results,
        "missing": missing,
        "ready_for_full_tests": len(missing) == 0,
        "ready_for_full_phase1_tests": len(missing) == 0,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))

    return 0 if not missing else 2


if __name__ == "__main__":
    raise SystemExit(main())
