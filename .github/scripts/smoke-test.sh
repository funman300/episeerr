#!/usr/bin/env bash
# Boot a built episeerr image and wait for its health endpoint to answer.
#
# Usage: smoke-test.sh <image-ref> [container-name]
# Env:   SMOKE_PORT (default 5002), SMOKE_TIMEOUT (default 60 seconds)
#
# The container starts with no config volume and no credentials, so this proves
# the image boots, imports cleanly and serves its health endpoint. It does not
# exercise any integration.
set -euo pipefail

IMAGE="${1:?usage: smoke-test.sh <image-ref> [container-name]}"
NAME="${2:-episeerr-smoke}"
PORT="${SMOKE_PORT:-5002}"
TIMEOUT="${SMOKE_TIMEOUT:-60}"
URL="http://localhost:${PORT}/api/series-stats"

cleanup() {
    docker rm -f "$NAME" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker run -d --name "$NAME" -p "${PORT}:5002" "$IMAGE" >/dev/null
echo "Started '${NAME}' from '${IMAGE}'; polling ${URL} for up to ${TIMEOUT}s"

elapsed=0
while [ "$elapsed" -lt "$TIMEOUT" ]; do
    if curl -fsS -o /dev/null "$URL"; then
        echo "OK: healthy after ${elapsed}s"
        exit 0
    fi
    if ! docker ps --format '{{.Names}}' | grep -qxF "$NAME"; then
        echo "::error::Container exited before becoming healthy"
        docker logs "$NAME" 2>&1 | tail -50
        exit 1
    fi
    sleep 3
    elapsed=$((elapsed + 3))
done

echo "::error::Timed out after ${TIMEOUT}s waiting for ${URL}"
docker logs "$NAME" 2>&1 | tail -50
exit 1
