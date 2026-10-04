"""Produce availability-aware forecasts without changing V1/V2 artifacts."""
import copy
import datetime as dt
import hashlib
import json
import pathlib
from availability import connect, import_snapshots, at_or_before, history, iso
from models.v2 import MinutesModel, PlayerModelV2, make_minutes_training
from models.v3 import role_moments, adjust_team, score_players
from run_experiments import ROOT, load_current, load_archive, split
from run_v2 import TEAM_CANDIDATES, MINUTE_CANDIDATES, team_forecasts, combine_minutes

OUT=ROOT/'reports/v3';OUT.mkdir(exist_ok=True)

def verify_v2():
    for name,digest in json.loads((OUT/'v2_manifest.json').read_text())['sha256'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:raise ValueError('Protected V2 artifact changed: '+name)

def main():
    verify_v2()
    rows,fixtures,deadlines,finished,scoring,b=load_current()
    gw=max(finished)+1;now=dt.datetime.now(dt.timezone.utc)
    if now>=dt.datetime.fromisoformat(deadlines[gw].replace('Z','+00:00')):raise ValueError('Target deadline has passed; cannot freeze as pre-deadline')
    source=ROOT/(ROOT/'data/latest.txt').read_text().strip();source_manifest=json.loads((source/'manifest.json').read_text())
    observed=iso(source_manifest['retrieved_at']);season=b['events'][0]['deadline_time']
    with connect() as db:
        import_snapshots(db);observation=at_or_before(db,season,observed)
        if observation is None:raise ValueError('No availability snapshot at forecast input time')
        histories={p['id']:history(db,season,p['id']) for p in b['elements']}
        snapshots=db.execute('SELECT COUNT(*) FROM snapshots WHERE season=?',(season,)).fetchone()[0]
    roster={p['id']:p for p in b['elements']}
    for pid,p in observation['players'].items():
        if pid in roster:roster[pid].update(p)
    archive=load_archive(scoring)
    training=combine_minutes(make_minutes_training(archive[0],archive[1],archive[2]),make_minutes_training(rows,fixtures,deadlines))
    selection=json.loads((ROOT/'reports/v2/current_results.json').read_text())['next_selection']
    config=json.loads((ROOT/'reports/current_results.json').read_text())
    name=selection['player']
    if name=='v1':
        key='r20_h8';blend=0.
    else:
        key,suffix=name.rsplit('_',1);blend=1. if suffix=='full' else .5
    minutes=MinutesModel(training,gw,**MINUTE_CANDIDATES[key])
    train,past,target=split(rows,fixtures,deadlines,gw)
    model=PlayerModelV2(train,scoring,minutes,**config['player_config']);model.minute_blend=blend
    matches=team_forecasts(train,past,target,gw,config['team_config'],include_grid=True)[selection['team']]
    matchmap={m['fixture']:m for m in matches};last_team={}
    for r in train:last_team[r['team']]=max(last_team.get(r['team'],''),r['kickoff_time'])
    payloads={name:{'configuration':{'parent':selection,'availability':name!='v2_same_snapshot','lineup':name=='v3'},
                    'players':[],'matches':matches} for name in ['v2_same_snapshot','availability_only','v3']}
    checks=[]
    for f in target:
        m=matchmap[f['id']]
        for team,lam,opp in [(f['team_h'],m['home_goals'],m['away_goals']),(f['team_a'],m['away_goals'],m['home_goals'])]:
            members=[p for p in roster.values() if p['team']==team]
            model.context={p['id']:dict(kickoff=f['kickoff_time'],home=team==f['team_h'],team_last_kickoff=last_team.get(team)) for p in members}
            raw=[];roles={}
            for p in members:
                r=model.raw(p['id'],p['element_type']);h=model.hist.get(p['id'],[])
                r.update(gw=gw,fixture=f['id'],team=team,name=p['web_name'],price=p['now_cost']/10,
                         prior_minutes=sum(x['minutes'] for x in h)/len(h) if h else 0,history_matches=len(h),cold_start=not bool(h))
                raw.append(r);roles[p['id']]=role_moments(model,p['id'],p['element_type'])
            base=score_players(raw,lam,opp,scoring)
            availability,_=adjust_team(raw,roles,roster,lam,opp,scoring,constrain=False)
            v3,audit=adjust_team(raw,roles,roster,lam,opp,scoring,constrain=True)
            audit.update(team=team,fixture=f['id']);checks.append(audit)
            for name,players in [('v2_same_snapshot',base),('availability_only',availability),('v3',v3)]:payloads[name]['players']+=players
    now=dt.datetime.now(dt.timezone.utc)
    if now>=dt.datetime.fromisoformat(deadlines[gw].replace('Z','+00:00')):raise ValueError('Deadline passed during fitting; refusing pre-deadline freeze')
    stamp=now.strftime('%Y%m%dT%H%M%S%fZ');directory=OUT/'freezes'/f'gw{gw}_{stamp}';directory.mkdir(parents=True)
    for name,payload in payloads.items():(directory/f'{name}.json').write_text(json.dumps(payload,indent=2,allow_nan=False))
    sourcefiles=['models/v3.py','run_v3.py','availability.py','models/v2.py','models/engine.py','run_experiments.py','run_v2.py']
    for name in sourcefiles:
        destination=directory/'source'/name;destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_bytes((ROOT/name).read_bytes())
    manifest={'created_at_utc':now.isoformat(),'gameweek':gw,'deadline_utc':deadlines[gw],'season_start_deadline':season,
              'data_snapshot':str(source.relative_to(ROOT)),'availability_observed_at':observed,'availability_snapshot_id':observation['snapshot_id'],
              'data_manifest_sha256':hashlib.sha256((source/'manifest.json').read_bytes()).hexdigest(),
              'source_code_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sourcefiles},
              'files_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.glob('*.json')},
              'role':'experimental early prospective forecast; availability mapping not yet calibrated',
              'policy':{'valid_next_round_percentage':'availability multiplier/cap, not start probability','unselectable_removed':0,
                        'unavailable_missing_percentage':0,'doubtful_missing_percentage':.75,'other_missing_percentage':1,
                        'lineup':'one goalkeeper and ten outfield starter marginals','infeasible':'raise; never relax injury caps silently',
                        'scorelines':'inherited unchanged from V2; no injury team-strength effect'}}
    (directory/'manifest.json').write_text(json.dumps(manifest,indent=2))
    (OUT/'latest_freeze.json').write_text(json.dumps({'path':str(directory.relative_to(ROOT))},indent=2))
    base={(p['player'],p['fixture']):p for p in payloads['v2_same_snapshot']['players']}
    avail={(p['player'],p['fixture']):p for p in payloads['availability_only']['players']}
    players=[]
    for p in payloads['v3']['players']:
        k=p['player'],p['fixture'];x=copy.deepcopy(p)
        x['v2']={field:base[k][field] for field in ['points','minutes','p_start','p_play','p60','components']}
        x['availability_only']={field:avail[k][field] for field in ['points','minutes','p_start']}
        x['delta_points']=p['points']-base[k]['points'];x['delta_minutes']=p['minutes']-base[k]['minutes']
        x['availability_history']=[h for h in histories[p['player']] if h['observed_at']<=observed][-10:]
        players.append(x)
    review={'meta':manifest,'players':players,'matches':[{k:v for k,v in m.items() if k!='score_grid'} for m in matches],
            'teams':b['teams'],'fixtures':[{'id':f['id'],'kickoff_time':f['kickoff_time'],'team_h':f['team_h'],'team_a':f['team_a']} for f in target],
            'lineup_checks':checks,'availability_snapshots':snapshots,
            'limitations':['Availability percentages are an uncalibrated model input, not starting probabilities.',
                           'Only GK/outfield competition is constrained; detailed roles and formations are not inferred from FPL positions.',
                           'Individual minutes are not a joint substitution/90-minute simulation.',
                           'Persistent injuries can already affect historical minutes; the availability multiplier may double-count some of that effect.',
                           'Scorelines are inherited from V2 and do not yet respond to injury news.',
                           'No retrospective injury backtest: observations begin when collected, not at news_added.']}
    (OUT/'review.json').write_text(json.dumps(review,indent=2,allow_nan=False))
    (OUT/'lineup_checks.json').write_text(json.dumps(checks,indent=2))
    excluded=[p for p in players if p['availability']['factor']==0]
    assert all(abs(p['points'])<1e-8 and p['minutes']==0 for p in excluded)
    assert all(abs(c['starter_sum']-11)<1e-7 and abs(c['goalkeeper_starters']-1)<1e-7 for c in checks)
    findings=['# V3: availability and lineup review','',
        f"Created {now.isoformat()} for GW{gw}. Input observed {observed}.",'',
        f"Generated {len(players)} player-fixture forecasts and {len(matches)} matches. {len(excluded)} players receive zero availability under the documented policy.",
        f"All {len(checks)} team-fixture checks satisfy 11 expected starters, including exactly one goalkeeper.",'',
        'The same-snapshot V2 comparator and availability-only ablation isolate input changes from the lineup adjustment. Original V2 artifacts remain unchanged.',
        '', '## Interpretation','',
        'Official fields and news text are preserved as source facts. A next-round percentage is used as an availability multiplier/cap, not a calibrated chance of starting. Missing-value fallbacks are explicit. News text is displayed, not used to infer diagnoses or parse return dates. A positive next-round percentage takes precedence over an injury/suspension status unless the player is removed or unselectable.',
        '', 'Current flags have not been applied to old games. There is no claimed historical V3 accuracy improvement; it must be evaluated prospectively. Compare V3 with the same-snapshot V2 forecast after results are final.',
        '', '## Limits','']+['- '+x for x in review['limitations']]+['',
        f"{snapshots} timestamped availability snapshots are stored in data/availability.sqlite. Import is idempotent; observations are never backdated to news_added.",'',
        '## Commands','', '```sh','python fetch_data.py','python run_v3.py','python build_review.py',
        'python serve_review.py','```','',
        'For lightweight availability capture only: `python availability.py --fetch`. It does not refresh model forecasts. No recurring capture task is scheduled.',
        '',f"Freeze: `{directory.relative_to(ROOT)}`.",
        '', 'After refreshing finished/data-checked results, run `python score_v3.py` to compare the saved variants without refitting.',
        '', 'Source: [official live FPL API](https://fantasy.premierleague.com/api/bootstrap-static/).']
    (OUT/'FINDINGS.md').write_text('\n'.join(findings)+'\n')
    verify_v2();print(json.dumps({'freeze':str(directory),'players':len(players),'excluded':len(excluded),'team_checks':len(checks),'availability_snapshots':snapshots},indent=2))

if __name__=='__main__':main()
