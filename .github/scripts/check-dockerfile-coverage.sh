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

# First argument of every COPY line, matched by awk field position so leading
# whitespace is tolerated and commented-out lines (first field "#") are
# naturally excluded.
copy_targets=()
while IFS= read -r target; do
    copy_targets+=("$target")
done < <(awk '$1 == "COPY" { print $2 }' Dockerfile)

missing=()
checked=0
for f in *.py; do
    if printf '%s\n' "${ALLOWLIST[@]}" | grep -qxF "$f"; then
        continue
    fi
    checked=$((checked + 1))
    if ! printf '%s\n' "${copy_targets[@]}" | grep -qxF "$f"; then
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
