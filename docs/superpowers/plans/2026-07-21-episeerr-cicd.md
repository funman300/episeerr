# episeerr CI/CD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gate every episeerr image on a build-and-boot check before it can reach `main` or GHCR, and keep the fork tracking upstream through reviewable PRs.

**Architecture:** Two small bash scripts under `.github/scripts/` hold all the logic; three workflows call them. `ci.yml` runs the checks on PRs and side branches without publishing anything. `docker-image.yml` runs the same smoke check on `main` and only pushes to GHCR once it passes. `sync-upstream.yml` proposes upstream merges as PRs, which then flow through `ci.yml`.

**Tech Stack:** GitHub Actions, bash, Docker Buildx, `docker/build-push-action@v6`, `gh` CLI (preinstalled on GitHub runners).

## Global Constraints

- Everything lives inside this repository as GitHub Actions workflows. Nothing is installed on, or executed against, any deployment host. No SSH, tunnels, or host agents.
- The existing GHCR tag scheme is preserved exactly: `latest`, `sha-<short>`, `b<run_number>`, `<VERSION>-b<run_number>`. Consumers pin immutable tags; a bad published build cannot be withdrawn, only superseded.
- Platform is `linux/amd64` only.
- `main` is built solely by `docker-image.yml`. `ci.yml` must never push an image.
- Allowlisted root module (deliberately not in the image): `get_plex_token.py`.
- Health endpoint used everywhere: `http://localhost:5002/api/series-stats` — the same one the image's own `HEALTHCHECK` uses.
- No new runtime dependencies in `requirements.txt` and no changes to application code.
- Work happens on branch `ci/pipeline`. Do not push to `main`.

## File Structure

| File | Responsibility |
| --- | --- |
| `.github/scripts/check-dockerfile-coverage.sh` (new) | Assert every root `*.py` is `COPY`ed into the image. Pure bash, no Docker. |
| `.github/scripts/smoke-test.sh` (new) | Boot an image, poll the health endpoint, dump logs and fail on timeout or early exit. |
| `.github/workflows/ci.yml` (new) | Run both scripts on PRs and non-`main` branches. Never publishes. |
| `.github/workflows/docker-image.yml` (modify) | Build → smoke test → push. Tag scheme unchanged. |
| `.github/workflows/sync-upstream.yml` (new) | Weekly upstream merge proposed as a PR; conflicts become an issue. |

---

### Task 1: Dockerfile module coverage check

The `Dockerfile` lists all sixteen root modules by name. A new module without a matching `COPY` produces an image that raises `ImportError` at runtime and passes every check that exists today. This script closes that gap and is the cheapest job in the pipeline.

**Files:**
- Create: `.github/scripts/check-dockerfile-coverage.sh`

**Interfaces:**
- Consumes: nothing.
- Produces: an executable script taking no arguments, run from anywhere (it `cd`s to the repo root itself). Exit 0 = all modules covered; exit 1 = at least one missing, names printed.

- [ ] **Step 1: Write the script**

```bash
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
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x .github/scripts/check-dockerfile-coverage.sh
```

- [ ] **Step 3: Run it against the current tree — expect PASS**

Run: `.github/scripts/check-dockerfile-coverage.sh`

Expected output (exit 0):
```
OK: 15 root module(s) COPYed into the image.
Allowlisted (not shipped): get_plex_token.py
```

If the count is not 15, stop and investigate before continuing — the repo has 16 root `.py` files and exactly one allowlisted.

- [ ] **Step 4: Prove it fails — add an uncopied module**

```bash
echo "# temporary CI probe" > zz_ci_probe.py
.github/scripts/check-dockerfile-coverage.sh; echo "exit=$?"
```

Expected (exit 1):
```
::error::Root modules missing from the Dockerfile COPY list:
  - zz_ci_probe.py
...
exit=1
```

- [ ] **Step 5: Prove the allowlist works**

