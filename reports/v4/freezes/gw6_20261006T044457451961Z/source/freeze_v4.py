"""Freeze the accepted V4 model and same-input V3 comparator before deadline."""
import datetime as dt
import hashlib
import json
from availability import connect,import_snapshots,at_or_before,iso
from models.v2 import MinutesModel,PlayerModelV2,make_minutes_training,AdjustedTeamModel
from models.v3 import role_moments,adjust_team
from models.v4_features import FeatureTeamModel,training_rows
from run_experiments import ROOT,load_current,load_archive,split
from run_v2 import combine_minutes,MINUTE_CANDIDATES,match_prediction
from run_v3 import verify_v2
from validate_v4_players import ClubAdapter,load_match_history

OUT=ROOT/'reports/v4'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text())

def verify_acceptance():
    results=read(OUT/'final_results.json');guard=read(OUT/'player_guard.json')
    new=results['confirmation']['candidate'];old=results['confirmation']['incumbent']
    if not (results['accepted_match_gate'] and new['log_loss']<=old['log_loss']*.99 and new['brier']<=old['brier']+.01
            and all(v['candidate']['log_loss']<=v['incumbent']['log_loss']+.03 for v in results['slices'].values())
            and guard['accepted_player_gate'] and guard['candidate']['prior_regulars']['rmse']<=guard['incumbent']['prior_regulars']['rmse']+.02):
        raise ValueError('V4 promotion gate failed')
    for name,digest in results['source_sha256'].items():
        if sha(ROOT/name)!=digest:raise ValueError('Selected model changed after evaluation')
    return results['configuration']

def main():
    verify_v2();config=verify_acceptance()
    rows,fixtures,deadlines,finished,scoring,b=load_current();gw=max(finished)+1
    now=dt.datetime.now(dt.timezone.utc)
    if now>=dt.datetime.fromisoformat(deadlines[gw].replace('Z','+00:00')):raise ValueError('Deadline passed')
    source=ROOT/(ROOT/'data/latest.txt').read_text().strip();observed=iso(read(source/'manifest.json')['retrieved_at'])
    season=b['events'][0]['deadline_time']
    with connect() as db:
        import_snapshots(db);observation=at_or_before(db,season,observed)
    if observation is None:raise ValueError('Missing availability observation')
    roster={p['id']:dict(p) for p in b['elements']}
    for pid,p in observation['players'].items():
        if pid in roster:roster[pid].update(p)
    archive=load_archive(scoring)
    mt=combine_minutes(make_minutes_training(archive[0],archive[1],archive[2]),make_minutes_training(rows,fixtures,deadlines))
    minutes=MinutesModel(mt,gw,**MINUTE_CANDIDATES['r3_h8'])
    train,past,target=split(rows,fixtures,deadlines,gw)
    player=PlayerModelV2(train,scoring,minutes,**read(ROOT/'reports/current_results.json')['player_config']);player.minute_blend=1.
    history=load_match_history(rows,fixtures,deadlines,b)
    model=FeatureTeamModel(history,observed,training_rows(history),'2026-27',**config)
    adapter=ClubAdapter(model,b)
    teammodels={'v4':adapter,'v3_same_snapshot':AdjustedTeamModel(past,train,ridge=20.,half_life=12.,rho=0.)}
    payloads={name:{'configuration':config if name=='v4' else {'incumbent':'adjusted_r20_h12'},
                    'matches':[match_prediction(m,f,gw,True) for f in target],'players':[]} for name,m in teammodels.items()}
    for m in payloads['v4']['matches']:
        m['explanation']=model.explain(adapter.names[m['home']],adapter.names[m['away']])
    last={}
    for r in train:last[r['team']]=max(last.get(r['team'],''),r['kickoff_time'])
    checks=[]
    for f in target:
        for team in (f['team_h'],f['team_a']):
            members=[p for p in roster.values() if p['team']==team]
            player.context={p['id']:dict(kickoff=f['kickoff_time'],home=team==f['team_h'],team_last_kickoff=last.get(team)) for p in members}
            raw=[];roles={}
            for p in members:
                r=player.raw(p['id'],p['element_type']);h=player.hist.get(p['id'],[])
                r.update(gw=gw,fixture=f['id'],team=team,name=p['web_name'],price=p['now_cost']/10,
                         prior_minutes=sum(x['minutes'] for x in h)/len(h) if h else 0,history_matches=len(h),cold_start=not bool(h))
                raw.append(r);roles[p['id']]=role_moments(player,p['id'],p['element_type'])
            for name,payload in payloads.items():
                m=next(m for m in payload['matches'] if m['fixture']==f['id'])
                lam,opp=(m['home_goals'],m['away_goals']) if team==f['team_h'] else (m['away_goals'],m['home_goals'])
                scored,audit=adjust_team(raw,roles,roster,lam,opp,scoring,constrain=True)
                payload['players']+=scored;checks.append(dict(audit,variant=name,fixture=f['id'],team=team))
    now=dt.datetime.now(dt.timezone.utc)
    if now>=dt.datetime.fromisoformat(deadlines[gw].replace('Z','+00:00')):raise ValueError('Deadline passed during fit')
    directory=OUT/'freezes'/f"gw{gw}_{now.strftime('%Y%m%dT%H%M%S%fZ')}";directory.mkdir(parents=True)
    for name,value in dict(payloads,lineup_checks=checks).items():(directory/f'{name}.json').write_text(json.dumps(value,allow_nan=False,separators=(',',':')))
    sources=['freeze_v4.py','models/v4.py','models/v4_features.py','models/v3.py','models/v2.py','models/engine.py','availability.py','run_v4.py','validate_v4_players.py','run_experiments.py','run_v2.py']
    for name in sources+['reports/v4/final_results.json','reports/v4/player_guard.json','reports/v4/PROTOCOL.md']:
        destination=directory/'source'/name;destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes((ROOT/name).read_bytes())
    meta={'model_version':'v4-experimental','forecast_file':'v4.json','created_at_utc':now.isoformat(),'gameweek':gw,
          'deadline_utc':deadlines[gw],'season_start_deadline':season,'data_snapshot':str(source.relative_to(ROOT)),
          'data_manifest_sha256':sha(source/'manifest.json'),'availability_observed_at':observed,
          'source_code_sha256':{name:sha(ROOT/name) for name in sources},
          'historical_inputs_sha256':{name:sha(ROOT/name) for name in ['data/prior_2024_25.csv','data/prior_season.csv']},
          'role':'Prospective experimental forecast after reused retrospective confirmation. No manual team adjustments.',
          'limitations':['Retrospective gains are modest; prospective accuracy remains unproven.',
                         'Availability mapping affects player points but is not calibrated.',
                         'Team scorelines do not yet adjust for individual injuries or manager changes.',
                         'One-gameweek forecasts only. Player minutes are not a joint substitution simulation.']}
    meta['files_sha256']={str(p.relative_to(directory)):sha(p) for p in directory.rglob('*') if p.is_file()}
    (directory/'manifest.json').write_text(json.dumps(meta,indent=2))
    (OUT/'latest_freeze.json').write_text(json.dumps({'path':str(directory.relative_to(ROOT))},indent=2))
    verify_v2();print(json.dumps({'freeze':str(directory),'players':len(payloads['v4']['players']),'matches':len(target)},indent=2))
if __name__=='__main__':main()
