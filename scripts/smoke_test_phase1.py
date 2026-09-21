from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src import app as server_app


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    init_payload = server_app.initialize_response()
    assert_true(bool(init_payload.get("protocolVersion")), "Missing protocolVersion")

    tools_payload = server_app.tools_list_response()
    tool_names = {tool["name"] for tool in tools_payload.get("tools", [])}
    assert_true("list_resource_groups" in tool_names, "Missing list_resource_groups tool")
    assert_true("list_virtual_machines" in tool_names, "Missing list_virtual_machines tool")
    assert_true("list_storage_accounts" in tool_names, "Missing list_storage_accounts tool")

    os.environ.pop("AZURE_SUBSCRIPTION_ID", None)
    health_callable = None
    for route in server_app.app.routes:
        if getattr(route, "path", None) == "/health":
            health_callable = route.endpoint
            break

    assert_true(health_callable is not None, "Health endpoint is not registered")
    health_payload = health_callable()
    assert_true(health_payload.get("status") == "degraded", "Expected degraded status without subscription")

    output = {
        "ok": True,
        "checks": {
            "initialize": True,
            "tools_list": True,
            "health_endpoint": True,
        },
        "tool_names": sorted(tool_names),
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
