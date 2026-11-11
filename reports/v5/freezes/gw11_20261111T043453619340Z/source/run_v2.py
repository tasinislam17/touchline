"""V2 rolling model selection. Writes only reports/v2 and prospective freezes."""
import datetime as dt
import hashlib
import json
import math
import pathlib
from collections import Counter
import numpy as np
from models.engine import TeamModel, PlayerModel
from models.v2 import AdjustedTeamModel, MinutesModel, PlayerModelV2, make_minutes_training
from run_experiments import ROOT, load_current, load_archive, split, evaluate

OUT=ROOT/'reports/v2';OUT.mkdir(exist_ok=True)
TEAM_CANDIDATES={
    'v1':None,
    'adjusted_r8_h12':dict(ridge=8.,half_life=12.,rho=0.),
    'adjusted_r20_h12':dict(ridge=20.,half_life=12.,rho=0.),
    'adjusted_r8_h38':dict(ridge=8.,half_life=38.,rho=0.),
    'adjusted_r8_h12_dc':dict(ridge=8.,half_life=12.,rho=-.08),
}
MINUTE_CANDIDATES={
    'v1':None,
    'r3_h8':dict(ridge=3.,half_life=8.),
    'r20_h8':dict(ridge=20.,half_life=8.),
    'r20_h26':dict(ridge=20.,half_life=26.),
}
VARIANTS=['v1']+[name+suffix for name in MINUTE_CANDIDATES if name!='v1' for suffix in ('_full','_half')]

def save(name,value):
    (OUT/name).write_text(json.dumps(value,indent=2,allow_nan=False))

def manifest_hash():
    paths=['models/v2.py','run_v2.py','models/engine.py','run_experiments.py']
    return {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}

def verify_v1():
    original=json.loads((OUT/'v1_manifest.json').read_text())['sha256']
    for p,digest in original.items():
        if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=digest:raise ValueError('V1 changed: '+p)

