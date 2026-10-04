"""Timestamped FPL availability observations, with explicit as-of retrieval.

`python availability.py` imports existing live snapshots idempotently.
`python availability.py --fetch` also captures a lightweight new live bootstrap.
news_added is source metadata, never treated as the time we first knew the news.
"""
import argparse
import datetime as dt
import hashlib
import json
import pathlib
import sqlite3
from fetch_data import fetch, BASE

ROOT=pathlib.Path(__file__).resolve().parent
FIELDS=['id','web_name','team','element_type','status','chance_of_playing_next_round',
        'chance_of_playing_this_round','news','news_added','removed','can_select']

def iso(stamp):
    if '-' not in stamp:
        stamp=dt.datetime.strptime(stamp,'%Y%m%dT%H%M%SZ').replace(tzinfo=dt.timezone.utc).isoformat()
    return dt.datetime.fromisoformat(stamp.replace('Z','+00:00')).astimezone(dt.timezone.utc).isoformat()

def connect(path=None):
    db=sqlite3.connect(path or ROOT/'data/availability.sqlite')
    db.execute('CREATE TABLE IF NOT EXISTS snapshots (id TEXT PRIMARY KEY, observed_at TEXT NOT NULL, season TEXT NOT NULL, source_path TEXT NOT NULL, sha256 TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS observations (snapshot_id TEXT NOT NULL, player INTEGER NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(snapshot_id,player))')
    return db

def ingest(db,directory):
    raw=(directory/'bootstrap.json').read_bytes();digest=hashlib.sha256(raw).hexdigest()
    meta=json.loads((directory/'manifest.json').read_text());b=json.loads(raw)
    expected=meta.get('sha256',{}).get('bootstrap.json')
    if expected and expected!=digest:raise ValueError('Snapshot checksum mismatch')
    observed=iso(meta['retrieved_at']);season=b['events'][0]['deadline_time']
    snapshot_id=hashlib.sha256((observed+season+digest).encode()).hexdigest()
    with db:
        db.execute('INSERT OR IGNORE INTO snapshots VALUES (?,?,?,?,?)',(snapshot_id,observed,season,str(directory),digest))
        db.executemany('INSERT OR IGNORE INTO observations VALUES (?,?,?)',
                       [(snapshot_id,p['id'],json.dumps({k:p.get(k) for k in FIELDS})) for p in b['elements']])
    return snapshot_id

def at_or_before(db,season,as_of):
    snapshot=db.execute('SELECT id,observed_at FROM snapshots WHERE season=? AND observed_at<=? ORDER BY observed_at DESC LIMIT 1',(season,iso(as_of))).fetchone()
    if snapshot is None:return None
    return {'snapshot_id':snapshot[0],'observed_at':snapshot[1],
            'players':{pid:json.loads(payload) for pid,payload in db.execute('SELECT player,payload FROM observations WHERE snapshot_id=?',(snapshot[0],))}}

def history(db,season,player):
    return [{'observed_at':when,**json.loads(payload)} for when,payload in db.execute(
        'SELECT s.observed_at,o.payload FROM snapshots s JOIN observations o ON s.id=o.snapshot_id WHERE s.season=? AND o.player=? ORDER BY s.observed_at',(season,player))]

def import_snapshots(db):
    for root in [ROOT/'data/raw',ROOT/'data/availability_raw']:
        if root.exists():
            for directory in sorted(root.iterdir()):
                if (directory/'manifest.json').exists() and (directory/'bootstrap.json').exists():ingest(db,directory)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--fetch',action='store_true');args=parser.parse_args()
    if args.fetch:
        stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        directory=ROOT/'data/availability_raw'/stamp;directory.mkdir(parents=True,exist_ok=False)
        fetch('bootstrap-static/',directory/'bootstrap.json')
        (directory/'manifest.json').write_text(json.dumps({'retrieved_at':stamp,'source':BASE,
            'sha256':{'bootstrap.json':hashlib.sha256((directory/'bootstrap.json').read_bytes()).hexdigest()}},indent=2))
    with connect() as db:
        import_snapshots(db)
        print(json.dumps({'snapshots':db.execute('SELECT COUNT(*) FROM snapshots').fetchone()[0],
                          'observations':db.execute('SELECT COUNT(*) FROM observations').fetchone()[0]}))

if __name__=='__main__':main()
