"""Fixed development selection and separately reported recent confirmation slices."""
import csv
import datetime as dt
import hashlib
import itertools
import json
import math
from pathlib import Path
import numpy as np
from models.v4 import ContextTeamModel, before
from models.v2 import AdjustedTeamModel
from models.engine import TeamModel
from run_experiments import load_current, load_archive, split
from run_v2 import match_prediction

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'reports/v4'
# Fixed before results. Same score distribution; no mode-diversity objective.
CANDIDATES={f'r{r}_d{d}_x{x}_v{int(v)}':dict(ridge=r,half_days=d,xg_weight=x,venue=v)
            for r,d,x,v in itertools.product([2.,8.],[120.,300.],[0.,.5,1.],[False,True])}


def archive_matches(path,season):
    records={}
    for r in csv.DictReader(open(path)):
        home=r['was_home']=='True';key=int(r['fixture'])
        m=records.setdefault(key,{'id':key,'season':season,'gw':int(r['round']),'kickoff':r['kickoff_time'],
            'hg':int(r['team_h_score']),'ag':int(r['team_a_score']),'hxg':0.,'axg':0.,'finished':True})
        m['home' if home else 'away']=r['team']
        x=r.get('expected_goals')
        if x not in ('',None):m['hxg' if home else 'axg']+=float(x)
    if any('home' not in m or 'away' not in m for m in records.values()):raise ValueError('Missing club identity')
    return list(records.values())


def current_matches(rows,fixtures,bootstrap):
    teams={t['id']:t['name'] for t in bootstrap['teams']};xgs={}
    for r in rows:
        key=r['fixture'],r['team'];xgs[key]=xgs.get(key,0)+float(r.get('expected_goals') or 0)
    return [{'id':f['id'],'season':'2026-27','gw':f['event'],'kickoff':f['kickoff_time'],
        'home':teams[f['team_h']],'away':teams[f['team_a']], 'hg':f['team_h_score'],'ag':f['team_a_score'],
        'hxg':xgs.get((f['id'],f['team_h'])),'axg':xgs.get((f['id'],f['team_a'])),
        'finished':f['finished']} for f in fixtures]


def metrics(rows):
    if not rows:return None
    return {'matches':len(rows),'log_loss':float(np.mean([r['nll'] for r in rows])),
            'brier':float(np.mean([r['brier'] for r in rows])), 'goal_mae':float(np.mean([r['goal_mae'] for r in rows])),
            'mean_draw_probability':float(np.mean([r['draw'] for r in rows])),
            'actual_draw_rate':float(np.mean([r['hg']==r['ag'] for r in rows]))}


def evaluate(model,targets,gw):
    result=[]
    for m in targets:
        h,a,g=model.distribution(m['home'],m['away']);gh,ga=m['hg'],m['ag']
        probs=[float(np.tril(g,-1).sum()),float(np.trace(g)),float(np.triu(g,1).sum())]
        result.append({'season':m['season'],'gw':gw,'fixture':m['id'],'home':m['home'],'away':m['away'],
            'hg':gh,'ag':ga,'home_goals':h,'away_goals':a,'home_win':probs[0],'draw':probs[1],'away_win':probs[2],
            'nll':-math.log(max(1e-15,g[gh,ga])),
            'brier':sum((p-y)**2 for p,y in zip(probs,[gh>ga,gh==ga,gh<ga])),
            'goal_mae':(abs(h-gh)+abs(a-ga))/2})
    return result


class NamedIncumbent:
    def __init__(self,past):
        names={t:i for i,t in enumerate(sorted({m[k] for m in past for k in ('home','away')}))}
        self.names=names
        fixtures=[{'id':i,'event':m['gw'],'team_h':names[m['home']],'team_a':names[m['away']],
            'team_h_score':m['hg'],'team_a_score':m['ag']} for i,m in enumerate(past)]
        rows=[{'fixture':i,'team':names[m[k]],'expected_goals':m[x] if m[x] is not None else m[g]} for i,m in enumerate(past) for k,x,g in [('home','hxg','hg'),('away','axg','ag')]]
        self.model=AdjustedTeamModel(fixtures,rows,ridge=20.,half_life=12.,xg_weight=.5)
    def distribution(self,h,a):return self.model.distribution(self.names.get(h,-1),self.names.get(a,-2))


class LeagueBaseline:
    def __init__(self,past):
        self.model=TeamModel([{'team_h_score':m['hg'],'team_a_score':m['ag'],'id':i,'team_h':m['home'],'team_a':m['away']} for i,m in enumerate(past)],[],prior=1e12)
    def distribution(self,h,a):return self.model.distribution(h,a)


