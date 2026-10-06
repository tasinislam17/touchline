"""Run a sequential forecast refresh. Local/manual only; never deploys a website.

A failed fetch, model run or validation leaves the published manifest untouched.
Model code refuses post-deadline retrospective freezes. Persist the job workspace
between executions or restore source/model artifacts before running in a fresh CI job.
"""
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys
import time
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.publication import atomic, encode


def main():
    start=time.monotonic()
    try:
        selection=json.loads((ROOT/'config/production-model.json').read_text())
        for command in (['fetch_data.py'], [selection['refresh_script']], ['-m', 'pipeline.publication']):
            subprocess.run([sys.executable, *command], cwd=ROOT, check=True, timeout=1800)
    except Exception as exc:
        atomic(ROOT/'web/public/data/status.json', encode({'state':'failed', 'attempted_at':dt.datetime.now(dt.timezone.utc).isoformat(), 'last_error':type(exc).__name__}))
        raise
    finally:
        print(json.dumps({'elapsed_seconds':round(time.monotonic()-start,2)}))

if __name__=='__main__':main()