```bash
sed -i 's/^ALLOWLIST=(get_plex_token.py)$/ALLOWLIST=(get_plex_token.py zz_ci_probe.py)/' .github/scripts/check-dockerfile-coverage.sh
.github/scripts/check-dockerfile-coverage.sh; echo "exit=$?"
```

Expected: exit 0, with `zz_ci_probe.py` listed as allowlisted.

- [ ] **Step 6: Clean up the probe**

```bash
rm zz_ci_probe.py
sed -i 's/^ALLOWLIST=(get_plex_token.py zz_ci_probe.py)$/ALLOWLIST=(get_plex_token.py)/' .github/scripts/check-dockerfile-coverage.sh
.github/scripts/check-dockerfile-coverage.sh
git diff --stat
```

Expected: the script passes again and `git diff --stat` shows no modification to the script beyond its creation.

- [ ] **Step 7: Commit**

```bash
git add .github/scripts/check-dockerfile-coverage.sh
git commit -m "ci: add Dockerfile module coverage check"
```

---

### Task 2: Image smoke test script

**Files:**
- Create: `.github/scripts/smoke-test.sh`

**Interfaces:**
- Consumes: nothing.
- Produces: `smoke-test.sh <image-ref> [container-name]`. Env overrides: `SMOKE_PORT` (default `5002`), `SMOKE_TIMEOUT` (default `60`, seconds). Exit 0 = healthy; exit 1 = timed out or container exited, with the last 50 log lines printed. Always removes the container on exit. Both `ci.yml` and `docker-image.yml` call this.

- [ ] **Step 1: Write the script**

```bash
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
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x .github/scripts/smoke-test.sh
```

- [ ] **Step 3: Build a stub `docker` so the script can be tested without a daemon**

There is no Docker on the development workstation. This stub exercises every branch of the script's control flow. It is scratch tooling in `/tmp` and is never committed.

```bash
mkdir -p /tmp/smoke-stub/bin /tmp/smoke-stub/www/api
echo '{"ok":true}' > /tmp/smoke-stub/www/api/series-stats

cat > /tmp/smoke-stub/bin/docker <<'STUB'
#!/usr/bin/env bash
# Minimal `docker` stand-in for testing smoke-test.sh without a daemon.
# Set STUB_EXITED=1 to simulate a container that died on startup.
case "$1" in
  run)  echo "stub-container-id" ;;
  ps)   [ "${STUB_EXITED:-0}" = "1" ] || echo "${STUB_NAME:-episeerr-smoke}" ;;
  logs) echo "stub log line 1"; echo "stub log line 2" ;;
  rm)   : ;;
  *)    echo "stub: unhandled args: $*" >&2; exit 2 ;;
esac
STUB
chmod +x /tmp/smoke-stub/bin/docker
```

- [ ] **Step 4: Test the healthy path — expect PASS**

```bash
python3 -m http.server 5099 --directory /tmp/smoke-stub/www >/dev/null 2>&1 &
echo $! > /tmp/smoke-stub/server.pid
sleep 1
PATH=/tmp/smoke-stub/bin:$PATH SMOKE_PORT=5099 SMOKE_TIMEOUT=12 STUB_NAME=probe \
  .github/scripts/smoke-test.sh fake:image probe; echo "exit=$?"
```

Expected:
```
Started 'probe' from 'fake:image'; polling http://localhost:5099/api/series-stats for up to 12s
OK: healthy after 0s
exit=0
```

- [ ] **Step 5: Test the timeout path — expect FAIL with logs**

```bash
kill "$(cat /tmp/smoke-stub/server.pid)"
sleep 1
PATH=/tmp/smoke-stub/bin:$PATH SMOKE_PORT=5099 SMOKE_TIMEOUT=6 STUB_NAME=probe \
  .github/scripts/smoke-test.sh fake:image probe; echo "exit=$?"
```

Expected: `::error::Timed out after 6s waiting for http://localhost:5099/api/series-stats`, then the two stub log lines, then `exit=1`. The whole run should take about 6 seconds.

