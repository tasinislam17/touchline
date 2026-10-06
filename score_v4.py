"""Score immutable V4 and same-input V3 forecasts after final results; never refit."""
import argparse
import datetime as dt
import json
import math
import pathlib
from run_experiments import ROOT, load_current, evaluate
from score_freeze import verify_freeze

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',nargs='?');args=parser.parse_args()
    directory=pathlib.Path(args.directory) if args.directory else ROOT/json.loads((ROOT/'reports/v4/latest_freeze.json').read_text())['path']
    manifest=verify_freeze(directory);rows,fixtures,_,finished,_,b=load_current();gw=manifest['gameweek']
    if b['events'][0]['deadline_time']!=manifest['season_start_deadline']:raise ValueError('Forecast and actual seasons differ')
    if gw not in finished:
        print(json.dumps({'status':'waiting_for_final_results','gw':gw,'checksums_verified':True}));return
    actual={f['id']:f for f in fixtures};payloads={name:json.loads((directory/name).read_text()) for name in ('v4.json','v3_same_snapshot.json')}
    actual_pairs={(r['element'],r['fixture']) for r in rows if r['round']==gw}
    common=set.intersection(*[{(p['player'],p['fixture']) for p in x['players']} for x in payloads.values()])&actual_pairs
    results={}
    for name,payload in payloads.items():
        matches=[]
        for m in payload['matches']:
            f=actual.get(m['fixture'])
            if not f or f.get('event')!=gw or f.get('team_h_score') is None:continue
            h,a=f['team_h_score'],f['team_a_score'];m=dict(m,actual_home=h,actual_away=a,nll=-math.log(max(m['score_grid'][h][a],1e-15)))
            matches.append(m)
        ps=[p for p in payload['players'] if (p['player'],p['fixture']) in common]
        if not ps:raise ValueError('No common forecast/actual support; refusing to emit misleading metrics')
        results[name]=evaluate(ps,matches,rows)
    output=ROOT/'reports/v4/evaluations';output.mkdir(exist_ok=True)
    path=output/(directory.name+'_'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
    path.write_text(json.dumps({'forecast_directory':str(directory),'gameweek':gw,'actual_snapshot':(ROOT/'data/latest.txt').read_text(),
                              'common_player_fixture_rows':len(common),'actual_rows_not_covered':len(actual_pairs-common),'results':results},indent=2,allow_nan=False))
    print(path)

if __name__=='__main__':main()
