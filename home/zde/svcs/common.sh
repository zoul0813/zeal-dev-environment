#!/bin/bash

set -euo pipefail

zde_init() {
  if [ -z "${ZDE_PATH:-}" ]; then
    ZDE_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
  fi

  COMPOSE_PATH="$ZDE_PATH/docker-compose.yml"
  CONTAINER_SERVICE="${CONTAINER_SERVICE:-zeal8bit-dev-env}"
  ZDE_USER_PATH="${ZDE_USER_PATH:-$HOME/.zeal8bit}"
  mkdir -p "$ZDE_USER_PATH"
  if [ ! -f "$ZDE_USER_PATH/deps.env" ]; then
    printf '# Managed by ZDE. Do not edit manually.\n' > "$ZDE_USER_PATH/deps.env"
  fi

  export ZDE_IMAGE="${ZDE_IMAGE:-zoul0813/zeal-dev-environment}"
  export ZDE_VERSION="${ZDE_VERSION:-latest}"

  if [ -n "${ZDE_USE:-}" ] && [ -z "${CONTAINER_CMD:-}" ]; then
    case "$ZDE_USE" in
      docker|podman)
        CONTAINER_CMD="$ZDE_USE"
        ;;
      *)
        echo "WARNING: Unsupported ZDE_USE value '$ZDE_USE' (expected: docker|podman); falling back to auto-detect"
        ;;
    esac
  fi

  if [ -z "${CONTAINER_CMD:-}" ]; then
    if command -v docker >/dev/null 2>&1; then
      CONTAINER_CMD=docker
    elif command -v podman >/dev/null 2>&1; then
      CONTAINER_CMD=podman
    else
      echo "WARNING: docker/podman not found, ensure docker or podman is installed before using ZDE"
      return 1
    fi
  fi

  if ! command -v "$CONTAINER_CMD" >/dev/null 2>&1; then
    echo "WARNING: Requested container runtime '$CONTAINER_CMD' not found"
    return 1
  fi

  HOST_UID="${HOST_UID:-$(id -u)}"
  HOST_GID="${HOST_GID:-$(id -g)}"
  HOST_HOME="${HOST_HOME:-$HOME}"
  if [ -t 1 ]; then
    ZDE_SOFT_EXIT="${ZDE_SOFT_EXIT:-1}"
  else
    ZDE_SOFT_EXIT="${ZDE_SOFT_EXIT:-0}"
  fi
  ZEAL_KERNEL_VERSION="${ZEAL_KERNEL_VERSION:-$(git -C "$ZDE_PATH/home/Zeal-8-bit-OS" describe --tags 2>/dev/null || true)}"
  ZDE_IMAGE_REF="${ZDE_IMAGE_REF:-${ZDE_IMAGE}:${ZDE_VERSION}}"
  LAUNCH_PWD="${LAUNCH_PWD:-$PWD}"
  HOST_CWD="${HOST_CWD:-$LAUNCH_PWD}"

  if [ "${#}" -gt 0 ]; then
    COMMAND="${1:-}"
    if [ "${#}" -gt 1 ]; then
      HOST_ARGS=("${@:2}")
    else
      HOST_ARGS=()
    fi
  else
    COMMAND=""
    HOST_ARGS=()
  fi

  export CONTAINER_CMD
  export ZDE_PATH
  export COMPOSE_PATH
  export CONTAINER_SERVICE
  export ZDE_USER_PATH
  export ZDE_IMAGE_REF
  export HOST_UID
  export HOST_GID
  export HOST_HOME
  export ZDE_SOFT_EXIT
  export ZEAL_KERNEL_VERSION
  export LAUNCH_PWD
  export HOST_CWD
}

zde_command() {
  CONTAINER_EXEC=(
    "$CONTAINER_CMD" compose -f "$COMPOSE_PATH" run -i --rm
    -e "HOST_UID=${HOST_UID}"
    -e "HOST_GID=${HOST_GID}"
    -e "HOST_HOME=${HOST_HOME}"
    -e "HOST_CWD=${HOST_CWD}"
    -e "ZDE_SOFT_EXIT=${ZDE_SOFT_EXIT}"
  )

  if [ -n "${ZEAL_KERNEL_VERSION:-}" ]; then
    CONTAINER_EXEC+=( -e "ZEAL_KERNEL_VERSION=${ZEAL_KERNEL_VERSION}" )
  fi
  for passthrough_var in \
    TERM \
    COLORTERM \
    TERM_PROGRAM \
    TERM_PROGRAM_VERSION \
    LC_TERMINAL \
    LC_TERMINAL_VERSION \
    ITERM_SESSION_ID \
    ITERM_PROFILE \
    ZDE_TUI_IMAGE_PROTOCOL; do
    if [ -n "${!passthrough_var-}" ]; then
      CONTAINER_EXEC+=( -e "${passthrough_var}=${!passthrough_var}" )
    fi
  done

  "${CONTAINER_EXEC[@]}" "$CONTAINER_SERVICE" /home/zeal8bit/zde/zde.py "$@"
}

