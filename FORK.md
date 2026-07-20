# Fork notes: funman300/episeerr

This is a fork of [Vansmak/episeerr](https://github.com/Vansmak/episeerr)
(based on upstream v3.7.17). Everything in the main [README](README.md)
still applies. This file documents only what this fork adds on top, and how
its prebuilt image is published and deployed.

All the added behavior is **off by default**, so the fork behaves exactly
like upstream until you opt in on the Scheduler / Global Settings page.

---

## Extra features

### 1. Multi-source coordination (Plex and Jellyfin at the same time)

Upstream expects a single watch-event source; sending events from two media
servers can cause double downloads. This fork lets more than one server
drive automation safely, so (for example) a Plex household and a Jellyfin
household can share one library.

Two mechanisms, both in `multi_source.py`, gated behind
`multi_source_enabled`:

- **Cross-source dedup** – the same series/season/episode reported again
  within `multi_source_dedup_minutes` (default 360) is processed once. This
  also covers the classic Plex-native + Tautulli double-report.
- **Per-series source affinity** – each series is pinned to the first source
  that reports it. Other sources still refresh activity timers (so Grace and
  Dormant stay accurate) but cannot move the episode window, preventing two
  viewers at different points in a show from fighting. A pin whose source
  goes silent for `multi_source_pin_ttl_days` (default 30, 0 = never) is
  taken over by the next source to report the series.

Global settings:

| Key | Default | Meaning |
| --- | --- | --- |
| `multi_source_enabled` | `false` | Master switch for this feature |
| `multi_source_affinity` | `true` | Pin each series to its first source |
| `multi_source_dedup_minutes` | `360` | Duplicate-event window (0 disables) |
| `multi_source_pin_ttl_days` | `30` | Silence before a pin can be taken over (0 = never) |

Inspect / override pins:

```bash
# View current pins and recent events
curl http://your-server:5002/api/multi-source/state

# Pin a series to a source (or clear with "source": null)
curl -X POST http://your-server:5002/api/multi-source/affinity \
  -H 'Content-Type: application/json' \
  -d '{"series_id": 123, "source": "jellyfin"}'
```

The Scheduler page also shows a live "Current series pins" table with
clear-pin buttons.

> Wiring two servers: point BOTH your Plex and Jellyfin webhooks at this
> instance (`/api/integration/plex/webhook` and
> `/api/integration/jellyfin/webhook`). Do not also add a Tautulli watched
> webhook if you already use the Plex native webhook.

### 2. Vacation / pause mode

A single switch (`automation_paused`) makes all watch events and scheduled
cleanup log-only: nothing is fetched, nothing is deleted. Useful for guests,
testing, or holidays. Pair it with reconciliation (below) to catch up on
anything watched while paused.

### 3. Missed-event reconciliation

Webhooks are fire-and-forget: an event that arrives while the app is down,
restarting, or paused is lost. When `reconcile_enabled` is on, a background
sweep (every `reconcile_interval_hours`, default 6) checks Plex and Jellyfin
watch history and replays anything missed, through the normal processing
path. Implemented in `reconcile.py`.

Safety properties: the first sweep only records a watermark (it never
bulk-replays your history), replays go through the same dedup/pinning gate
as live webhooks, a per-sweep cap prevents processing storms, and a failed
source sweep keeps its watermark so nothing is skipped.

| Key | Default | Meaning |
| --- | --- | --- |
| `automation_paused` | `false` | Log-only mode, no fetch or delete |
| `reconcile_enabled` | `false` | Enable the missed-event sweep |
| `reconcile_interval_hours` | `6` | How often to sweep |

Enable reconciliation only after your first successful live webhook test.

### 4. Concurrency hardening

- Watch integrations write a unique per-event payload file and pass its path
  to `media_processor.py`, instead of sharing one temp file (which could be
  clobbered by near-simultaneous events).
- `record_movie_watched()` uses a file lock + atomic rename so concurrent
  movie events from multiple servers/users cannot corrupt the stamp file.

---

## Prebuilt image (GHCR) and CI/CD

This fork builds its own image with GitHub Actions and publishes it to the
GitHub Container Registry, so you can pull instead of building locally.

- Image: `ghcr.io/funman300/episeerr` (public)
- Workflow: [.github/workflows/docker-image.yml](.github/workflows/docker-image.yml)
- Triggers: every push to `main`, plus manual dispatch
- Tags per build: `latest`, `sha-<commit>`, `b<run number>`, and
  `<version>-b<run number>`

If you fork this yourself, the workflow builds under YOUR account
(`ghcr.io/<you>/episeerr`) using the built-in `GITHUB_TOKEN` (no secrets to
configure). After the first successful run, set the package visibility to
Public once in the GitHub UI so hosts can pull without logging in:
`github.com/users/<you>/packages/container/episeerr/settings`.

### Deploy from the image

```yaml
# docker-compose.yml
services:
  episeerr:
    # Pin to an immutable commit tag, not :latest, so restarts are
    # deterministic. Bump it when you want a newer build.
    image: ghcr.io/funman300/episeerr:latest
    container_name: episeerr
    restart: unless-stopped
    ports:
      - "5002:5002"
    environment:
      - PYTHONUNBUFFERED=1
      - LOG_LEVEL=INFO
      - TZ=Etc/UTC
    volumes:
      - ./config:/app/config
      - ./logs:/app/logs
      - ./data:/app/data
      - ./temp:/app/temp
    # Join the same Docker network as your Sonarr so `sonarr` resolves by name
    networks:
      - arr
networks:
  arr:
    external: true
```

```bash
docker compose pull && docker compose up -d
# then open http://your-server:5002/setup
```

Update flow: push to `main` -> Actions builds and pushes -> bump the image
tag in your compose -> `docker compose pull && docker compose up -d`.

### Build locally instead (optional)

```bash
git clone https://github.com/funman300/episeerr
cd episeerr
docker build -t episeerr:local .
# set image: episeerr:local in docker-compose.yml, then: docker compose up -d
```

---

## Contributing upstream

These changes are kept on this fork. The multi-source feature was written to
be upstream-friendly (default-off, migration-safe), but this fork does not
open pull requests against the upstream repo.