- [ ] **Step 6: Test the container-exited-early path — expect FAIL fast**

```bash
PATH=/tmp/smoke-stub/bin:$PATH SMOKE_PORT=5099 SMOKE_TIMEOUT=60 STUB_NAME=probe STUB_EXITED=1 \
  .github/scripts/smoke-test.sh fake:image probe; echo "exit=$?"
```

Expected: `::error::Container exited before becoming healthy`, the two stub log lines, `exit=1`, and — importantly — it returns in under a second rather than waiting out the 60s timeout.

- [ ] **Step 7: Clean up the stub**

```bash
rm -rf /tmp/smoke-stub
```

- [ ] **Step 8: Commit**

```bash
git add .github/scripts/smoke-test.sh
git commit -m "ci: add image smoke test script"
```

---

### Task 3: CI workflow for PRs and side branches

**Files:**
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: `.github/scripts/check-dockerfile-coverage.sh` and `.github/scripts/smoke-test.sh` from Tasks 1 and 2.
- Produces: a workflow named `CI` with jobs `dockerfile-coverage` and `build-and-smoke`. Nothing downstream depends on it.

- [ ] **Step 1: Write the workflow**

```yaml
name: CI

# Verification for pull requests and side branches. Builds the image and boots
# it, but never publishes: pushes to main are handled by docker-image.yml, which
# is the only workflow allowed to write to GHCR.

on:
  pull_request:
    branches: [main]
  push:
    branches-ignore: [main]

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read

jobs:
  dockerfile-coverage:
    name: Dockerfile module coverage
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Check every root module is COPYed
        run: .github/scripts/check-dockerfile-coverage.sh

  build-and-smoke:
    name: Build image and smoke test
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build image (no push)
        uses: docker/build-push-action@v6
        with:
          context: .
          file: ./Dockerfile
          platforms: linux/amd64
          push: false
          load: true
          tags: episeerr:ci
          # Read-only cache: PR builds must not evict the main build's cache.
          cache-from: type=gha

      - name: Smoke test
        run: .github/scripts/smoke-test.sh episeerr:ci episeerr-ci
```

- [ ] **Step 2: Validate the YAML parses**

Run:
```bash
python3 -c "import yaml,sys; d=yaml.safe_load(open('.github/workflows/ci.yml')); print(sorted(d['jobs']))"
```
Expected: `['build-and-smoke', 'dockerfile-coverage']`

- [ ] **Step 3: Confirm the workflow cannot publish**

Run:
```bash
grep -nE "push: true|ghcr.io|docker/login-action|packages: write" .github/workflows/ci.yml; echo "exit=$?"
```
Expected: no matches, `exit=1`. If anything matches, the workflow can write to the registry and must be corrected.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: build and smoke test on PRs and side branches"
```

- [ ] **Step 5: Push the branch and confirm CI runs green**

```bash
git push -u origin ci/pipeline
```

Then watch the run for branch `ci/pipeline` in the repository's Actions tab. Expected: `CI` triggers (it is not `main`), `dockerfile-coverage` passes in seconds, `build-and-smoke` builds the image and prints `OK: healthy after Ns`.

Do not continue until this run is green — Tasks 4 and 5 both depend on `smoke-test.sh` working on a real runner.

- [ ] **Step 6: Prove the smoke test actually catches a broken image**

```bash
git checkout -b ci/pipeline-probe
printf '\nimport nonexistent_module_probe\n' >> episeerr.py
git commit -am "test: deliberate import error to verify CI catches it"
git push -u origin ci/pipeline-probe
```

Expected: `build-and-smoke` fails. The image builds fine (the error is at import time, not build time), the container exits immediately, and the step prints `::error::Container exited before becoming healthy` followed by a `ModuleNotFoundError: No module named 'nonexistent_module_probe'` traceback from the container logs.

This is the single most important verification in the plan: it proves the gate catches the exact failure mode this repo has.

- [ ] **Step 7: Delete the probe branch**

```bash
git checkout ci/pipeline
git branch -D ci/pipeline-probe
git push origin --delete ci/pipeline-probe
```

---

### Task 4: Gate the GHCR push on the smoke test

Today `docker-image.yml` builds and pushes in one step, so a broken image is published and tagged `latest` before anything notices. Because consumers pin immutable `sha-`/`b<n>` tags, a bad publish cannot be withdrawn. This task inserts the smoke test between building and pushing.

**Files:**
- Modify: `.github/workflows/docker-image.yml`

**Interfaces:**
- Consumes: `.github/scripts/smoke-test.sh` from Task 2.
- Produces: unchanged public behaviour — same triggers, same four tags, same job summary. Only the internal step order changes.

- [ ] **Step 1: Replace the file with the gated version**

The only changes from the current file are the header comment, the new "Build candidate image" and "Smoke test candidate" steps, and the rename of the final build step to "Push image". Everything else — triggers, `paths-ignore`, concurrency, permissions, `VERSION` reading, login, `metadata-action` tags, cache, summary — is byte-for-byte as it was.

```yaml
name: Build and push Docker image

