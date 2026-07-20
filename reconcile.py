"""
Missed watch-event reconciliation.

Webhooks are fire-and-forget: if Episeerr is down, restarting, or paused when
an episode finishes, the event is lost and that show's rolling window stalls
until the next watch. This module periodically sweeps the media servers'
watch history for episodes played since the last sweep and replays them
through the normal processing path (same per-event payload + media_processor
subprocess the webhook integrations use), so the system self-heals.

Replays are safe: multi-source dedup ignores episodes already processed, and
re-running window logic for an already-current episode is a no-op. Gated
behind `reconcile_enabled` (default off) and skipped while
`automation_paused` is set.

Currently sweeps Plex and Jellyfin. State (last sweep time) lives in
data/reconcile_state.json; the first run only initializes the watermark so
enabling the feature never replays historical watch data.
"""

import json
import logging
import os
import subprocess
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

STATE_FILE = os.path.join(os.getcwd(), 'data', 'reconcile_state.json')

# Overlap added to each sweep window so events landing during the previous
# sweep are not missed; dedup absorbs the resulting replays.
OVERLAP_SECONDS = 300

# Hard cap per sweep so a misbehaving history API cannot trigger a
# processing storm. Anything beyond the cap is logged, not silently dropped.
MAX_EVENTS_PER_SWEEP = 50


def _load_state():
    try:
        with open(STATE_FILE, 'r') as fh:
            return json.load(fh)
    except Exception:
        return {}


def _save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    tmp = STATE_FILE + '.tmp'
    with open(tmp, 'w') as fh:
        json.dump(state, fh, indent=2)
    os.replace(tmp, STATE_FILE)


