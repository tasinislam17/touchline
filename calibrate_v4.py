"""Round 2: fixed-base low-score dependence selected only on development folds."""
import datetime as dt
import hashlib
import json
from pathlib import Path
from run_v4 import archive_matches,current_matches,metrics,evaluate,bootstrap_interval,ROOT,OUT
from run_experiments import load_current
from models.v4 import ContextTeamModel


def main():
    first=json.loads((OUT/'round1/results.json').read_text());config=first['configuration']
    prior=archive_matches(ROOT/'data/prior_2024_25.csv','2024-25');arch=archive_matches(ROOT/'data/prior_season.csv','2025-26')
    rows,fixtures,deadlines,finished,_,b=load_current();current=current_matches(rows,fixtures,b)
    candidates={rho:[] for rho in [-.20,-.15,-.10,-.05,0.,.05]}
    for season,matches,history,gws in [('2025-26',arch,prior,range(4,39)),('2026-27',current,prior+arch,finished)]:
        for gw in gws:
            target=[m for m in matches if m['gw']==gw and m['finished'] and m['hg'] is not None]
            if not target:continue
            cutoff=deadlines[gw] if season=='2026-27' else (dt.datetime.fromisoformat(min(m['kickoff'] for m in matches if m['gw']==gw).replace('Z','+00:00'))-dt.timedelta(hours=24)).isoformat()
            model=ContextTeamModel(history+matches,cutoff,**config)
            for rho in candidates:
                model.rho=rho;candidates[rho]+=evaluate(model,target,gw)
    dev=lambda rs:[r for r in rs if r['season']=='2025-26' and r['gw']<=30]
    conf=lambda rs:[r for r in rs if r['season']=='2026-27' or r['gw']>=31]
    rho=min(candidates,key=lambda x:metrics(dev(candidates[x]))['log_loss']);selected=conf(candidates[rho])
    base=json.loads((OUT/'confirmation_predictions.json').read_text())['incumbent'];new=metrics(selected);old=metrics(base)
    slices={s:{'candidate':metrics([r for r in selected if r['season']==s]),'incumbent':metrics([r for r in base if r['season']==s])} for s in ['2025-26','2026-27']}
    accepted=new['log_loss']<=old['log_loss']*.99 and new['brier']<=old['brier']+.01 and all(v['candidate']['log_loss']<=v['incumbent']['log_loss']+.03 for v in slices.values())
    result={'configuration':dict(config,rho=rho),'accepted_match_gate':bool(accepted),'confirmation':{'candidate':new,'incumbent':old},'slices':slices,
        'development_rho_trials':{str(k):metrics(dev(v)) for k,v in candidates.items()},
        'nll_difference_gw_bootstrap_ci95':bootstrap_interval(selected,base),
        'role':'second-round retrospective confirmation; reused confirmation, not independent proof',
        'source_sha256':{'models/v4.py':hashlib.sha256((ROOT/'models/v4.py').read_bytes()).hexdigest()}}
    (OUT/'corrected_results.json').write_text(json.dumps(result,indent=2))
    (OUT/'corrected_predictions.json').write_text(json.dumps({'candidate':selected,'incumbent':base},indent=2))
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
