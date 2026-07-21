# episeerr CI/CD design

**Date:** 2026-07-21
**Repo:** `funman300/episeerr` (fork of `Vansmak/episeerr`)
**Status:** approved, pending implementation

## Context

This fork is a Python/Flask app shipped as a single container image. Today CI
consists of one workflow, `.github/workflows/docker-image.yml`, which builds on
every push to `main` and pushes to GHCR tagged `latest`, `sha-<short>`, `b<run>`
and `<VERSION>-b<run>`.

Two gaps motivate this work:

1. **Nothing runs on pull requests or side branches.** The repo carries seven
   branches (`main`, `dev`, `custom`, `extras`, `lite`, `multi-source-support`,
   `episeerr-backup`). Breakage is only discovered after it has landed on `main`
   and been tagged `latest` in GHCR.
2. **`Dockerfile` copies each root module by name.** Sixteen root `*.py` files are
   listed individually. Adding a module to the fork without adding a matching
   `COPY` produces an image that fails at import time at runtime and passes every
   existing check. Only `get_plex_token.py` is intentionally excluded (it is a
   standalone operator helper, not part of the app).

### Scope boundary

**Everything in this spec is a GitHub Actions workflow inside this repository.**
Nothing is installed on, or executed against, any deployment host.

The pipeline ends at the GHCR push. Consumers pull the published image
themselves; how and when they do that is outside this design. The one fact about
consumption that matters here is that at least one consumer pins an immutable
`sha-`/`b<n>` tag rather than tracking `latest`, so the existing tag scheme must
be preserved exactly, and a bad build must never be published under those tags in
the first place — there is no post-publish correction path.

## Goals

- Catch broken builds before they reach GHCR or `main`.
- Catch modules missing from the image.
- Keep the fork mergeable with upstream without silent drift.

## Non-goals

- **Deployment automation of any kind.** No host-side scripts, agents, timers,
  SSH from Actions, or tunnels. Deploying the published image stays a manual
  operator action, unchanged by this work.
- A Python test suite. The project has no tests and writing them is separate work.
- Linting, `pip-audit`, Trivy, Dependabot. Considered and deliberately deferred.
- Multi-arch images. The only consumer platform is x86_64.

## Design

### 1. `.github/workflows/ci.yml` (new)

Triggers: `pull_request` targeting `main`, and `push` to any branch except `main`
(`main` is covered by `docker-image.yml`). Concurrency group per ref with
`cancel-in-progress: true`.

**Job `dockerfile-coverage`** — no Docker build, runs in seconds:

- For every `*.py` at the repo root, assert a `COPY <file>` line exists in
  `Dockerfile`.
- Allowlist: `get_plex_token.py`.
- On failure, print each missing module and exit non-zero.

Directory copies (`integrations/`, `templates/`, `static/`) are wholesale `COPY`
statements and need no per-file check.

**Job `build-and-smoke`**:

- `docker/setup-buildx-action@v3`.
- `docker/build-push-action@v6` with `push: false`, `load: true`, `tags:
  episeerr:ci`, `cache-from: type=gha`. Cache is read-only here
  (no `cache-to`) so PR builds cannot evict the `main` build cache.
- `docker run -d --name episeerr-ci -p 5002:5002 episeerr:ci`.
- Poll `http://localhost:5002/api/series-stats` every 3s for up to 60s. This is
  the same endpoint the image's own `HEALTHCHECK` uses.
- On failure or timeout: `docker logs episeerr-ci` into the step output, then
  exit non-zero.
- Always `docker rm -f episeerr-ci` in an `if: always()` step.

The two jobs run in parallel; `dockerfile-coverage` fails fast and cheaply.

### 2. `.github/workflows/docker-image.yml` (modified)

One structural change: build, load, smoke-test, then push — so an image that
cannot serve `/api/series-stats` never reaches GHCR and never becomes `latest`.
This matters more than it would elsewhere because consumers pin immutable tags:
a bad build that gets published cannot be un-published, only superseded.

