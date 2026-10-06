"""Separate bounded feature-family experiment; confirmation reuse is disclosed."""
import datetime as dt
import json
from run_v4 import ROOT,OUT,archive_matches,current_matches,metrics,evaluate,bootstrap_interval
from run_experiments import load_current
from models.v4 import utc
from models.v4_features import FeatureTeamModel,training_rows


def main():
    prior=archive_matches(ROOT/'data/prior_2024_25.csv','2024-25');arch=archive_matches(ROOT/'data/prior_season.csv','2025-26')
    rows,fixtures,deadlines,finished,_,b=load_current();cur=current_matches(rows,fixtures,b)
    for m in cur:
        if m['gw'] in deadlines:m['deadline']=deadlines[m['gw']]
    allmatches=prior+arch+cur;training=training_rows(allmatches)
    configs={f'r{r}_table{int(t)}':{'ridge':r,'standings':t} for r in [1.,5.,20.] for t in [False,True]}
    forecasts={name:[] for name in configs}
    for season,matches,gws in [('2025-26',arch,range(4,39)),('2026-27',cur,finished)]:
        for gw in gws:
            target=[m for m in matches if m['gw']==gw and m['finished'] and m['hg'] is not None]
            if not target:continue
            cutoff=deadlines[gw] if season=='2026-27' else (utc(min(m['kickoff'] for m in matches if m['gw']==gw))-dt.timedelta(hours=24)).isoformat()
            for name,config in configs.items():
                model=FeatureTeamModel(allmatches,cutoff,training,season,**config)
                forecasts[name]+=evaluate(model,target,gw)
    dev=lambda rs:[r for r in rs if r['season']=='2025-26' and r['gw']<=30]
    conf=lambda rs:[r for r in rs if r['season']=='2026-27' or r['gw']>=31]
    selected=min(configs,key=lambda n:metrics(dev(forecasts[n]))['log_loss']);pred=conf(forecasts[selected])
    base=json.loads((OUT/'confirmation_predictions.json').read_text())['incumbent'];new=metrics(pred);old=metrics(base)
    slices={s:{'candidate':metrics([r for r in pred if r['season']==s]),'incumbent':metrics([r for r in base if r['season']==s])} for s in ['2025-26','2026-27']}
    accepted=new['log_loss']<=old['log_loss']*.99 and new['brier']<=old['brier']+.01 and all(v['candidate']['log_loss']<=v['incumbent']['log_loss']+.03 for v in slices.values())
    result={'selected':selected,'configuration':configs[selected],'accepted_match_gate':bool(accepted),
        'development':{n:metrics(dev(rs)) for n,rs in forecasts.items()},'confirmation':{'candidate':new,'incumbent':old},
        'slices':slices,'nll_difference_gw_bootstrap_ci95':bootstrap_interval(pred,base),
        'role':'retrospective exploratory confirmation after multiple model families; prospective evidence pending'}
    (OUT/'feature_results.json').write_text(json.dumps(result,indent=2));(OUT/'feature_predictions.json').write_text(json.dumps({'candidate':pred,'incumbent':base},indent=2))
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
