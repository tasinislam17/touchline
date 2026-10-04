"""Evaluate a saved forecast against a refreshed API snapshot without refitting.

Usage: python score_freeze.py [reports/v2/freezes/gw6_TIMESTAMP]
Run fetch_data.py first after the GW is complete. Forecast checksums are verified.
"""
import argparse
import datetime as dt
import hashlib
import json
import pathlib
from run_experiments import ROOT, load_current, evaluate


def verify_freeze(directory):
    manifest=json.loads((directory/'manifest.json').read_text())
    for name,digest in manifest['files_sha256'].items():
        if hashlib.sha256((directory/name).read_bytes()).hexdigest()!=digest:
            raise ValueError('Saved forecast checksum mismatch: '+name)
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',nargs='?')
    args=parser.parse_args()
    directory=pathlib.Path(args.directory) if args.directory else ROOT/json.loads((ROOT/'reports/v2/latest_freeze.json').read_text())['path']
    manifest=verify_freeze(directory)
    rows,fixtures,_,finished,_,bootstrap=load_current();gw=manifest['gameweek']
    if manifest.get('season_start_deadline',bootstrap['events'][0]['deadline_time'])!=bootstrap['events'][0]['deadline_time']:
        raise ValueError('Current API season differs from the saved forecast season')
    if gw not in finished:
        print(json.dumps({'status':'waiting_for_final_results','gameweek':gw,'forecast_files_verified':True,
                          'message':'Refresh with fetch_data.py after the gameweek is finished and data-checked; then run this scorer again.'},indent=2))
        return
    actual={f['id']:f for f in fixtures};results={}
    actual_pairs={(r['element'],r['fixture']) for r in rows if r['round']==gw}
    for name in manifest['files_sha256']:
        payload=json.loads((directory/name).read_text());matches=[]
        for m in payload['matches']:
            f=actual.get(m['fixture'])
            if f is None or f.get('event')!=gw or f.get('team_h_score') is None:continue
            m=dict(m,actual_home=f['team_h_score'],actual_away=f['team_a_score'])
            # Preserve original score probabilities; never rebuild the model here.
            if 'score_grid' in m:
                import math
                m['nll']=-math.log(max(m['score_grid'][f['team_h_score']][f['team_a_score']],1e-15))
            matches.append(m)
        p=[x for x in payload['players'] if (x['player'],x['fixture']) in actual_pairs]
        predicted={(x['player'],x['fixture']) for x in p}
        results[name]={'metrics':evaluate(p,matches,rows),
                       'unpredicted_actual_rows':len(actual_pairs-predicted),
                       'prediction_rows_without_target_actual':len(payload['players'])-len(p),
                       'matched_matches':len(matches),'forecast_matches':len(payload['matches']),
                       'scoreline_log_loss_available':all('nll' in m for m in matches) and bool(matches)}
    # Common support avoids crediting V2 for adding easy-to-predict inactive players.
    payloads={name:json.loads((directory/name).read_text()) for name in manifest['files_sha256']}
    common=set.intersection(*[{(x['player'],x['fixture']) for x in value['players']} for value in payloads.values()])&actual_pairs
    common_metrics={name:evaluate([x for x in value['players'] if (x['player'],x['fixture']) in common],[],rows)
                    for name,value in payloads.items()}
    now=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output=ROOT/'reports/v2/live_evaluations'/f'{directory.name}_{now}.json';output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps({'forecast_directory':str(directory),'scored_at_utc':now,'gameweek':gw,
        'actual_snapshot':(ROOT/'data/latest.txt').read_text().strip(),'results':results,'common_support':common_metrics},indent=2,allow_nan=False))
    print(output)


if __name__=='__main__':main()