# Builds the Episeerr image in GitHub's cloud and pushes it to the GitHub
# Container Registry (GHCR) so the host can `docker compose pull` instead of
# building locally. Runs on every push to main and on manual dispatch.
#
# The image is built and booted on the runner before anything is pushed.
# Consumers pin immutable sha-/b<n> tags, so a broken image that reaches GHCR
# cannot be withdrawn, only superseded — the gate has to come first.

on:
  push:
    branches: [main]
    paths-ignore:
      - '**.md'
      - 'runbook.md'
      - 'docs/**'
      - 'docker-compose.yml'   # deployment ref, does not affect the image
  workflow_dispatch: {}

concurrency:
  group: docker-${{ github.ref }}
  cancel-in-progress: true

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write        # push to ghcr.io/<owner>/<repo> with GITHUB_TOKEN
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Read VERSION
        id: ver
        run: echo "version=$(tr -d '[:space:]' < VERSION)" >> "$GITHUB_OUTPUT"

      - name: Set up Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Compute tags and labels
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ghcr.io/${{ github.repository }}
          tags: |
            type=raw,value=latest,enable={{is_default_branch}}
            type=sha,prefix=sha-,format=short
            type=raw,value=b${{ github.run_number }}
            type=raw,value=${{ steps.ver.outputs.version }}-b${{ github.run_number }}

      - name: Build candidate image (no push)
        uses: docker/build-push-action@v6
        with:
          context: .
          file: ./Dockerfile
          platforms: linux/amd64
          push: false
          load: true
          tags: episeerr:candidate
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Smoke test candidate
        run: .github/scripts/smoke-test.sh episeerr:candidate episeerr-candidate

      - name: Build and push
        uses: docker/build-push-action@v6
        with:
          context: .
          file: ./Dockerfile
          platforms: linux/amd64
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Summary
        run: |
          {
            echo "### Image pushed to GHCR"
            echo ""
            echo "Pinnable tags for this build:"
            echo '```'
            echo "${{ steps.meta.outputs.tags }}"
            echo '```'
            echo "Pull on the host with:"
            echo '```'
            echo "docker compose pull && docker compose up -d"
            echo '```'
          } >> "$GITHUB_STEP_SUMMARY"
