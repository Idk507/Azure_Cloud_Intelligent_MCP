# Tunnel Options For Phase 1

Phase 1 requires exposing the local MCP endpoint (`/mcp`) over HTTPS so remote MCP clients can connect.

## Option A: ngrok (development quick path)

1. Start the local server:
   - `python -m src.app`
2. Start ngrok:
   - `ngrok http 8000`
3. Copy the generated HTTPS URL and append `/mcp`.
4. Use that endpoint in your MCP client configuration.

Notes:

- Keep ngrok and the local server running during tests.
- Use ngrok only for local development.

## Option B: OpenAI Secure MCP Tunnel (recommended for managed environments)

1. Create a tunnel in your OpenAI platform configuration.
2. Start the local server:
   - `python -m src.app`
3. Start the tunnel client and point it to `http://127.0.0.1:8000/mcp`.
4. Select the tunnel from the MCP client connector settings.

Notes:

- This avoids exposing an inbound public URL directly to your machine.
- Keep the tunnel process alive for the whole MCP session.

## Basic Connectivity Check

After configuring either option:

1. Ensure `/health` returns `{"status":"ok"}`.
2. Scan tools in the MCP client.
3. Run one read-only call (`list_resource_groups`) and verify a structured response.