def _spawn_processor(title, season, episode, source):
    """Replay one watch event through the standard processing path."""
    temp_dir = os.path.join(os.getcwd(), 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    payload = {
        'server_title': title,
        'server_season_num': int(season),
        'server_ep_num': int(episode),
        'source': source,
    }
    temp_path = os.path.join(
        temp_dir, f'data_from_server_{os.urandom(4).hex()}.json')
    with open(temp_path, 'w') as fh:
        json.dump(payload, fh)
    result = subprocess.run(
        ["python3", os.path.join(os.getcwd(), "media_processor.py"), temp_path],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        logger.error(
            f"[reconcile] media_processor failed for '{title}' "
            f"S{season}E{episode} (rc={result.returncode}): "
            f"{(result.stderr or '').strip()[:300]}")
        return False
    return True


def _sweep_plex(since_ts):
    """Episodes viewed on Plex since since_ts: [(viewed_ts, title, season, ep)]."""
    from settings_db import get_service
    from episeerr_utils import http

    svc = get_service('plex', 'default')
    if not svc or not svc.get('url') or not svc.get('api_key'):
        return []

    resp = http.get(
        f"{svc['url'].rstrip('/')}/status/sessions/history/all",
        headers={'X-Plex-Token': svc['api_key'],
                 'Accept': 'application/json'},
        params={'viewedAt>': int(since_ts),
                'sort': 'viewedAt:desc',
                'X-Plex-Container-Size': 500},
        timeout=30,
    )
    resp.raise_for_status()
    metadata = (resp.json().get('MediaContainer') or {}).get('Metadata') or []

    events = []
    for item in metadata:
        if item.get('type') != 'episode':
            continue
        title = item.get('grandparentTitle')
        season = item.get('parentIndex')
        episode = item.get('index')
        viewed = item.get('viewedAt')
        if not all([title, season is not None, episode is not None, viewed]):
            continue
        if int(viewed) <= since_ts:
            continue
        events.append((int(viewed), title, int(season), int(episode)))
    return events


def _parse_jellyfin_date(value):
    """Jellyfin dates are ISO with .NET 7-digit fractions and 'Z'."""
    if not value:
        return None
    try:
        base = value.split('.')[0].rstrip('Z')
        return datetime.strptime(base, '%Y-%m-%dT%H:%M:%S').replace(
            tzinfo=timezone.utc).timestamp()
    except Exception:
        return None


def _sweep_jellyfin(since_ts):
    """Episodes played on Jellyfin since since_ts: [(ts, title, season, ep)]."""
    from integrations import get_integration
    from episeerr_utils import http

    integration = get_integration('jellyfin')
    if integration is None:
        return []
    config = integration.get_config()
    if not config or not config.get('url') or not config.get('api_key'):
        return []
    user_id = integration._resolve_user_id(config)
    if not user_id:
        logger.warning("[reconcile] Jellyfin user could not be resolved")
        return []

    resp = http.get(
        f"{config['url'].rstrip('/')}/Users/{user_id}/Items",
        headers={'X-Emby-Token': config['api_key']},
        params={'IncludeItemTypes': 'Episode', 'Recursive': 'true',
                'Filters': 'IsPlayed', 'SortBy': 'DatePlayed',
                'SortOrder': 'Descending', 'Limit': 500,
                'Fields': 'SeriesName,ParentIndexNumber,IndexNumber,UserData'},
        timeout=30,
    )
    resp.raise_for_status()

    events = []
    for item in resp.json().get('Items') or []:
        played_at = _parse_jellyfin_date(
            (item.get('UserData') or {}).get('LastPlayedDate'))
        if played_at is None or played_at <= since_ts:
            continue
        title = item.get('SeriesName')
        season = item.get('ParentIndexNumber')
        episode = item.get('IndexNumber')
        if not all([title, season is not None, episode is not None]):
            continue
        events.append((played_at, title, int(season), int(episode)))
    return events


def run_reconciliation():
    """One sweep. Returns a summary dict; never raises."""
    from media_processor import load_global_settings

    summary = {'ran': False, 'replayed': 0, 'errors': []}
    try:
        settings = load_global_settings()
        if not settings.get('reconcile_enabled', False):
            return summary
        if settings.get('automation_paused', False):
            logger.info("[reconcile] Skipping sweep - automation is paused")
            return summary

        sweep_start = time.time()
        state = _load_state()
        last_sweep = state.get('last_sweep')

        if not last_sweep:
            # First run: only set the watermark, never replay all history.
            state['last_sweep'] = sweep_start
            _save_state(state)
            logger.info("[reconcile] Initialized watermark; sweeps begin "
                        "with the next interval")
            summary['ran'] = True
            return summary

        since = last_sweep - OVERLAP_SECONDS
        events = []
        for sweep_fn, label in ((_sweep_plex, 'plex'),
                                (_sweep_jellyfin, 'jellyfin')):
            try:
                found = sweep_fn(since)
                if found:
                    logger.info(f"[reconcile] {label}: {len(found)} watched "
                                f"episode(s) since last sweep")
                events.extend((ts, title, s, e, label)
                              for ts, title, s, e in found)
            except Exception as exc:
                logger.warning(f"[reconcile] {label} sweep failed: {exc}")
                summary['errors'].append(f"{label}: {exc}")

        events.sort(key=lambda ev: ev[0])  # replay in watch order
        capped = len(events) > MAX_EVENTS_PER_SWEEP
        if capped:
            logger.warning(
                f"[reconcile] {len(events)} events found, capping at "
                f"{MAX_EVENTS_PER_SWEEP}; the rest are picked up next sweep")
            events = events[:MAX_EVENTS_PER_SWEEP]

        replayed = 0
        for ts, title, season, episode, source in events:
            if _spawn_processor(title, season, episode, source):
                replayed += 1

        # A failed source sweep keeps the old watermark so its window is
        # retried (dedup absorbs the overlap). When capped, advance only to
        # the newest replayed event so the dropped tail is retried next sweep.
        if not summary['errors']:
            state['last_sweep'] = (events[-1][0] if capped and events
                                   else sweep_start)
            _save_state(state)

        if replayed:
            logger.info(f"[reconcile] Replayed {replayed} missed event(s)")
        summary.update(ran=True, replayed=replayed)
        return summary
    except Exception as exc:
        logger.error(f"[reconcile] Unexpected error: {exc}", exc_info=True)
        summary['errors'].append(str(exc))
        return summary
