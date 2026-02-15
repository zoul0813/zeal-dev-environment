#!/bin/bash

set -euo pipefail

container_running() {
  "$CONTAINER_CMD" ps --format '{{.Names}}' | grep -xq "$CONTAINER_NAME"
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
