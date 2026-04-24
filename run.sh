#!/usr/bin/env bash
# Azure AI Agent Quickstart — one-shot launcher.
#
#   1. Ensures .env exists (copied from .env.example on first run).
#   2. Reads LLM_PROVIDER, then validates only the vars that
#      provider requires.
#   3. Reports which OTHER providers are also configured and which
#      optional integrations are active.
#   4. docker compose up --build -d, waits for /healthz, prints URLs.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

BOLD=$'\033[1m'
DIM=$'\033[2m'
RED=$'\033[31m'
GREEN=$'\033[32m'
YELLOW=$'\033[33m'
RESET=$'\033[0m'

if [[ ! -f "$SCRIPT_DIR/.env.example" ]]; then
  echo "${RED}Missing .env.example — are you in the repo root?${RESET}" >&2
  exit 1
fi

# --- First-run: copy .env.example -> .env and stop. ---
if [[ ! -f "$SCRIPT_DIR/.env" ]]; then
  cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
  echo "${GREEN}Created .env from .env.example.${RESET}"
  echo
  echo "Next steps:"
  echo "  1. Open .env in VS Code (or any editor)."
  echo "  2. Pick an LLM_PROVIDER (azure | openai | anthropic) and fill in"
  echo "     just that provider's block."
  echo "  3. Re-run ./run.sh"
  exit 0
fi

# --- Helpers. ---
env_get() {
  local key="$1"
  local line
  line="$(grep -E "^[[:space:]]*${key}=" "$SCRIPT_DIR/.env" | tail -n1 || true)"
  [[ -z "$line" ]] && { echo ""; return; }
  local val="${line#*=}"
  val="${val#"${val%%[![:space:]]*}"}"
  val="${val%"${val##*[![:space:]]}"}"
  val="${val%\"}"; val="${val#\"}"
  val="${val%\'}"; val="${val#\'}"
  echo "$val"
}

is_placeholder() {
  local v="$1"
  [[ -z "$v" ]] && return 0
  local lower
  lower="$(printf '%s' "$v" | tr '[:upper:]' '[:lower:]')"
  case "$lower" in
    changeme|your-key-here|todo|xxx) return 0 ;;
    *) return 1 ;;
  esac
}

display_var() {
  local k="$1" v="$2"
  case "$k" in
    *KEY*|*SECRET*) printf '%s...(redacted)' "$(printf '%s' "$v" | head -c 6)" ;;
    *) printf '%s' "$v" ;;
  esac
}

provider_configured() {
  # Returns 0 if the given provider has all its required vars set.
  local p="$1"
  case "$p" in
    azure)
      ! is_placeholder "$(env_get AZURE_OPENAI_ENDPOINT)" \
        && ! is_placeholder "$(env_get AZURE_OPENAI_API_KEY)"
      ;;
    openai)
      ! is_placeholder "$(env_get OPENAI_API_KEY)"
      ;;
    anthropic)
      ! is_placeholder "$(env_get ANTHROPIC_API_KEY)"
      ;;
    *) return 1 ;;
  esac
}

echo "${BOLD}Azure AI Agent Quickstart${RESET}"

# --- Determine provider + its required vars. ---
PROVIDER="$(env_get LLM_PROVIDER)"
PROVIDER="${PROVIDER:-azure}"
case "$PROVIDER" in
  azure|openai|anthropic) ;;
  *)
    echo "${RED}LLM_PROVIDER=$PROVIDER is not recognized. Use azure, openai, or anthropic.${RESET}"
    exit 1
    ;;
esac

case "$PROVIDER" in
  azure)
    REQUIRED=(AZURE_OPENAI_ENDPOINT AZURE_OPENAI_API_KEY AZURE_OPENAI_DEPLOYMENT AZURE_OPENAI_API_VERSION)
    ;;
  openai)
    REQUIRED=(OPENAI_API_KEY OPENAI_MODEL)
    ;;
  anthropic)
    REQUIRED=(ANTHROPIC_API_KEY ANTHROPIC_MODEL)
    ;;
esac

echo "${DIM}Validating .env for LLM_PROVIDER=${PROVIDER}...${RESET}"
all_ok=1
for k in "${REQUIRED[@]}"; do
  v="$(env_get "$k")"
  if is_placeholder "$v"; then
    echo "  ${RED}x${RESET} $k is missing"
    all_ok=0
  else
    echo "  ${GREEN}OK${RESET} $k = $(display_var "$k" "$v")"
  fi
done

if [[ "$all_ok" -ne 1 ]]; then
  echo
  echo "${RED}.env is missing required values for provider '${PROVIDER}'. Edit .env and re-run ./run.sh${RESET}"
  exit 1
fi

# --- Report OTHER providers. ---
echo
echo "${BOLD}Other providers:${RESET}"
for p in azure openai anthropic; do
  [[ "$p" == "$PROVIDER" ]] && continue
  if provider_configured "$p"; then
    echo "  ${GREEN}on${RESET}  $p (also configured — can switch via LLM_PROVIDER=$p)"
  else
    echo "  ${YELLOW}off${RESET} $p (not configured)"
  fi
done

# --- Optional integrations. ---
search_active=1
for k in AZURE_AI_SEARCH_ENDPOINT AZURE_AI_SEARCH_KEY AZURE_AI_SEARCH_INDEX; do
  v="$(env_get "$k")"
  if is_placeholder "$v"; then search_active=0; fi
done
ai_active=1
v="$(env_get APPLICATIONINSIGHTS_CONNECTION_STRING)"
if is_placeholder "$v"; then ai_active=0; fi

tavily_active=1
v="$(env_get TAVILY_API_KEY)"
if is_placeholder "$v"; then tavily_active=0; fi

echo
echo "${BOLD}Detected optional integrations:${RESET}"
if [[ "$search_active" -eq 1 ]]; then
  echo "  ${GREEN}on${RESET}  Azure AI Search (research agent will use your index)"
else
  echo "  ${YELLOW}off${RESET} Azure AI Search — research agent falls back to local FTS5"
fi
if [[ "$ai_active" -eq 1 ]]; then
  echo "  ${GREEN}on${RESET}  Application Insights (cloud traces enabled)"
else
  echo "  ${YELLOW}off${RESET} Application Insights — traces limited to in-memory + SQLite"
fi
if [[ "$tavily_active" -eq 1 ]]; then
  echo "  ${GREEN}on${RESET}  Tavily web search (UI toggle in header will be enabled)"
else
  echo "  ${YELLOW}off${RESET} Tavily web search — UI toggle will be disabled"
fi

# --- Start compose. ---
if ! command -v docker >/dev/null 2>&1; then
  echo "${RED}Docker is not installed or not on PATH. Install Docker Desktop and try again.${RESET}"
  exit 1
fi

echo
echo "${DIM}docker compose up --build -d...${RESET}"
docker compose up --build -d

# --- Wait for /healthz. ---
echo -n "Waiting for api to be healthy"
for i in $(seq 1 30); do
  if curl -fsS http://localhost:8000/healthz >/dev/null 2>&1; then
    echo " ${GREEN}ok${RESET}"
    break
  fi
  echo -n "."
  sleep 2
done

if ! curl -fsS http://localhost:8000/healthz >/dev/null 2>&1; then
  echo
  echo "${RED}api did not become healthy. Check: docker compose logs api${RESET}"
  exit 1
fi

echo
echo "${BOLD}Ready.${RESET}"
echo "  API:  http://localhost:8000/docs"
echo "  UI:   http://localhost:5173"
echo
echo "${DIM}Stop with: docker compose down${RESET}"
