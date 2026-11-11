"""Reproducible expanding-window experiments, with frozen chronological selection."""
import csv, datetime, hashlib, itertools, json, math, pathlib
import numpy as np
from models.engine import TeamModel, PlayerModel, defensive_award, score_actual

ROOT=pathlib.Path(__file__).resolve().parent
OUT=ROOT/'reports'; OUT.mkdir(exist_ok=True)

def dump(name, value):
    (OUT/name).write_text(json.dumps(value, indent=2, allow_nan=False))

def load_current():
    directory=ROOT/(ROOT/'data/latest.txt').read_text().strip()
    b=json.loads((directory/'bootstrap.json').read_text())
    fixtures=json.loads((directory/'fixtures.json').read_text()); fmap={f['id']:f for f in fixtures}
    rows=[]
    for p in b['elements']:
        for r in json.loads((directory/f"player_{p['id']}.json").read_text())['history']:
            f=fmap[r['fixture']]
            rows.append(dict(r,position=p['element_type'],team=f['team_h'] if r['was_home'] else f['team_a'],name=p['web_name']))
    deadlines={e['id']:e['deadline_time'] for e in b['events']}
    finished=[e['id'] for e in b['events'] if e['finished'] and e['data_checked']]
    return rows, fixtures, deadlines, finished, b['game_config']['scoring'], b

def load_archive(scoring):
    raw=list(csv.DictReader((ROOT/'data/prior_season.csv').open()))
    positions={'GK':1,'GKP':1,'DEF':2,'MID':3,'FWD':4}
    rows=[]; fixtures={}
    for item in raw:
        r={}
        for k,v in item.items():
            try: r[k]=float(v) if '.' in v else int(v)
            except (ValueError,TypeError): r[k]=v
        r['was_home']=item['was_home']=='True';r['position']=positions[item['position']]
        rows.append(r)
        f=fixtures.setdefault(r['fixture'],{'id':r['fixture'],'event':r['round'],'kickoff_time':r['kickoff_time'],
            'team_h_score':r['team_h_score'],'team_a_score':r['team_a_score'],'finished':True})
        f['team_a' if r['was_home'] else 'team_h']=r['opponent_team']
    for r in rows:
        f=fixtures[r['fixture']];r['team']=f['team_h'] if r['was_home'] else f['team_a']
    deadlines={}
    for gw in sorted(set(r['round'] for r in rows)):
        earliest=min(r['kickoff_time'] for r in rows if r['round']==gw)
        dt=datetime.datetime.fromisoformat(earliest.replace('Z','+00:00'))-datetime.timedelta(hours=24)
        deadlines[gw]=dt.isoformat().replace('+00:00','Z')
    return rows,list(fixtures.values()),deadlines,sorted(deadlines),scoring

def split(rows, fixtures, deadlines, gw):
    # Add three hours to kickoff as a conservative match-completion boundary.
    def before(f):
        if not f.get('kickoff_time') or f.get('event') is None: return False
        end=datetime.datetime.fromisoformat(f['kickoff_time'].replace('Z','+00:00'))+datetime.timedelta(hours=3)
        return f['event']<gw and end<datetime.datetime.fromisoformat(deadlines[gw].replace('Z','+00:00')) and f.get('finished')
    past=[f for f in fixtures if before(f)]
    ids={f['id'] for f in past}
    return [r for r in rows if r['fixture'] in ids],past,[f for f in fixtures if f.get('event')==gw]