zde_service_exists() {
  local service_name="$1"
  "$CONTAINER_CMD" compose -f "$COMPOSE_PATH" config --services 2>/dev/null | grep -xq "$service_name"
}

zde_shell() {
  local service_name="${1:-$CONTAINER_SERVICE}"
  if ! zde_service_exists "$service_name"; then
    if [ "$service_name" != "$CONTAINER_SERVICE" ]; then
      echo "Service '$service_name' not found in docker-compose.yml, falling back to '$CONTAINER_SERVICE'"
      service_name="$CONTAINER_SERVICE"
    fi
  fi

  CONTAINER_EXEC=(
    "$CONTAINER_CMD" compose -f "$COMPOSE_PATH" run -i --rm
    -e "HOST_UID=${HOST_UID}"
    -e "HOST_GID=${HOST_GID}"
    -e "HOST_HOME=${HOST_HOME}"
    -e "HOST_CWD=${HOST_CWD}"
    -e "ZDE_SOFT_EXIT=${ZDE_SOFT_EXIT}"
  )

  if [ -n "${ZEAL_KERNEL_VERSION:-}" ]; then
    CONTAINER_EXEC+=( -e "ZEAL_KERNEL_VERSION=${ZEAL_KERNEL_VERSION}" )
  fi
  for passthrough_var in \
    TERM \
    COLORTERM \
    TERM_PROGRAM \
    TERM_PROGRAM_VERSION \
    LC_TERMINAL \
    LC_TERMINAL_VERSION \
    ITERM_SESSION_ID \
    ITERM_PROFILE \
    ZDE_TUI_IMAGE_PROTOCOL; do
    if [ -n "${!passthrough_var-}" ]; then
      CONTAINER_EXEC+=( -e "${passthrough_var}=${!passthrough_var}" )
    fi
  done

  "${CONTAINER_EXEC[@]}" "$service_name" /bin/bash
}

container_running() {
  "$CONTAINER_CMD" ps --format '{{.Names}}' | grep -xq "$CONTAINER_NAME"
}

container_running_name() {
  local container_name="$1"
  "$CONTAINER_CMD" ps --format '{{.Names}}' | grep -xq "$container_name"
}

container_status_name() {
  local container_name="$1"
  if container_running_name "$container_name"; then
    echo "running"
  else
    echo "stopped"
  fi
}

container_status() {
  container_status_name "$CONTAINER_NAME"
}

container_exists() {
  "$CONTAINER_CMD" ps -a --format '{{.Names}}' | grep -xq "$CONTAINER_NAME"
}

start_container() {
  if container_running; then
    return 0
  fi

  if container_exists; then
    "$CONTAINER_CMD" rm -f "$CONTAINER_NAME" >/dev/null
  fi

  "$CONTAINER_CMD" run -d --name "$CONTAINER_NAME" \
    --platform linux/amd64 \
    -p "${SERVER_PORT}:${SERVER_PORT}" \
    -v "${LAUNCH_PWD}:/src" \
    -v "$ZDE_PATH/home:/home/zeal8bit" \
    "$ZDE_IMAGE_REF" \
    python3 -m http.server --directory "$SERVER_DIR" "$SERVER_PORT" >/dev/null
}

stop_container() {
  if container_exists; then
    "$CONTAINER_CMD" rm -f "$CONTAINER_NAME" >/dev/null
  fi
}

dep_installed() {
  local dep_id="$1"
  local lock_file="${ZDE_USER_PATH:-$HOME/.zeal8bit}/deps-lock.yml"
  if [ ! -f "$lock_file" ]; then
    return 1
  fi

  if command -v yq >/dev/null 2>&1; then
    local repo
    repo=$(yq -r ".dependencies.\"$dep_id\".repo // \"\"" "$lock_file" 2>/dev/null || true)
    [ -n "$repo" ] && [ "$repo" != "null" ]
    return $?
  fi

  local escaped
  escaped=$(printf '%s' "$dep_id" | sed 's/[.[\\*^$()+?{|]/\\&/g')
  grep -Eq "^[[:space:]]{2}${escaped}:" "$lock_file"
}

require_deps() {
  local missing=()
  local dep_id
  for dep_id in "$@"; do
    if ! dep_installed "$dep_id"; then
      missing+=("$dep_id")
    fi
  done

  if [ "${#missing[@]}" -eq 0 ]; then
    return 0
  fi

  echo "Missing required dependencies for this command:"
  for dep_id in "${missing[@]}"; do
    echo "  - $dep_id"
  done
  echo "Install with:"
  for dep_id in "${missing[@]}"; do
    echo "  zde deps install \"$dep_id\""
  done
  return 1
}
