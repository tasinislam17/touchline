"""Validate immutable research inputs and atomically publish a compact app contract.

Never fits models or relabels an old forecast as newly predicted. No manager data.
Usage: python -m pipeline.publication [--output web/public/data]
"""
import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 1


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def atomic(path, raw):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
        tmp = Path(f.name)
        try:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
    try:
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()


def timestamp(value):
    if '-' not in value:
        return dt.datetime.strptime(value, '%Y%m%dT%H%M%SZ').replace(tzinfo=dt.timezone.utc)
    result = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Naive input timestamp')
    return result


def finite(value, label):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError(f'Invalid numeric field: {label}')


def unique(rows, key, label):
    ids = [row[key] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError(f'Duplicate {label} identity')


def normalize(bootstrap, fixtures, observed_at):
    """Season namespaces IDs; all fixtures retained, including unscheduled and doubles."""
    for key in ('events', 'teams', 'elements', 'element_types'):
        if not isinstance(bootstrap.get(key), list) or not bootstrap[key]:
            raise ValueError(f'Missing source collection: {key}')
    if not isinstance(fixtures, list):
        raise ValueError('Fixtures must be a list')
    for key in ('events', 'teams', 'elements'):
        unique(bootstrap[key], 'id', key)
    unique(fixtures, 'id', 'fixtures')
    start = min(timestamp(e['deadline_time']) for e in bootstrap['events'])
    season = f'{start.year}-{str(start.year + 1)[-2:]}'
    teams = [{k: t[k] for k in ('id', 'name', 'short_name')} for t in bootstrap['teams']]
    team_ids = {t['id'] for t in teams}
    event_ids = {e['id'] for e in bootstrap['events']}
    players = []
    for p in bootstrap['elements']:
        if p['team'] not in team_ids or p['element_type'] not in (1, 2, 3, 4):
            raise ValueError('Unknown team/position')
        finite(p['now_cost'], 'price')
        if p['now_cost'] < 0:
            raise ValueError('Negative price')
        players.append({'id': p['id'], 'key': f"{season}:player:{p['id']}",
                        'name': p['web_name'], 'team': p['team'], 'position': p['element_type'],
                        'price_tenths': p['now_cost'], 'status': p.get('status', 'unknown'),
                        'news': p.get('news', ''), 'chance_next_round': p.get('chance_of_playing_next_round'),
                        'total_points': p.get('total_points', 0), 'ownership': float(p.get('selected_by_percent') or 0)})
    normalized_fixtures = []
    for f in fixtures:
        if f['team_h'] not in team_ids or f['team_a'] not in team_ids or f['team_h'] == f['team_a']:
            raise ValueError('Invalid fixture teams')
        if f.get('event') is not None and f['event'] not in event_ids:
            raise ValueError('Unknown fixture event')
        normalized_fixtures.append({k: f.get(k) for k in ('id', 'event', 'team_h', 'team_a', 'kickoff_time', 'finished')})
    return {'season': season, 'observed_at': timestamp(observed_at).isoformat(), 'teams': teams, 'players': players,
            'events': [{'id': e['id'], 'deadline': e['deadline_time'], 'finished': e['finished'], 'overrides': e.get('overrides', {})} for e in bootstrap['events']],
            'fixtures': normalized_fixtures,
            'rules_source': {'game_settings': bootstrap.get('game_settings', {}), 'element_types': bootstrap['element_types']}}


def validate_forecast(payload, catalog, meta):
    players = {p['id']: p for p in catalog['players']}
    fixtures = {f['id']: f for f in catalog['fixtures']}
    target = {f['id'] for f in catalog['fixtures'] if f['event'] == meta['gameweek']}
    if not target:
        raise ValueError('No fixtures for target gameweek')
    observed = timestamp(catalog['observed_at'])
    created = timestamp(meta['created_at_utc'])
    deadline = timestamp(meta['deadline_utc'])
    if not observed <= created < deadline:
        raise ValueError('Observation/forecast/deadline ordering violates pre-deadline contract')
    first = min(e['deadline'] for e in catalog['events'])
    if timestamp(first) != timestamp(meta['season_start_deadline']):
        raise ValueError('Season mismatch')
    event = next(e for e in catalog['events'] if e['id'] == meta['gameweek'])
    if timestamp(event['deadline']) != deadline:
        raise ValueError('Deadline mismatch')
    seen = set()
    for p in payload['players']:
        key = p['player'], p['fixture']
        if key in seen:
            raise ValueError('Duplicate player-fixture forecast')
        seen.add(key)
        if p['player'] not in players or p['fixture'] not in target:
            raise ValueError('Unknown forecast identity')
        f = fixtures[p['fixture']]
        if p['gw'] != meta['gameweek'] or p['team'] != players[p['player']]['team'] or p['team'] not in (f['team_h'], f['team_a']):
            raise ValueError('Forecast team/event mismatch')
        for k in ('points', 'minutes', 'goals', 'assists', 'p_play', 'p_start', 'p60', 'p_clean_sheet'):
            finite(p[k], k)
        if not 0 <= p['minutes'] <= 90 or not 0 <= p['p_start'] <= p['p_play'] <= 1 or not 0 <= p['p60'] <= p['p_play'] or not 0 <= p['p_clean_sheet'] <= 1:
            raise ValueError('Invalid player moments')
        for k, v in p['components'].items():
            finite(v, k)
        if abs(sum(p['components'].values()) - p['points']) > 1e-6:
            raise ValueError('Point components do not sum')
    expected = {(p['id'], fid) for fid in target for p in players.values() if p['team'] in (fixtures[fid]['team_h'], fixtures[fid]['team_a'])}
    if seen != expected:
        raise ValueError('Incomplete player-fixture coverage')
    unique(payload['matches'], 'fixture', 'match forecast')
    if {m['fixture'] for m in payload['matches']} != target:
        raise ValueError('Incomplete match coverage')
    for m in payload['matches']:
        f = fixtures[m['fixture']]
        if (m['home'], m['away'], m['gw']) != (f['team_h'], f['team_a'], meta['gameweek']):
            raise ValueError('Match identity mismatch')
        for key in ('home_win', 'draw', 'away_win', 'home_goals', 'away_goals'):
            finite(m[key], key)
            if m[key] < 0:
                raise ValueError('Negative match moment')
        if abs(m['home_win'] + m['draw'] + m['away_win'] - 1) > 1e-6:
            raise ValueError('Match probabilities do not sum to one')
        grid = m['score_grid']
        # Research grid is a nested matrix, retained in the published contract.
        values = [v for row in grid for v in row] if isinstance(grid[0], list) else [r['probability'] for r in grid]
        if any(not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 for v in values) or abs(sum(values) - 1) > 1e-6:
            raise ValueError('Invalid score grid')


def build(root=ROOT, freeze=None):
    root = Path(root)
    selection = read_json(root / 'config/production-model.json') if (root / 'config/production-model.json').exists() else {'pointer': 'reports/v3/latest_freeze.json'}
    freeze = Path(freeze) if freeze else root / read_json(root / selection['pointer'])['path']
    meta = read_json(freeze / 'manifest.json')
    for name, expected in meta['files_sha256'].items():
        if digest((freeze / name).read_bytes()) != expected:
            raise ValueError('Forecast checksum mismatch: ' + name)
    source = root / meta['data_snapshot']
    if digest((source / 'manifest.json').read_bytes()) != meta['data_manifest_sha256']:
        raise ValueError('Data manifest checksum mismatch')
    manifest = read_json(source / 'manifest.json')
    for name, expected in manifest['sha256'].items():
        if digest((source / name).read_bytes()) != expected:
            raise ValueError('Source checksum mismatch: ' + name)
    bootstrap = read_json(source / 'bootstrap.json')
    catalog = normalize(bootstrap, read_json(source / 'fixtures.json'), manifest['retrieved_at'])
    forecast_file = meta.get('forecast_file', 'v3.json')
    forecast = read_json(freeze / forecast_file)
    validate_forecast(forecast, catalog, meta)
    rows = []
    for p in forecast['players']:
        rows.append({k: p[k] for k in ('player', 'fixture', 'gw', 'team', 'points', 'minutes', 'p_start', 'p_play', 'p60', 'goals', 'assists', 'p_clean_sheet', 'components', 'availability')})
    # Include players without fixtures with a zero gameweek sum, without inventing a fixture row.
    aggregate = [{'player': p['id'], 'gw': meta['gameweek'], 'points': sum(r['points'] for r in rows if r['player'] == p['id']),
                  'fixtures': [r['fixture'] for r in rows if r['player'] == p['id']]} for p in catalog['players']]
    return {'schema_version': SCHEMA, 'meta': {'model_version': meta.get('model_version', 'v3-experimental'), 'season': catalog['season'],
            'gameweek': meta['gameweek'], 'deadline': meta['deadline_utc'], 'observed_at': catalog['observed_at'],
            'forecast_at': meta['created_at_utc'], 'source_checksum': meta['data_manifest_sha256'],
            'forecast_checksum': meta['files_sha256'][forecast_file], 'next_scheduled_refresh': None,
            'refresh_mode': 'manual-development', 'stale_after_hours': 24,
            'limitations': meta.get('limitations', ['Availability mapping is experimental, not calibrated.', 'Scorelines do not yet respond to injury news.',
                             'One-gameweek forecasts only. No optimizer recommendations yet.', 'Player minutes are not a joint substitution simulation.'])},
            'catalog': catalog, 'player_forecasts': rows, 'gameweek_totals': aggregate, 'matches': forecast['matches']}


def publish(payload, output, now=None):
    output = Path(output)
    raw = encode(payload)
    sha = digest(raw)
    file = f'forecast-{sha}.json'
    now = now or dt.datetime.now(dt.timezone.utc).isoformat()
    atomic(output / file, raw)
    previous = None
    if (output / 'manifest.json').exists():
        old = read_json(output / 'manifest.json')
        previous = old['current'] if old['current']['sha256'] != sha else old.get('previous')
    ref = {'file': file, 'sha256': sha, 'bytes': len(raw)}
    manifest = {'schema_version': SCHEMA, 'current': ref, 'previous': previous, 'published_at': now,
                'last_successful_refresh': payload['meta']['observed_at'], 'next_scheduled_refresh': None,
                'refresh_mode': 'manual-development'}
    # Manifest is the commit point. Readers never see a reference to an incomplete file.
    atomic(output / 'manifest.json', encode(manifest))
    atomic(output / 'status.json', encode({'state': 'ok', 'attempted_at': now, 'last_error': None}))
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default=str(ROOT / 'web/public/data'))
    parser.add_argument('--freeze', type=Path)
    args = parser.parse_args()
    try:
        result = publish(build(freeze=args.freeze), args.output)
        print(json.dumps(result, indent=2))
    except Exception as exc:
        atomic(Path(args.output) / 'status.json', encode({'state': 'failed', 'attempted_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'last_error': type(exc).__name__}))
        raise


if __name__ == '__main__':
    main()