```

- [ ] **Step 2: Verify the tag scheme is untouched**

Run:
```bash
git diff .github/workflows/docker-image.yml | grep -E '^[-+].*type=(raw|sha)' ; echo "exit=$?"
```
Expected: no output, `exit=1`. Any diff on a `type=raw` or `type=sha` line means the tag scheme changed, which Global Constraints forbid.

The pattern is scoped to `type=(raw|sha)` deliberately: a bare `type=` also matches the `cache-from: type=gha` and `cache-to: type=gha,mode=max` lines that this task legitimately adds to the new candidate-build step, which would make the check fail on a correct implementation.

- [ ] **Step 3: Verify the smoke test precedes the push**

Run:
```bash
python3 - <<'PY'
import yaml
steps = yaml.safe_load(open('.github/workflows/docker-image.yml'))['jobs']['build']['steps']
names = [s.get('name') for s in steps]
smoke = names.index('Smoke test candidate')
push  = names.index('Build and push')
print(f"smoke at {smoke}, push at {push}")
assert smoke < push, "smoke test must run before the push"
print("OK")
PY
```
Expected: `smoke at 6, push at 7` then `OK`. (Step indices are 0-based; the preceding steps are Checkout, Read VERSION, Set up Buildx, Log in to GHCR, Compute tags and labels, Build candidate image.)

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/docker-image.yml
git commit -m "ci: smoke test the image before pushing to GHCR"
```

Note: this workflow only runs on `main`, so it cannot be verified from the branch. It is verified in Task 6 when the branch merges.

---

### Task 5: Upstream sync workflow

**Files:**
- Create: `.github/workflows/sync-upstream.yml`

**Interfaces:**
- Consumes: nothing from earlier tasks. Its PRs are verified by `ci.yml` from Task 3.
- Produces: a weekly workflow named `Sync Upstream`. Emits either a PR from branch `upstream-sync/<short-sha>`, or an issue, or nothing.

- [ ] **Step 1: Write the workflow**

