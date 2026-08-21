# Local LinkedIn MCP Quick Start

This guide runs **your fork** of `abetoluwani/linkedin-mcp-server` on your own computer. It keeps the MCP browser profile on that computer, so the session can persist without a cloud server and without sending a LinkedIn cookie or token to chat, a connector configuration, or a third party.

> The MCP profile is separate from your everyday browser profile. The local import flow reads and validates an existing local LinkedIn session, then saves the validated session into the MCP's private local profile. It never prints the cookie value.

## Before You Start

You need a macOS or Linux computer with a local LinkedIn browser session and [uv](https://docs.astral.sh/uv/) installed. Clone your fork, make the launcher executable, and create its private profile location.

```bash
git clone https://github.com/abetoluwani/linkedin-mcp-server.git
cd linkedin-mcp-server
chmod +x scripts/local/linkedin-mcp-local.sh
./scripts/local/linkedin-mcp-local.sh setup
```

The setup command creates `~/.linkedin-mcp` with owner-only permissions. Do not place unrelated files in that directory.

## Create the MCP Session Once

Choose one of the following methods. Both retain the session only on your computer.

| Preferred method | Command | When to use it |
| --- | --- | --- |
| Reuse the current browser session | `./scripts/local/linkedin-mcp-local.sh import` | Recommended when Chrome, Chromium, Brave, Edge, Arc, Vivaldi, or another supported local browser is already signed in to LinkedIn. |
| Fresh isolated login | `./scripts/local/linkedin-mcp-local.sh login` | Use if import is unavailable, LinkedIn rejects the imported session, or you prefer a completely separate MCP browser profile. |

For an import, close the source browser first if macOS asks for permission to access its browser-security storage. For a fresh login, a separate local browser window opens. Complete LinkedIn login, any verification, or captcha directly in that window. Never send a password, one-time code, or browser cookie to an agent.

## Confirm Session Readiness

After the import or login finishes, run:

```bash
./scripts/local/linkedin-mcp-local.sh status
```

A ready status means the local MCP can begin work. A login-required or expired result means stop and run the import or login command again. Do not treat a failed or ambiguous status as permission to perform engagement actions.

## Start Your Local MCP

For a local desktop MCP client, start stdio mode:

```bash
./scripts/local/linkedin-mcp-local.sh serve-stdio
```

For a local HTTP-capable MCP client, start a loopback-only endpoint:

```bash
./scripts/local/linkedin-mcp-local.sh serve-http
```

The default HTTP endpoint is `http://127.0.0.1:8080/mcp`. It is deliberately bound to `127.0.0.1`, not the public internet. Do not change it to `0.0.0.0` unless you first add strong authentication, TLS, and network controls.

## Client Configuration Pattern

A desktop MCP client that can start local commands should use this pattern, replacing `/absolute/path` with the actual cloned repository location:

```json
{
  "command": "/absolute/path/linkedin-mcp-server/scripts/local/linkedin-mcp-local.sh",
  "args": ["serve-stdio"]
}
```

The running local service will expose your fork's login-status, engagement-status, Like, and comment tools. Each engagement action still requires the explicit confirmation parameters and visible verification implemented in your fork.

## Operating Rules

| Rule | Reason |
| --- | --- |
| Keep the local computer available when a local MCP client or scheduled action needs it. | The browser profile and MCP process live on that computer. |
| Check status before every engagement batch. | A LinkedIn session may expire or be challenged. |
| Keep `~/.linkedin-mcp` private and do not commit it. | It can contain authenticated browser-session data. |
| Do not export, paste, or transmit LinkedIn cookies/tokens. | The launcher retains them locally through the browser profile. |
| Use one LinkedIn account/profile per local MCP data directory. | This avoids ambiguous browser ownership and incorrect verification. |
| Do not expose the local HTTP endpoint publicly. | An unauthenticated remote MCP endpoint could expose account actions. |

## Troubleshooting

If `uvx` is missing, install uv from the official uv documentation and rerun setup. If browser import does not work, use the fresh local login command. If LinkedIn asks for a checkpoint, approval, or captcha, finish it only in the local login browser. If the MCP reports `login_required`, do not attempt Like or comment operations; restore the session first.