def bootstrap_interval(rows,base):
    groups={}
    for r,b in zip(rows,base):groups.setdefault((r['season'],r['gw']),[]).append(r['nll']-b['nll'])
    values=list(groups.values());rng=np.random.default_rng(20261006)
    draws=[np.mean([v for i in rng.integers(0,len(values),len(values)) for v in values[i]]) for _ in range(3000)]
    return list(map(float,np.quantile(draws,[.025,.975])))


def main():
    OUT.mkdir(exist_ok=True)
    (OUT/'candidates.json').write_text(json.dumps(CANDIDATES,indent=2))
    prior=archive_matches(ROOT/'data/prior_2024_25.csv','2024-25')
    archived=archive_matches(ROOT/'data/prior_season.csv','2025-26')
    rows,fixtures,deadlines,finished,scoring,b=load_current();current=current_matches(rows,fixtures,b)
    seasons=[('2025-26',archived,prior,{gw:(min(m['kickoff'] for m in archived if m['gw']==gw)) for gw in range(1,39)}),
             ('2026-27',current,prior+archived,deadlines)]
    # Historical archive cutoff precedes the first fixture by 24h; no within-GW leakage.
    seasons[0][3].update({gw:(dt.datetime.fromisoformat(v.replace('Z','+00:00'))-dt.timedelta(hours=24)).isoformat() for gw,v in seasons[0][3].items()})
    outcomes={name:[] for name in CANDIDATES};baselines={'incumbent':[],'league':[]}
    for season,matches,history,cuts in seasons:
        gws=range(4,39) if season=='2025-26' else sorted(finished)
        for gw in gws:
            target=[m for m in matches if m['gw']==gw and m['finished'] and m['hg'] is not None]
            if not target:continue
            cutoff=cuts[gw];past=before(matches,cutoff);training=before(history+matches,cutoff)
            for name,config in CANDIDATES.items():
                outcomes[name]+=evaluate(ContextTeamModel(training,cutoff,**config),target,gw)
            baselines['incumbent']+=evaluate(NamedIncumbent(past),target,gw)
            baselines['league']+=evaluate(LeagueBaseline(past),target,gw)
            print(season,'GW',gw,flush=True)
    dev=lambda rows:[r for r in rows if r['season']=='2025-26' and r['gw']<=30]
    confirm=lambda rows:[r for r in rows if r['season']=='2026-27' or r['gw']>=31]
    selected=min(CANDIDATES,key=lambda n:metrics(dev(outcomes[n]))['log_loss'])
    selected_rows=outcomes[selected];new=metrics(confirm(selected_rows));old=metrics(confirm(baselines['incumbent']))
    slices={season:{'candidate':metrics([r for r in confirm(selected_rows) if r['season']==season]),
                    'incumbent':metrics([r for r in confirm(baselines['incumbent']) if r['season']==season])} for season in ['2025-26','2026-27']}
    accepted=new['log_loss']<=old['log_loss']*.99 and new['brier']<=old['brier']+.01 and all(v['candidate']['log_loss']<=v['incumbent']['log_loss']+.03 for v in slices.values())
    result={'selected':selected,'configuration':CANDIDATES[selected],'accepted_match_gate':bool(accepted),
        'development':{n:metrics(dev(rs)) for n,rs in outcomes.items()},
        'confirmation':{'candidate':new,**{n:metrics(confirm(rs)) for n,rs in baselines.items()}},'slices':slices,
        'nll_difference_gw_bootstrap_ci95':bootstrap_interval(confirm(selected_rows),confirm(baselines['incumbent'])),
        'folds':[{'season':s,'gw':g,'candidate':metrics([r for r in selected_rows if r['season']==s and r['gw']==g]),
            'incumbent':metrics([r for r in baselines['incumbent'] if r['season']==s and r['gw']==g])} for s,g in sorted({(r['season'],r['gw']) for r in selected_rows})],
        'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'data/prior_2024_25.csv',ROOT/'data/prior_season.csv',ROOT/'models/v4.py',ROOT/'run_v4.py']},
        'role':'chronological retrospective development/confirmation; not untouched prospective evidence'}
    (OUT/'results.json').write_text(json.dumps(result,indent=2))
    (OUT/'confirmation_predictions.json').write_text(json.dumps({'candidate':confirm(selected_rows),'incumbent':confirm(baselines['incumbent'])},indent=2))
    print(json.dumps({k:v for k,v in result.items() if k not in ('development','folds','source_sha256')},indent=2))

if __name__=='__main__':main()