```yaml
name: Sync Upstream

# Weekly check for new commits on Vansmak/episeerr. A clean merge becomes a pull
# request; a conflicting merge becomes an issue. Never merges to main
# automatically — this fork carries real behavioural divergence (multi_source.py,
# cross-source dedup, per-series source affinity, see FORK.md) that must not be
# resolved unattended.

on:
  schedule:
    - cron: '0 6 * * 1'   # Mondays 06:00 UTC
  workflow_dispatch: {}

permissions:
  contents: write
  pull-requests: write
  issues: write

concurrency:
  group: sync-upstream
  cancel-in-progress: false

env:
  UPSTREAM_URL: https://github.com/Vansmak/episeerr.git
  UPSTREAM_REF: upstream/main

jobs:
  sync:
    name: Propose upstream merge
    runs-on: ubuntu-latest
    steps:
      - name: Checkout fork
        uses: actions/checkout@v4
        with:
          fetch-depth: 0
          # GITHUB_TOKEN is hard-blocked from pushing changes under
          # .github/workflows/. When an upstream sync touches CI files,
          # WORKFLOW_PUSH_TOKEN (a PAT with contents + workflows write) is
          # required; without it the push fails and an issue is opened.
          token: ${{ secrets.WORKFLOW_PUSH_TOKEN || github.token }}

      - name: Configure git identity
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"

      - name: Fetch upstream
        run: |
          git remote add upstream "$UPSTREAM_URL"
          git fetch --no-tags upstream main

      - name: Decide whether a sync is needed
        id: check
        run: |
          SHA="$(git rev-parse --short "$UPSTREAM_REF")"
          BRANCH="upstream-sync/${SHA}"
          echo "sha=$SHA"       >> "$GITHUB_OUTPUT"
          echo "branch=$BRANCH" >> "$GITHUB_OUTPUT"

          if git merge-base --is-ancestor "$UPSTREAM_REF" HEAD; then
            echo "needed=false" >> "$GITHUB_OUTPUT"
            echo "Already up to date with upstream/main ($SHA)."
          elif git ls-remote --exit-code --heads origin "$BRANCH" >/dev/null 2>&1; then
            echo "needed=false" >> "$GITHUB_OUTPUT"
            echo "Branch $BRANCH already exists; nothing to do."
          else
            echo "needed=true" >> "$GITHUB_OUTPUT"
            echo "Sync needed up to upstream $SHA."
          fi

      - name: Merge upstream onto a sync branch
        id: merge
        if: steps.check.outputs.needed == 'true'
        run: |
          git checkout -b "${{ steps.check.outputs.branch }}"
          git log --oneline --no-decorate "HEAD..${UPSTREAM_REF}" > /tmp/commits.txt
          if git merge "$UPSTREAM_REF" --no-edit; then
            echo "clean=true" >> "$GITHUB_OUTPUT"
          else
            echo "clean=false" >> "$GITHUB_OUTPUT"
            git diff --name-only --diff-filter=U > /tmp/conflicts.txt
            git merge --abort
          fi

      - name: Push branch and open pull request
        id: push
        if: steps.merge.outputs.clean == 'true'
        env:
          GH_TOKEN: ${{ secrets.WORKFLOW_PUSH_TOKEN || github.token }}
        run: |
          BRANCH="${{ steps.check.outputs.branch }}"
          if ! git push origin "$BRANCH"; then
            echo "push_failed=true" >> "$GITHUB_OUTPUT"
            echo "Push rejected — see the follow-up step."
            exit 0
          fi
          {
            echo "Automated sync of upstream \`Vansmak/episeerr\` up to \`${{ steps.check.outputs.sha }}\`."
            echo
            echo "Merged cleanly. CI on this PR must pass before merging."
            echo
            echo "### Upstream commits included"
            echo '```'
            cat /tmp/commits.txt
            echo '```'
          } > /tmp/pr-body.md
          gh pr create \
            --base main \
            --head "$BRANCH" \
            --title "Sync upstream Vansmak/episeerr @ ${{ steps.check.outputs.sha }}" \
            --body-file /tmp/pr-body.md

      - name: Open issue when the push needs a PAT
        if: steps.push.outputs.push_failed == 'true'
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          {
            echo "The upstream sync up to \`${{ steps.check.outputs.sha }}\` merged cleanly but could not be pushed."
            echo
            echo "This almost always means the merge touches files under \`.github/workflows/\`,"
            echo "which \`GITHUB_TOKEN\` is not permitted to write. Configure a repository secret"
            echo "named \`WORKFLOW_PUSH_TOKEN\` — a PAT with \`contents: write\` and"
            echo "\`workflows: write\` on this repository — and re-run the workflow."
            echo
            echo "Failed run: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
          } > /tmp/issue-body.md
          gh issue create \
            --title "Upstream sync blocked @ ${{ steps.check.outputs.sha }}" \
            --body-file /tmp/issue-body.md

      - name: Open issue on merge conflict
        if: steps.merge.outputs.clean == 'false'
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          {
            echo "Merging upstream \`Vansmak/episeerr\` @ \`${{ steps.check.outputs.sha }}\` into \`main\` conflicts."
            echo
            echo "### Conflicting paths"
            echo '```'
            cat /tmp/conflicts.txt
            echo '```'
            echo
            echo "Resolve locally:"
            echo
            echo '```bash'
            echo "git fetch https://github.com/Vansmak/episeerr.git main"
            echo "git checkout -b ${{ steps.check.outputs.branch }} main"
            echo "git merge FETCH_HEAD"
            echo '```'
            echo
            echo "Failed run: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
          } > /tmp/issue-body.md
          gh issue create \
            --title "Upstream sync conflict @ ${{ steps.check.outputs.sha }}" \
            --body-file /tmp/issue-body.md
```

- [ ] **Step 2: Validate the YAML parses and the guards are consistent**

Run:
```bash
python3 - <<'PY'
import yaml
w = yaml.safe_load(open('.github/workflows/sync-upstream.yml'))
steps = w['jobs']['sync']['steps']
for s in steps:
    if 'if' in s:
        print(f"{s['name']!r:52} if: {s['if']}")