def predictions(rows,fixtures,deadlines,gw,scoring,team_config,player_config):
    train,past,target=split(rows,fixtures,deadlines,gw)
    team=TeamModel(past,train,**team_config); player=PlayerModel(train,scoring,**player_config)
    latest={}
    for r in sorted(train,key=lambda x:x['kickoff_time']): latest[r['element']]=r
    result=[]; matches=[]
    for f in target:
        h,a,grid=team.distribution(f['team_h'],f['team_a'])
        score=np.unravel_index(np.argmax(grid),grid.shape)
        match={'gw':gw,'fixture':f['id'],'home':f['team_h'],'away':f['team_a'],'home_goals':h,'away_goals':a,
               'mode_scoreline':list(map(int,score)),'home_win':float(np.tril(grid,-1).sum()),'draw':float(np.trace(grid)),
               'away_win':float(np.triu(grid,1).sum()),'home_cs':math.exp(-a),'away_cs':math.exp(-h),
               'actual_home':f.get('team_h_score'),'actual_away':f.get('team_a_score')}
        if f.get('team_h_score') is not None:
            gh,ga=f['team_h_score'],f['team_a_score']
            match['nll']=h-gh*math.log(h)+math.lgamma(gh+1)+a-ga*math.log(a)+math.lgamma(ga+1)
        matches.append(match)
        for t,lam,opp in [(f['team_h'],h,a),(f['team_a'],a,h)]:
            members=[(p,r['position']) for p,r in latest.items() if r['team']==t]
            for pred in player.predict_fixture(members,lam,opp):
                pred.update(gw=gw,fixture=f['id'],team=t,name=latest[pred['player']]['name'])
                hist=player.hist[pred['player']]
                pred['prior_minutes']=sum(r['minutes'] for r in hist)/len(hist)
                result.append(pred)
    return result,matches

def evaluate(preds,matches,rows,alpha=1):
    actual={(r['element'],r['fixture']):r for r in rows}
    pairs=[(p,actual[(p['player'],p['fixture'])]) for p in preds if (p['player'],p['fixture']) in actual]
    metrics={'player_fixture_rows':len(pairs),'matches':len(matches)}
    for name,subset in [('all',pairs),('prior_regulars',[(p,r) for p,r in pairs if p['prior_minutes']>=45])]:
        if not subset: continue
        # Sum player-fixture predictions for doubles before player-GW point metrics.
        totals={}
        for p,r in subset:
            k=(p['gw'],p['player']);v=totals.setdefault(k,[0,0])
            v[0]+=alpha*p['points']+(1-alpha)*p['baseline'];v[1]+=r['total_points']
        errors=np.array([a-b for a,b in totals.values()])
        metrics[name]={'n':len(totals),'mae':float(np.abs(errors).mean()),'rmse':float(np.sqrt((errors**2).mean())),
                       'bias':float(errors.mean())}
    for key,truth in [('minutes',lambda r:r['minutes']),('goals',lambda r:r['goals_scored']),('assists',lambda r:r['assists']),
                      ('p_start',lambda r:r['starts']>0),('p60',lambda r:r['minutes']>=60),
                      ('p_defcon',lambda r:defensive_award(r,r['position'])),('p_clean_sheet',lambda r:r['clean_sheets'])]:
        errors=np.array([p[key]-truth(r) for p,r in pairs])
        metrics[key]={'mae':float(np.abs(errors).mean()),'mse':float((errors**2).mean())}
    scored=[m for m in matches if 'nll' in m]
    if scored:
        metrics['scoreline_nll']=float(np.mean([m['nll'] for m in scored]))
        metrics['goal_mae']=float(np.mean([abs(m['home_goals']-m['actual_home'])+abs(m['away_goals']-m['actual_away']) for m in scored])/2)
        metrics['result_brier']=float(np.mean([sum((m[k]-int(y))**2 for k,y in zip(['home_win','draw','away_win'],
            [m['actual_home']>m['actual_away'],m['actual_home']==m['actual_away'],m['actual_home']<m['actual_away']])) for m in scored]))
    return metrics

def select(rows,fixtures,deadlines,scoring,validation,label):
    team_trials=[]
    for prior,xg_weight in itertools.product([2,8,1000000],[0,.5,1]):
        config=dict(prior=prior,xg_weight=xg_weight); ms=[]
        for gw in validation:
            train,past,target=split(rows,fixtures,deadlines,gw);model=TeamModel(past,train,**config)
            for f in target:
                if f['team_h_score'] is None:continue
                h,a=model.predict(f['team_h'],f['team_a']);gh,ga=f['team_h_score'],f['team_a_score']
                ms.append(h-gh*math.log(h)+math.lgamma(gh+1)+a-ga*math.log(a)+math.lgamma(ga+1))
        team_trials.append({'config':config,'nll':float(np.mean(ms))})
    tc=min(team_trials,key=lambda x:x['nll'])['config'];trials=[]
    for prior,recent,xg_weight in itertools.product([90,360],[.65,1.0],[0,.75,1]):
        pc=dict(prior=prior,recent=recent,xg_weight=xg_weight);ps=[];ms=[]
        for gw in validation:
            p,m=predictions(rows,fixtures,deadlines,gw,scoring,tc,pc);ps+=p;ms+=m
        for alpha in [0,.5,1]:
            ev=evaluate(ps,ms,rows,alpha)
            trials.append({'config':pc,'alpha':alpha,'rmse':ev['prior_regulars']['rmse'],'mae':ev['prior_regulars']['mae']})
    best=min(trials,key=lambda x:x['rmse'])
    dump(label+'_selection.json',{'validation_gws':validation,'team_trials':team_trials,'player_trials':trials,'selected_team':tc,'selected_player':best})
    return tc,best['config'],best['alpha']

