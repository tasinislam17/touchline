"""Create an immutable pre-deadline V5 forecast and same-snapshot V4 comparator."""
import datetime as dt
import hashlib
import json
from availability import connect,import_snapshots,at_or_before,iso
from models.v2 import MinutesModel,PlayerModelV2,make_minutes_training
from models.v3 import role_moments,adjust_team
from models.v5 import FeatureTeamModelV5,training_rows
from run_experiments import ROOT,load_archive,load_current,split
from run_v2 import combine_minutes,match_prediction
from run_v3 import verify_v2
from run_v5 import BASE,MINUTES_CANDIDATES
from validate_v4_players import load_match_history

OUT=ROOT/'reports/v5'


def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


class BoundModel:
    def __init__(self,model,names,kickoff):self.model=model;self.names=names;self.kickoff=kickoff
    def distribution(self,home,away):return self.model.distribution(self.names[home],self.names[away],self.kickoff)


def verify_selection():
    result=read(OUT/'results.json')
    if result['match']['production']!='v4':raise ValueError('Unexpected V5 match promotion state')
    if not result['minutes']['accepted'] or result['minutes']['production']!='r3_h26':raise ValueError('V5 minutes gate failed')
    if not result['combined_player_gate']:raise ValueError('V5 combined player gate failed')
    if result['production_config']['match']!=BASE or result['production_config']['minutes']!=MINUTES_CANDIDATES['r3_h26']:
        raise ValueError('Production configuration differs from evaluated selection')
    source=ROOT/result['input_snapshot']
    if (ROOT/'data/latest.txt').read_text().strip()!=result['input_snapshot']:raise ValueError('Live input changed after V5 evaluation')
    if sha(source/'manifest.json')!=result['data_manifest_sha256']:raise ValueError('V5 data manifest changed')
    for name,digest in result['source_sha256'].items():
        if sha(ROOT/name)!=digest:raise ValueError('V5 evaluated source changed: '+name)
    return result