PY
```
Expected exactly:
```
'Merge upstream onto a sync branch'                  if: steps.check.outputs.needed == 'true'
'Push branch and open pull request'                  if: steps.merge.outputs.clean == 'true'
'Open issue when the push needs a PAT'               if: steps.push.outputs.push_failed == 'true'
'Open issue on merge conflict'                       if: steps.merge.outputs.clean == 'false'
```

When the merge step is skipped, `steps.merge.outputs.clean` is empty, so neither the push nor the conflict step fires. That is the intended "nothing to do" path.

- [ ] **Step 3: Commit and push**

```bash
git add .github/workflows/sync-upstream.yml
git commit -m "ci: propose upstream syncs as reviewable pull requests"
git push
```

- [ ] **Step 4: Dispatch it and confirm behaviour**

The workflow must exist on the default branch before it can be dispatched, so this step happens after Task 6 merges. Record it as a post-merge action:

From the Actions tab, run `Sync Upstream` manually. Expected: either the log ends with `Already up to date with upstream/main (<sha>).`, or a PR titled `Sync upstream Vansmak/episeerr @ <sha>` appears with CI running on it, or an issue titled `Upstream sync conflict @ <sha>` appears listing conflicting paths. All three are correct outcomes; which one occurs depends on upstream's state.

- [ ] **Step 5: Confirm it is idempotent**

Dispatch `Sync Upstream` a second time. Expected: the log ends with either `Already up to date` or `Branch upstream-sync/<sha> already exists; nothing to do.` — and no second PR or issue is created.

---

### Task 6: Merge and verify on `main`

**Files:**
- No file changes. This task verifies Task 4, which only runs on `main`.

**Interfaces:**
- Consumes: everything from Tasks 1–5.
- Produces: a verified pipeline on the default branch.

- [ ] **Step 1: Confirm the branch is green**

```bash
git status --short
git log --oneline main..ci/pipeline
```
Expected: a clean tree and five commits — coverage check, smoke script, CI workflow, docker-image gating, sync workflow. Confirm the latest `CI` run on `ci/pipeline` is green before merging.

- [ ] **Step 2: Open the pull request**

```bash
gh pr create --base main --head ci/pipeline \
  --title "Add CI: build gating, smoke tests and upstream sync" \
  --body "Implements docs/superpowers/specs/2026-07-21-episeerr-cicd-design.md"
```

If `gh` is not authenticated on this machine, open the PR through the web UI instead.

- [ ] **Step 3: Merge once CI passes**

Merge the PR. This triggers `docker-image.yml` on `main`.

- [ ] **Step 4: Verify the gated publish**

Open the `Build and push Docker image` run for the merge commit. Confirm, in order:

1. `Build candidate image (no push)` succeeds.
2. `Smoke test candidate` prints `OK: healthy after Ns`.
3. `Build and push` succeeds and is largely a cache hit (it should take seconds, not minutes).
4. The job summary lists all four tags: `latest`, `sha-<short>`, `b<n>`, `<VERSION>-b<n>`.

- [ ] **Step 5: Confirm the published tags exist**

```bash
curl -s "https://ghcr.io/token?scope=repository:funman300/episeerr:pull" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])' > /tmp/ghcr-token
curl -s -H "Authorization: Bearer $(cat /tmp/ghcr-token)" \
  https://ghcr.io/v2/funman300/episeerr/tags/list \
  | python3 -c 'import json,sys; t=json.load(sys.stdin)["tags"]; print(len(t), "tags"); print([x for x in t if x.startswith(("b","sha-"))][-6:])'
rm /tmp/ghcr-token
```
Expected: the new `b<n>` and `sha-<short>` tags for this run are present.

---

## Post-implementation notes

- `Sync Upstream` runs Mondays at 06:00 UTC. Its first scheduled run is the real
  test of the schedule trigger; the dispatch in Task 5 only proves the logic.
- If `build-and-smoke` starts failing on timeout rather than on a real error,
  raise `SMOKE_TIMEOUT` in the workflow call rather than deleting the gate.
- The deliberate-import-error probe in Task 3 Step 6 is worth repeating any time
  the smoke script changes; it is the only test that proves the gate works
  end to end on a real runner.