def run_season(rows,fixtures,deadlines,finished,scoring,validation,test,label):
    mismatches=[{'player':r['element'],'fixture':r['fixture'],'actual':r['total_points'],'reconstructed':score_actual(r,r['position'],scoring)}
                for r in rows if abs(score_actual(r,r['position'],scoring)-r['total_points'])>.01]
    dump(label+'_scoring_audit.json',{'rows':len(rows),'mismatches':len(mismatches),'examples':mismatches[:30]})
    tc,pc,alpha=select(rows,fixtures,deadlines,scoring,validation,label)
    allp=[];allm=[];folds=[];baseline_m=[]
    for gw in test:
        p,m=predictions(rows,fixtures,deadlines,gw,scoring,tc,pc)
        _,bm=predictions(rows,fixtures,deadlines,gw,scoring,{'prior':1000000,'xg_weight':0},pc)
        allp+=p;allm+=m;baseline_m+=bm
        folds.append({'gw':gw,'selected':evaluate(p,m,rows,alpha),'rolling_points_baseline':evaluate(p,bm,rows,0)})
        print(label,'GW',gw,'RMSE',round(folds[-1]['selected']['prior_regulars']['rmse'],3),flush=True)
    summary={'validation_gws':validation,'test_gws':test,'team_config':tc,'player_config':pc,'component_weight':alpha,
             'selected':evaluate(allp,allm,rows,alpha),'baseline':evaluate(allp,baseline_m,rows,0),'folds':folds}
    dump(label+'_results.json',summary);dump(label+'_match_predictions.json',allm)
    actual={(r['element'],r['fixture']):r for r in rows}
    for p in allp:
        p['selected_points']=alpha*p['points']+(1-alpha)*p['baseline']
        p['actual']=actual.get((p['player'],p['fixture']),{}).get('total_points')
    dump(label+'_player_predictions.json',allp)
    # Paired uncertainty over GW blocks, not artificially independent player rows.
    differences=np.array([f['selected']['prior_regulars']['rmse']-f['rolling_points_baseline']['prior_regulars']['rmse'] for f in folds])
    rng=np.random.default_rng(42)
    boot=np.mean(rng.choice(differences,(2000,len(differences))),axis=1)
    summary['mean_fold_rmse_difference_ci95']=list(map(float,np.quantile(boot,[.025,.975]))) if len(folds)>1 else None
    dump(label+'_results.json',summary)
    return tc,pc,alpha,summary

def main():
    rows,fixtures,deadlines,finished,scoring,b=load_current()
    current=run_season(rows,fixtures,deadlines,finished,scoring,[4],[g for g in finished if g>=5],'current')
    ar,af,ad,ag,asc=load_archive(scoring)
    archive=run_season(ar,af,ad,ag,asc,list(range(4,13)),list(range(13,39)),'archive')
    gw=max(finished)+1
    p,m=predictions(rows,fixtures,deadlines,gw,scoring,*current[:2])
    for x in p:x['selected_points']=current[2]*x['points']+(1-current[2])*x['baseline']
    dump('next_gameweek_players.json',sorted(p,key=lambda x:-x['selected_points']));dump('next_gameweek_matches.json',m)
    dump('provenance.json',{'current_snapshot':(ROOT/'data/latest.txt').read_text(),
        'archive_url':'https://raw.githubusercontent.com/vaastav/Fantasy-Premier-League/master/data/2025-26/gws/merged_gw.csv',
        'archive_sha256':hashlib.sha256((ROOT/'data/prior_season.csv').read_bytes()).hexdigest(),
        'archive_cutoff':'earliest kickoff minus 24 hours; conservative proxy, not archived deadline',
        'selection':'current GW4 -> test GW5; archive GW4-12 -> frozen parameters GW13-38'})

if __name__=='__main__':main()
