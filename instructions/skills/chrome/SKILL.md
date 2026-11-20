---
name: chrome
description: Use this when the user asks you to browse, inspect, or interact with a web page and the chrome_* tools are not available. Launches a headless Chrome with remote debugging and a local MCP bridge so the chrome_* tools become available.
---

The `chrome_*` tools come from a local chrome-devtools-mcp server bridged over HTTP. If they are not in your toolset, the bridge is not running. Launch it, then end your turn — the session re-probes failed MCP servers at the start of each turn, so the tools become available on the next turn.

First check whether the pieces are already running; do not start a second copy:

- Chrome CDP: `curl -s http://127.0.0.1:9222/json/version`
- Bridge: `curl -s -o /dev/null -w '%{http_code}' -X POST http://127.0.0.1:8080/mcp -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"bot","version":"0"}}}'`

Detect the platform with `uname` (`Darwin` is macOS, `Linux` is Linux). On macOS, Chrome is an app bundle, not a `google-chrome` binary on PATH — `which google-chrome` or `which chromium` failing does not mean Chrome is missing; check with `[ -d "/Applications/Google Chrome.app" ]`.

If Chrome is not running, start it headless with a dedicated profile (never the user's everyday profile):

- macOS: `open -a "Google Chrome" --args --headless=new --remote-debugging-port=9222 --user-data-dir="$PWD/chrome-profile"`
- Linux: `nohup google-chrome --headless=new --remote-debugging-port=9222 --user-data-dir="$PWD/chrome-profile" >/dev/null 2>&1 &`

If the bridge is not running, start it:

`nohup npx -y mcp-proxy --host 127.0.0.1 --port 8080 -- npx -y chrome-devtools-mcp@latest --browserUrl=http://127.0.0.1:9222 --filesystemRoot="$PWD" > chrome-mcp.log 2>&1 &`

`--filesystemRoot` lets the file-writing tools (screenshots, traces) save into the workspace; without it they fail with `Access denied: ... is not within any of the configured workspace roots`. If the bridge is already running but was started without it, stop it with `pkill -f chrome-devtools-mcp` and start it again with the flag.

Poll the two curl commands above until both answer (up to a minute on the first npx run). Then tell the user Chrome is ready — the chrome_* tools are available from the next turn.

## Headed mode

Headless is the default. Only when the user explicitly wants to watch the browser, drop `--headless=new` from the Chrome command; everything else stays the same.

Screenshots, navigation, and script evaluation all work in headless mode.