def match_prediction(model,f,gw,include_grid=False):
    h,a,grid=model.distribution(f['team_h'],f['team_a'])
    top=np.argsort(grid.ravel())[-5:][::-1]
    result={'gw':gw,'fixture':f['id'],'home':f['team_h'],'away':f['team_a'],
            'home_goals':h,'away_goals':a,'mode_scoreline':list(map(int,np.unravel_index(top[0],grid.shape))),
            'top_scorelines':[{'home':int(i//26),'away':int(i%26),'probability':float(grid.ravel()[i])} for i in top],
            'home_win':float(np.tril(grid,-1).sum()),'draw':float(np.trace(grid)),'away_win':float(np.triu(grid,1).sum()),
            'home_cs':float(grid[:,0].sum()),'away_cs':float(grid[0,:].sum()),
            'actual_home':f.get('team_h_score'),'actual_away':f.get('team_a_score')}
    if f.get('team_h_score') is not None:
        gh,ga=f['team_h_score'],f['team_a_score']
        result['nll']=-math.log(max(float(grid[gh,ga]),1e-15))
    if include_grid:result['score_grid']=grid.tolist()
    return result

def team_forecasts(train,past,target,gw,base_config,include_grid=False):
    result={}
    for name,config in TEAM_CANDIDATES.items():
        model=TeamModel(past,train,**base_config) if config is None else AdjustedTeamModel(past,train,**config)
        result[name]=[match_prediction(model,f,gw,include_grid=include_grid) for f in target]
    return result

def forecast_players(train,past,target,gw,scoring,config,matches,minute_model=None,blend=1.,roster=None):
    player=PlayerModel(train,scoring,**config) if minute_model is None else PlayerModelV2(train,scoring,minute_model,**config)
    latest={};last_team={}
    for r in sorted(train,key=lambda r:r['kickoff_time']):
        latest[r['element']]=r;last_team[r['team']]=r['kickoff_time']
    if roster is not None:
        # Allowed only for current prospective snapshots, never retrospective labels.
        latest={p['id']:{'element':p['id'],'position':p['element_type'],'name':p['web_name'],'team':p['team'],
                         'status':p.get('status'),'news':p.get('news','')} for p in roster}
    mmap={m['fixture']:m for m in matches};result=[]
    for f in target:
        m=mmap[f['id']]
        for t,lam,opp in [(f['team_h'],m['home_goals'],m['away_goals']),(f['team_a'],m['away_goals'],m['home_goals'])]:
            members=[(p,r['position']) for p,r in latest.items() if r['team']==t]
            if minute_model is not None:
                player.minute_blend=blend
                player.context={p:dict(kickoff=f['kickoff_time'],home=t==f['team_h'],team_last_kickoff=last_team.get(t)) for p,_ in members}
            for pred in player.predict_fixture(members,lam,opp):
                hist=player.hist.get(pred['player'],[])
                pred.update(gw=gw,fixture=f['id'],team=t,name=latest[pred['player']]['name'],
                            prior_minutes=sum(r['minutes'] for r in hist)/len(hist) if hist else 0,
                            history_matches=len(hist),cold_start=not bool(hist))
                if roster is not None:
                    pred['availability_status']=latest[pred['player']]['status']
                    pred['availability_news']=latest[pred['player']]['news']
                    pred['availability_adjusted']=False
                result.append(pred)
    return result

def choose_team(history):
    if not history:return 'v1'
    return min(TEAM_CANDIDATES,key=lambda name:np.mean([m['nll'] for fold in history for m in fold['teams'][name]]))

def choose_player(history):
    if not history:return 'v1'
    return min(VARIANTS,key=lambda name:sum(f['player_metrics'][name]['prior_regulars']['rmse']**2*f['player_metrics'][name]['prior_regulars']['n'] for f in history)
               /sum(f['player_metrics'][name]['prior_regulars']['n'] for f in history))

def common_comparison(preds,base,matches,base_matches,rows):
    keys={(p['player'],p['fixture']) for p in preds}&{(p['player'],p['fixture']) for p in base}
    return {'v2':evaluate([p for p in preds if (p['player'],p['fixture']) in keys],matches,rows),
            'v1':evaluate([p for p in base if (p['player'],p['fixture']) in keys],base_matches,rows)}

def combine_minutes(archive,current):
    data={k:np.concatenate([archive[k],current[k]]) for k in ('x','y','position','completed')}
    data['gw']=np.concatenate([archive['gw']-38,current['gw']])
    data['deadlines']=current['deadlines']
    return data

def run_season(label,rows,fixtures,deadlines,scoring,gws,base_team,base_player,training,outer_start):
    history=[];all_pred=[];all_base=[];all_matches=[];all_base_matches=[];ablation={name:[] for name in VARIANTS}
    fold_reports=[]
    for gw in gws:
        train,past,target=split(rows,fixtures,deadlines,gw)
        teams=team_forecasts(train,past,target,gw,base_team)
        # Selection is completed before recording the current fold's outcomes.
        selected_team=choose_team(history);selected_player=choose_player(history)
        models={name:MinutesModel(training,gw,**config) for name,config in MINUTE_CANDIDATES.items() if config is not None}
        variants={'v1':forecast_players(train,past,target,gw,scoring,base_player,teams[selected_team])}
        for name,model in models.items():
            for suffix,blend in [('_full',1.),('_half',.5)]:
                variants[name+suffix]=forecast_players(train,past,target,gw,scoring,base_player,teams[selected_team],model,blend)
        baseline=forecast_players(train,past,target,gw,scoring,base_player,teams['v1'])
        metrics={name:evaluate(p,teams[selected_team],rows) for name,p in variants.items()}
        entry={'gw':gw,'teams':teams,'player_metrics':metrics,'selected_team':selected_team,'selected_player':selected_player,
               'inner_gws':[f['gw'] for f in history]}
        if gw>=outer_start:
            chosen=variants[selected_player];comparison=common_comparison(chosen,baseline,teams[selected_team],teams['v1'],rows)
            fold_reports.append({'gw':gw,'selected_team':selected_team,'selected_player':selected_player,'inner_gws':entry['inner_gws'],**comparison})
            all_pred+=chosen;all_base+=baseline;all_matches+=teams[selected_team];all_base_matches+=teams['v1']
            for name,p in variants.items():ablation[name]+=p
            print(f"{label} GW{gw}: {selected_team}/{selected_player}; RMSE {comparison['v2']['prior_regulars']['rmse']:.3f} vs {comparison['v1']['prior_regulars']['rmse']:.3f}",flush=True)
        history.append(entry)
    overall=common_comparison(all_pred,all_base,all_matches,all_base_matches,rows)
    lookup={(r['element'],r['fixture']):r for r in rows}
    for p in all_pred:
        r=lookup.get((p['player'],p['fixture']),{})
        p['actual_points']=r.get('total_points');p['actual_minutes']=r.get('minutes')
    targetrows=[r for r in rows if r['round'] in [f['gw'] for f in fold_reports]]
    covered={(p['player'],p['fixture']) for p in all_pred}
    omitted=[r for r in targetrows if (r['element'],r['fixture']) not in covered]
    diff=np.array([f['v2']['prior_regulars']['rmse']-f['v1']['prior_regulars']['rmse'] for f in fold_reports])
    ci=None
    if len(diff)>1:
        # Moving blocks preserve short-run serial dependence better than individual rows.
        rng=np.random.default_rng(42);blocks=[diff[i:i+4] for i in range(len(diff)-3)]
        draws=[]
        for _ in range(2000):
            sampled=np.concatenate([blocks[i] for i in rng.integers(0,len(blocks),math.ceil(len(diff)/4))])[:len(diff)]
            draws.append(sampled.mean())
        ci=list(map(float,np.quantile(draws,[.025,.975])))
    result={'label':label,'role':'nested chronological development replay; archive previously inspected',
            'outer_gws':[f['gw'] for f in fold_reports],**overall,'folds':fold_reports,
            'mean_fold_rmse_difference_block_ci95':ci,
            'coverage':{'target_rows':len(targetrows),'covered_actual_rows':len(targetrows)-len(omitted),
                        'omitted_rows':len(omitted),'omitted_appearances':sum(r['minutes']>0 for r in omitted)},
            'team_selection_counts':dict(Counter(f['selected_team'] for f in fold_reports)),
            'player_selection_counts':dict(Counter(f['selected_player'] for f in fold_reports)),
            'ablations':{name:evaluate(p,all_matches,rows) for name,p in ablation.items()},
            'next_selection':{'team':choose_team(history),'player':choose_player(history)}}
    save(label+'_results.json',result);save(label+'_selection_trace.json',history)
    save(label+'_players.json',all_pred);save(label+'_matches.json',all_matches)
    return result

def freeze_current(rows,fixtures,deadlines,finished,scoring,b,training,result,base_team,base_player):
    gw=max(finished)+1;train,past,target=split(rows,fixtures,deadlines,gw)
    if dt.datetime.now(dt.timezone.utc)>=dt.datetime.fromisoformat(deadlines[gw].replace('Z','+00:00')):
        raise ValueError('Cannot create a pre-deadline freeze after the gameweek deadline')
    teams=team_forecasts(train,past,target,gw,base_team,include_grid=True);selection=result['next_selection']
    chosen=selection['player'];team=selection['team']
    # Freeze a learned challenger even if chronological selection retains the incumbent.
    challenger='r20_h8_half'
    names={'v1':'v1','selected_v2':chosen,'minutes_challenger':challenger}
    output={};models={}
    for label,name in names.items():
        if name=='v1':model=None;blend=1.
        else:
            key,suffix=name.rsplit('_',1);blend=1. if suffix=='full' else .5
            if key not in models:models[key]=MinutesModel(training,gw,**MINUTE_CANDIDATES[key])
            model=models[key]
        mt=teams['v1'] if label=='v1' else teams[team]
        output[label]={'configuration':{'team':'v1' if label=='v1' else team,'player':name},
                       'players':forecast_players(train,past,target,gw,scoring,base_player,mt,model,blend,roster=b['elements']),
                       'matches':mt}
    # Guarantee every registered player has a prospective fallback, even when the
    # selected historical variant is the incumbent and previously returned None.
    fallback_model=MinutesModel(training,gw,**MINUTE_CANDIDATES['r20_h8'])
    fallback=forecast_players(train,past,target,gw,scoring,base_player,teams[team],fallback_model,.5,roster=b['elements'])
    for label in ('selected_v2',):
        present={(p['player'],p['fixture']) for p in output[label]['players']}
        for p in fallback:
            if (p['player'],p['fixture']) not in present:
                p['fallback_reason']='no historical appearances';output[label]['players'].append(p)
    stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    directory=OUT/'freezes'/f'gw{gw}_{stamp}';directory.mkdir(parents=True)
    for label,payload in output.items():
        (directory/f'{label}.json').write_text(json.dumps(payload,indent=2,allow_nan=False))
    source=ROOT/(ROOT/'data/latest.txt').read_text().strip()
    metadata={'created_at_utc':stamp,'gameweek':gw,'deadline_utc':deadlines[gw],
              'season_start_deadline':b['events'][0]['deadline_time'],
              'role':'early pre-deadline research forecast; not final deadline forecast',
              'data_snapshot':str(source.relative_to(ROOT)),'source_code_sha256':manifest_hash(),
              'data_manifest_sha256':hashlib.sha256((source/'manifest.json').read_bytes()).hexdigest(),
              'files_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.glob('*.json')},
              'limitations':['No injury adjustments; statuses are attached for review.','Historical bonus/action models retained.','No joint lineup constraint.']}
    (directory/'manifest.json').write_text(json.dumps(metadata,indent=2))
    save('latest_freeze.json',{'path':str(directory.relative_to(ROOT))})
    print('Frozen',directory,flush=True)

def main():
    verify_v1()
    save('protocol.json',{'created_at':dt.datetime.now(dt.timezone.utc).isoformat(),'team_candidates':TEAM_CANDIDATES,
        'minutes_candidates':MINUTE_CANDIDATES,'blends':[1,.5],'outer_archive_gws':list(range(13,39)),
        'inner':'expanding earlier GW4+; team selected by log loss, player by regular-player points RMSE',
        'current_minutes_training':'prior-season minutes features plus earlier current-season features; no future labels',
        'historical_reuse':'Previously inspected archive; nested replay reduces selection leakage but does not erase researcher hindsight.',
        'source_code_sha256':manifest_hash()})
    rows,fixtures,deadlines,finished,scoring,b=load_current()
    ar,af,ad,ag,_=load_archive(scoring)
    at=make_minutes_training(ar,af,ad)
    archive=json.loads((ROOT/'reports/archive_results.json').read_text())
    run_season('archive',ar,af,ad,scoring,range(4,39),archive['team_config'],archive['player_config'],at,13)
    ct=combine_minutes(at,make_minutes_training(rows,fixtures,deadlines))
    current=json.loads((ROOT/'reports/current_results.json').read_text())
    result=run_season('current',rows,fixtures,deadlines,scoring,[g for g in finished if g>=4],
                      current['team_config'],current['player_config'],ct,5)
    freeze_current(rows,fixtures,deadlines,finished,scoring,b,ct,result,current['team_config'],current['player_config'])
    verify_v1()

if __name__=='__main__':main()
