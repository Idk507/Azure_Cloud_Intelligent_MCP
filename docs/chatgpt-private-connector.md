# Connect a Self-Hosted Server to ChatGPT

ChatGPT connects to remote MCP endpoints; it cannot directly reach `localhost` on your computer. Keep the Azure MCP server local, then expose only its `/mcp` endpoint through a secure tunnel or deploy it behind HTTPS.

## Development connection

1. Start the local server as described in [self-hosted-quickstart.md](self-hosted-quickstart.md).
2. Use an HTTPS tunnel. See [tunnel-options.md](tunnel-options.md) for development and secure-tunnel options.
3. Verify the tunnel resolves to the MCP endpoint, for example `https://your-tunnel.example/mcp`.
4. In ChatGPT Developer Mode, create a private custom MCP app using that HTTPS endpoint and scan its tools.
5. Test `list_accessible_subscriptions` or another read-only tool before using a planned mutation.

## Safety requirements

- Do not expose the raw local port to the public internet.
- Treat a temporary tunnel URL as a development endpoint only.
- Keep the server and tunnel running only while you need the connection.
- Use the tool's plan and single-use approval flow for every controlled action.
- Disconnect the custom app when you finish testing.

For an organization-wide, always-on endpoint, use the hosted multi-tenant design in [portable-plugin-architecture.md](portable-plugin-architecture.md), not a developer tunnel.
