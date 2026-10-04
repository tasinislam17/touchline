"""Download immutable, validated public FPL snapshots; no credentials required."""
import concurrent.futures
import datetime
import hashlib
import json
import pathlib
import subprocess
import time
from pipeline.publication import atomic, encode, normalize

ROOT = pathlib.Path(__file__).resolve().parent
BASE = 'https://fantasy.premierleague.com/api/'


def fetch(path, dest):
    for attempt in range(4):
        r = subprocess.run(['curl', '-fsSL', '--max-time', '45', BASE + path], capture_output=True)
        if r.returncode == 0:
            try:
                value = json.loads(r.stdout)
                atomic(dest, r.stdout)
                return value
            except ValueError:
                pass
        if attempt < 3:
            time.sleep(2 ** attempt)
    raise RuntimeError('Failed to fetch ' + path)


def snapshot(root=ROOT, fetcher=fetch, workers=4):
    root = pathlib.Path(root)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    directory = root / 'data/raw' / stamp
    directory.mkdir(parents=True, exist_ok=False)
    b = fetcher('bootstrap-static/', directory / 'bootstrap.json')
    fixtures = fetcher('fixtures/', directory / 'fixtures.json')
    normalized = normalize(b, fixtures, stamp)
    def player(p):
        result = fetcher(f"element-summary/{p['id']}/", directory / f"player_{p['id']}.json")
        if not isinstance(result.get('history'), list) or not isinstance(result.get('fixtures'), list):
            raise ValueError('Invalid player history schema')
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for i, _ in enumerate(pool.map(player, b['elements']), 1):
            if i % 100 == 0:
                print(f'{i}/{len(b["elements"])} players', flush=True)
    # No manifest or latest pointer is committed until every response passes validation.
    manifest = {'retrieved_at': stamp, 'completed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'source': BASE, 'players': len(b['elements']),
                'sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.glob('*.json')}}
    atomic(directory / 'manifest.json', encode(manifest))
    atomic(root / 'data/normalized' / f'{stamp}.json', encode(normalized))
    atomic(root / 'data/latest.txt', str(directory.relative_to(root)).encode())
    return directory


def main():
    print(snapshot(), flush=True)


if __name__ == '__main__':
    main()