def main():
    verify_v2();selection=verify_selection()
    rows,fixtures,deadlines,finished,scoring,bootstrap=load_current();gw=max(finished)+1
    now=dt.datetime.now(dt.timezone.utc);deadline=dt.datetime.fromisoformat(deadlines[gw].replace('Z','+00:00'))
    if now>=deadline:raise ValueError('Target deadline has passed')
    source=ROOT/selection['input_snapshot'];source_manifest=read(source/'manifest.json');observed=iso(source_manifest['retrieved_at'])
    season=bootstrap['events'][0]['deadline_time']
    with connect() as database:
        import_snapshots(database);observation=at_or_before(database,season,observed)
    if observation is None:raise ValueError('No availability observation at forecast input time')
    roster={player['id']:dict(player) for player in bootstrap['elements']}
    for player_id,value in observation['players'].items():
        if player_id in roster:roster[player_id].update(value)
    archive=load_archive(scoring)
    minutes_training=combine_minutes(make_minutes_training(archive[0],archive[1],archive[2]),
                                     make_minutes_training(rows,fixtures,deadlines))
    train,past,target=split(rows,fixtures,deadlines,gw)
    player_config=selection['production_config']['player']
    player_models={
        'v5':PlayerModelV2(train,scoring,MinutesModel(minutes_training,gw,**MINUTES_CANDIDATES['r3_h26']),**player_config),
        'v4_same_snapshot':PlayerModelV2(train,scoring,MinutesModel(minutes_training,gw,**MINUTES_CANDIDATES['r3_h8']),**player_config),
    }
    for model in player_models.values():model.minute_blend=1.
    history=load_match_history(rows,fixtures,deadlines,bootstrap);match_training=training_rows(history,BASE)
    team_model=FeatureTeamModelV5(history,observed,match_training,'2026-27',BASE)
    names={team['id']:team['name'] for team in bootstrap['teams']}
    matches=[match_prediction(BoundModel(team_model,names,fixture['kickoff_time']),fixture,gw,True) for fixture in target]
    for match in matches:
        fixture=next(f for f in target if f['id']==match['fixture'])
        match['explanation']=team_model.explain(names[match['home']],names[match['away']],fixture['kickoff_time'])
    payloads={name:{'configuration':{'match':BASE,'minutes':MINUTES_CANDIDATES['r3_h26' if name=='v5' else 'r3_h8'],
                                     'player':player_config},'matches':json.loads(json.dumps(matches)),'players':[]}
              for name in player_models}
    last_team={}
    for row in train:last_team[row['team']]=max(last_team.get(row['team'],''),row['kickoff_time'])
    checks=[]
    match_map={match['fixture']:match for match in matches}
    for fixture in target:
        match=match_map[fixture['id']]
        for team in (fixture['team_h'],fixture['team_a']):
            members=[player for player in roster.values() if player['team']==team]
            team_lambda,opponent_lambda=((match['home_goals'],match['away_goals']) if team==fixture['team_h']
                                         else (match['away_goals'],match['home_goals']))
            for variant,player_model in player_models.items():
                player_model.context={player['id']:{'kickoff':fixture['kickoff_time'],'home':team==fixture['team_h'],
                                      'team_last_kickoff':last_team.get(team)} for player in members}
                raw=[];roles={}
                for player in members:
                    value=player_model.raw(player['id'],player['element_type']);history_rows=player_model.hist.get(player['id'],[])
                    value.update(gw=gw,fixture=fixture['id'],team=team,name=player['web_name'],price=player['now_cost']/10,
                                 prior_minutes=sum(row['minutes'] for row in history_rows)/len(history_rows) if history_rows else 0,
                                 history_matches=len(history_rows),cold_start=not bool(history_rows))
                    raw.append(value);roles[player['id']]=role_moments(player_model,player['id'],player['element_type'])
                scored,audit=adjust_team(raw,roles,roster,team_lambda,opponent_lambda,scoring,constrain=True)
                payloads[variant]['players']+=scored;checks.append(dict(audit,variant=variant,fixture=fixture['id'],team=team))
    now=dt.datetime.now(dt.timezone.utc)
    if now>=deadline:raise ValueError('Deadline passed during V5 fitting')
    directory=OUT/'freezes'/f"gw{gw}_{now.strftime('%Y%m%dT%H%M%S%fZ')}";directory.mkdir(parents=True)
    for name,payload in payloads.items():(directory/f'{name}.json').write_text(json.dumps(payload,separators=(',',':'),allow_nan=False))
    (directory/'lineup_checks.json').write_text(json.dumps(checks,separators=(',',':'),allow_nan=False))
    sources=['freeze_v5.py','models/v5.py','models/v4.py','models/v3.py','models/v2.py','models/engine.py','availability.py',
             'run_v5.py','run_v4.py','run_experiments.py','run_v2.py']
    evidence=['reports/v5/PROTOCOL.md','reports/v5/results.json']
    for name in sources+evidence:
        destination=directory/'source'/name;destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes((ROOT/name).read_bytes())
    manifest={'model_version':'v5-experimental','forecast_file':'v5.json','created_at_utc':now.isoformat(),'gameweek':gw,
              'deadline_utc':deadlines[gw],'season_start_deadline':season,'data_snapshot':selection['input_snapshot'],
              'data_manifest_sha256':selection['data_manifest_sha256'],'availability_observed_at':observed,
              'source_code_sha256':{name:sha(ROOT/name) for name in sources},
              'historical_inputs_sha256':{name:sha(ROOT/name) for name in ('data/prior_2024_25.csv','data/prior_season.csv')},
              'role':'Pre-deadline GW11 forecast. V4 match form retained; minutes decay updated after GW9-10 confirmation.',
              'limitations':['The minutes improvement is small and needs more prospective rounds.',
                             'Only 20 matches were available in the new match confirmation slice.',
                             'Availability mapping affects player points but remains uncalibrated.',
                             'Team rates do not automatically alter for injury or manager-change scenarios.',
                             'One-gameweek forecasts only; minutes are not a joint substitution simulation.']}
    manifest['files_sha256']={str(path.relative_to(directory)):sha(path) for path in directory.rglob('*') if path.is_file()}
    (directory/'manifest.json').write_text(json.dumps(manifest,indent=2))
    (OUT/'latest_freeze.json').write_text(json.dumps({'path':str(directory.relative_to(ROOT))},indent=2))
    verify_v2();print(json.dumps({'freeze':str(directory),'gameweek':gw,'players':len(payloads['v5']['players']),
                                  'matches':len(matches),'deadline':deadlines[gw]},indent=2))


if __name__=='__main__':main()
