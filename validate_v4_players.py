"""Same-input player regression guard: no hindsight availability overlay."""
import json
from run_experiments import ROOT,load_current,load_archive,split,evaluate
from run_v2 import combine_minutes,MINUTE_CANDIDATES,forecast_players,match_prediction
from models.v2 import MinutesModel,make_minutes_training,AdjustedTeamModel
from models.v4_features import FeatureTeamModel,training_rows
from run_v4 import archive_matches,current_matches

class ClubAdapter:
    def __init__(self,model,bootstrap):
        self.model=model;self.names={t['id']:t['name'] for t in bootstrap['teams']}
    def distribution(self,home,away):return self.model.distribution(self.names[home],self.names[away])

def load_match_history(rows,fixtures,deadlines,b):
    cur=current_matches(rows,fixtures,b)
    for m in cur:
        if m['gw'] in deadlines:m['deadline']=deadlines[m['gw']]
    return archive_matches(ROOT/'data/prior_2024_25.csv','2024-25')+archive_matches(ROOT/'data/prior_season.csv','2025-26')+cur

def main():
    rows,fixtures,deadlines,finished,scoring,b=load_current()
    arch=load_archive(scoring)
    minutes_training=combine_minutes(make_minutes_training(arch[0],arch[1],arch[2]),make_minutes_training(rows,fixtures,deadlines))
    history=load_match_history(rows,fixtures,deadlines,b);training=training_rows(history)
    config=json.loads((ROOT/'reports/v4/final_results.json').read_text())['configuration']
    player_config=json.loads((ROOT/'reports/current_results.json').read_text())['player_config']
    totals={'candidate':[],'incumbent':[]};folds=[]
    for gw in finished:
        if gw<2:continue
        train,past,target=split(rows,fixtures,deadlines,gw)
        minutes=MinutesModel(minutes_training,gw,**MINUTE_CANDIDATES['r3_h8'])
        models={'candidate':ClubAdapter(FeatureTeamModel(history,deadlines[gw],training,'2026-27',**config),b),
                'incumbent':AdjustedTeamModel(past,train,ridge=20.,half_life=12.,rho=0.)}
        predictions={}
        for name,model in models.items():
            matches=[match_prediction(model,f,gw) for f in target]
            predictions[name]=forecast_players(train,past,target,gw,scoring,player_config,matches,minute_model=minutes,blend=1.)
        keys=set.intersection(*[{(p['player'],p['fixture']) for p in ps} for ps in predictions.values()])
        fold={'gw':gw}
        for name,ps in predictions.items():
            ps=[p for p in ps if (p['player'],p['fixture']) in keys];totals[name]+=ps
            fold[name]=evaluate(ps,[],rows)
        folds.append(fold)
    result={name:evaluate(ps,[],rows) for name,ps in totals.items()}
    result['accepted_player_gate']=result['candidate']['prior_regulars']['rmse']<=result['incumbent']['prior_regulars']['rmse']+.02
    result['folds']=folds
    result['limitations']=['GW1 excluded: no current player history.','Common historical roster only; no hindsight injury flags.','Tests the team-rate change; prospective availability overlay remains uncalibrated.']
    (ROOT/'reports/v4/player_guard.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='folds'},indent=2))
if __name__=='__main__':main()
