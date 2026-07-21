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

# Every source argument of every COPY line. Leading option words (--chown=,
# --from=, etc.) are skipped, and of the remaining arguments all but the last
# are sources (the last is the destination). A leading "./" is stripped from
# each source so "./app.py" and "app.py" compare equal. Commented-out lines
# (first field "#") are naturally excluded since their first field isn't
# "COPY". The JSON-array form ("COPY [\"app.py\", \".\"]") is not parsed by
# this loop; it is detected and rejected below.
copy_targets=()
while read -r -a fields || [ "${#fields[@]}" -gt 0 ]; do
    [ "${#fields[@]}" -eq 0 ] && continue
    [ "${fields[0]}" = "COPY" ] || continue

    args=()
    for ((i = 1; i < ${#fields[@]}; i++)); do
        case "${fields[$i]}" in
            --*) continue ;;
            *) args+=("${fields[$i]}") ;;
        esac
    done

    [ ${#args[@]} -eq 0 ] && continue

    case "${args[0]}" in
        \[*)
            echo "::error::COPY line uses the JSON-array form, which this check does not support:"
            echo "  ${fields[*]}"
            echo
            echo "Rewrite it as shell form (COPY src dest) or this check cannot verify Dockerfile coverage."
            exit 1
            ;;
    esac

    # All arguments except the last are sources; the last is the destination.
    for ((i = 0; i < ${#args[@]} - 1; i++)); do
        src="${args[$i]}"
        src="${src#./}"
        copy_targets+=("$src")
    done
done < Dockerfile

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
