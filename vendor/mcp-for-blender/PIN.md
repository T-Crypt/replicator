Vendored from https://github.com/ahujasid/mcp-for-blender at 8f40787fbde8e6d8fe51c5a3553e5635fff40d2b (MIT).
Replicator launches Blender with BLENDERMCP_NO_UPDATE_CHECK=1; the MCP server runs with DISABLE_TELEMETRY=true.
The socket stays on localhost (the add-on refuses non-loopback unless allow_remote_connections is set; we never set it).
