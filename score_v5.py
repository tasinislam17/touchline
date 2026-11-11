"""Score immutable V5 and same-snapshot V4 forecasts after the target round is final."""
import argparse
import datetime as dt
import json
import math
from pathlib import Path
from run_experiments import ROOT,load_current,evaluate
from score_freeze import verify_freeze


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',nargs='?');arguments=parser.parse_args()
    directory=Path(arguments.directory) if arguments.directory else ROOT/json.loads((ROOT/'reports/v5/latest_freeze.json').read_text())['path']
    manifest=verify_freeze(directory);rows,fixtures,_,finished,_,bootstrap=load_current();gw=manifest['gameweek']
    if bootstrap['events'][0]['deadline_time']!=manifest['season_start_deadline']:raise ValueError('Forecast and actual seasons differ')
    if gw not in finished:
        print(json.dumps({'status':'waiting_for_final_results','gw':gw,'checksums_verified':True}));return
    payloads={name:json.loads((directory/name).read_text()) for name in ('v5.json','v4_same_snapshot.json')}
    actual_fixtures={fixture['id']:fixture for fixture in fixtures}
    actual_pairs={(row['element'],row['fixture']) for row in rows if row['round']==gw}
    common=set.intersection(*[{(p['player'],p['fixture']) for p in payload['players']} for payload in payloads.values()])&actual_pairs
    results={}
    for name,payload in payloads.items():
        matches=[]
        for forecast in payload['matches']:
            fixture=actual_fixtures.get(forecast['fixture'])
            if not fixture or fixture.get('event')!=gw or fixture.get('team_h_score') is None:continue
            home,away=fixture['team_h_score'],fixture['team_a_score']
            matches.append(dict(forecast,actual_home=home,actual_away=away,
                                nll=-math.log(max(forecast['score_grid'][home][away],1e-15))))
        players=[p for p in payload['players'] if (p['player'],p['fixture']) in common]
        if not players:raise ValueError('No common forecast/actual support')
        results[name]=evaluate(players,matches,rows)
    output=ROOT/'reports/v5/evaluations';output.mkdir(exist_ok=True)
    path=output/(directory.name+'_'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
    path.write_text(json.dumps({'forecast_directory':str(directory),'gameweek':gw,'actual_snapshot':(ROOT/'data/latest.txt').read_text(),
                                'common_player_fixture_rows':len(common),'actual_rows_not_covered':len(actual_pairs-common),
                                'results':results},indent=2,allow_nan=False))
    print(path)


if __name__=='__main__':main()
