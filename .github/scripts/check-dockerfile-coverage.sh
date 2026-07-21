#!/usr/bin/env bash
# Fail if a root-level Python module is not COPYed into the image.
#
# The Dockerfile lists every application module by name, so adding a module to
# the fork without a matching COPY line produces an image that raises
# ImportError at runtime while passing every other check.
set -euo pipefail

cd "$(dirname "$0")/../.."

# Root modules that are deliberately not part of the image.
ALLOWLIST=(get_plex_token.py)

missing=()
checked=0
for f in *.py; do
    if printf '%s\n' "${ALLOWLIST[@]}" | grep -qxF "$f"; then
        continue
    fi
    checked=$((checked + 1))
    if ! grep -qE "^COPY[[:space:]]+${f}([[:space:]]|\$)" Dockerfile; then
        missing+=("$f")
    fi
done

if [ ${#missing[@]} -gt 0 ]; then
    echo "::error::Root modules missing from the Dockerfile COPY list:"
    printf '  - %s\n' "${missing[@]}"
    echo
    echo "Add 'COPY <module> .' to Dockerfile, or add the file to ALLOWLIST in"
    echo ".github/scripts/check-dockerfile-coverage.sh if it should not ship."
    exit 1
fi

echo "OK: ${checked} root module(s) COPYed into the image."
echo "Allowlisted (not shipped): ${ALLOWLIST[*]}"