- Split the existing `docker/build-push-action` step into two invocations sharing
  the same Buildx builder and gha cache: first with `push: false, load: true,
  tags: episeerr:candidate`, then, after the smoke test passes, the existing step
  with `push: true` and the full `docker/metadata-action` tag set. The second
  build is a cache hit, so the cost is the smoke test only (~15s).
- The smoke-test step is identical to `ci.yml`'s and is extracted to
  `.github/scripts/smoke-test.sh` so both workflows call one implementation.
- Existing triggers, `paths-ignore`, tag scheme, permissions and job summary are
  unchanged.

### 3. `.github/workflows/sync-upstream.yml` (new)

Triggers: `schedule` weekly (Mondays 06:00 UTC) and `workflow_dispatch`.

- Checkout with `fetch-depth: 0`.
- Add `https://github.com/Vansmak/episeerr.git` as remote `upstream`, fetch.
- If `upstream/main` is already an ancestor of `main`, log "up to date" and exit 0.
- Create branch `upstream-sync/<upstream-short-sha>`. If a branch for that SHA
  already exists, exit 0 — the job is idempotent and will not spam.
- Attempt `git merge upstream/main --no-edit`.
  - **Clean:** push the branch and open a PR against `main` titled
    `Sync upstream Vansmak/episeerr @ <short-sha>`, body listing the upstream
    commits included (`git log --oneline main..upstream/main`).
  - **Conflict:** `git merge --abort`, then open an issue titled
    `Upstream sync conflict @ <short-sha>` listing the conflicting paths from
    `git diff --name-only --diff-filter=U`. Do not push a broken branch.

Never merges to `main` automatically. This fork carries real behavioural
divergence — `multi_source.py`, cross-source dedup, per-series source affinity —
documented in `FORK.md`, and those changes must not be resolved unattended.

Token: the checkout uses `secrets.WORKFLOW_PUSH_TOKEN` when that secret exists and
falls back to `github.token`. GitHub blocks `GITHUB_TOKEN` from pushing changes
under `.github/workflows/`, so when an upstream sync touches workflow files and no
PAT is configured, the push fails; the workflow catches that and opens an issue
explaining that a PAT is required, rather than failing silently. This mirrors the
arrangement already documented in the `AndroidAPS-old-fork` sync workflow.

Opening the PR exercises `ci.yml`, so upstream syncs are build-tested before merge.

## Testing

All verification happens in GitHub Actions on a scratch branch, plus what can be
run locally with bash alone.

- `check-dockerfile-coverage.sh`: run locally against the current tree (expect
  pass, `get_plex_token.py` allowlisted); then add a throwaway root module and
  re-run (expect failure naming it); then delete it.
- `smoke-test.sh`: exercised locally against a stubbed `docker` on `PATH` plus a
  `python3 -m http.server` standing in for the app, covering the healthy path,
  the timeout path, and the container-exited-early path. No Docker required.
- `ci.yml`: verified by pushing a scratch branch with a deliberate import error
  and confirming `build-and-smoke` fails with the traceback in the logs output;
  and a second scratch branch adding an uncopied root module, confirming
  `dockerfile-coverage` fails naming it.
- `docker-image.yml`: verified by confirming a normal `main` build still publishes
  the full tag set, and that the smoke step sits before the push step in the run.
- `sync-upstream.yml`: first run via `workflow_dispatch` against current upstream,
  checking that either a PR opens or the "up to date" path is taken; the conflict
  path is checked by dispatching from a scratch branch carrying a conflicting edit.

## Risks

- **Smoke test flakiness.** If the app takes longer than 60s to serve
  `/api/series-stats` on a cold container in a GitHub runner, CI fails
  spuriously. If the window proves tight, raise it rather than removing the gate.
- **Smoke test starts the app with no configuration.** It runs with no `/app/config`
  volume and no Sonarr/Plex credentials, so it proves the image boots, imports
  cleanly and serves its health endpoint — not that integrations work. That is the
  intended depth: it catches the failure mode this repo actually has (a module
  missing from the image, or an import error), not integration regressions.
- **Upstream sync PRs may pile up.** One branch per upstream SHA, deduped, so
  they cannot duplicate — but an unattended repo will accumulate open PRs. They
  are cheap to close.
