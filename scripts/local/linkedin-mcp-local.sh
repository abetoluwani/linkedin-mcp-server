#!/usr/bin/env bash
# Local launcher for abetoluwani/linkedin-mcp-server.
# It never prints, exports, or uploads LinkedIn cookies or tokens.

set -euo pipefail

MCP_SOURCE_DEFAULT="https://github.com/abetoluwani/linkedin-mcp-server/archive/e8ea4f5e0fba3a3872052d6270d72032de9c2bb6.tar.gz"
MCP_SOURCE="${LINKEDIN_MCP_SOURCE:-$MCP_SOURCE_DEFAULT}"
PROFILE_ROOT="${LINKEDIN_MCP_PROFILE_ROOT:-$HOME/.linkedin-mcp}"
PROFILE_DIR="${LINKEDIN_MCP_PROFILE_DIR:-$PROFILE_ROOT/profile}"
HTTP_HOST="${LINKEDIN_MCP_HTTP_HOST:-127.0.0.1}"
HTTP_PORT="${LINKEDIN_MCP_HTTP_PORT:-8080}"

usage() {
  cat <<'EOF'
Usage: linkedin-mcp-local.sh <command> [browser]

Commands:
  setup                 Create the private local profile directory.
  import [browser]      Import a current LinkedIn session from a local browser.
  login                 Open a separate local LinkedIn login window.
  serve-stdio           Start the MCP over stdio for a local MCP client.
  serve-http            Start the MCP at http://127.0.0.1:8080/mcp by default.
  status                Check whether the saved MCP profile has a ready session.
  help                  Show this help.

Environment overrides:
  LINKEDIN_MCP_PROFILE_ROOT   Parent directory for local MCP data.
  LINKEDIN_MCP_PROFILE_DIR    Exact browser-profile directory.
  LINKEDIN_MCP_SOURCE         Immutable package source URL or package spec.
  LINKEDIN_MCP_HTTP_HOST      Loopback host for HTTP mode (default: 127.0.0.1).
  LINKEDIN_MCP_HTTP_PORT      HTTP mode port (default: 8080).

No command copies, displays, or sends LinkedIn cookies/tokens.
EOF
}

require_uvx() {
  if ! command -v uvx >/dev/null 2>&1; then
    cat >&2 <<'EOF'
uvx is required but was not found.
Install uv from https://docs.astral.sh/uv/ and rerun this command.
EOF
    exit 1
  fi
}

prepare_profile_root() {
  mkdir -p "$PROFILE_ROOT"
  chmod 700 "$PROFILE_ROOT"
}

run_server() {
  uvx --from "$MCP_SOURCE" mcp-server-linkedin --user-data-dir "$PROFILE_DIR" "$@"
}

command_name="${1:-help}"
case "$command_name" in
  setup)
    require_uvx
    prepare_profile_root
    printf 'Private MCP profile directory prepared at: %s\n' "$PROFILE_ROOT"
    printf 'Next: run "%s import" to reuse a local browser session, or "%s login" for a fresh MCP login.\n' "$0" "$0"
    ;;
  import)
    require_uvx
    prepare_profile_root
    shift
    run_server --import-from-browser "$@"
    ;;
  login)
    require_uvx
    prepare_profile_root
    run_server --login --no-headless
    ;;
  serve-stdio)
    require_uvx
    prepare_profile_root
    run_server --no-daemon --browser-idle-timeout 0
    ;;
  serve-http)
    require_uvx
    prepare_profile_root
    run_server --transport streamable-http --host "$HTTP_HOST" --port "$HTTP_PORT" --path /mcp --browser-idle-timeout 0
    ;;
  status)
    require_uvx
    prepare_profile_root
    run_server --status
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    printf 'Unknown command: %s\n\n' "$command_name" >&2
    usage >&2
    exit 2
    ;;
esac
