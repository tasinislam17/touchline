"""Bounded V5 selection using new completed gameweeks without confirmation leakage."""
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from models.v2 import MinutesModel,make_minutes_training
from models.v5 import FeatureTeamModelV5,training_rows
from run_experiments import ROOT,load_archive,load_current,split,evaluate as player_metrics
from run_v2 import combine_minutes,forecast_players,match_prediction
from run_v4 import archive_matches,current_matches,metrics

OUT=ROOT/'reports/v5';OUT.mkdir(exist_ok=True)
BASE={'ridge':20.,'half_days':365.,'long_window':30,'recent_window':5,'venue_window':15,
      'goals_features':True,'rest':False,'ppg':False,'rho':-.15}


def changed(**values):return dict(BASE,**values)


MATCH_CANDIDATES={
    'v4':BASE,
    'ridge10':changed(ridge=10.),'ridge40':changed(ridge=40.),
    'decay180':changed(half_days=180.),'decay730':changed(half_days=730.),
    'recent3':changed(recent_window=3),'recent8':changed(recent_window=8),
    'long20':changed(long_window=20),'long50':changed(long_window=50),
    'venue10':changed(venue_window=10),'venue20':changed(venue_window=20),
    'xg_only':changed(goals_features=False),'rest':changed(rest=True),'ppg':changed(ppg=True),
    'rho10':changed(rho=-.10),'rho20':changed(rho=-.20),
}
MINUTES_CANDIDATES={f'r{ridge}_h{half}':{'ridge':float(ridge),'half_life':float(half)}
                    for ridge in (3,10,20) for half in (4,8,16,26)}


def structure(config):
    return tuple(config[key] for key in ('long_window','recent_window','venue_window','goals_features','rest','ppg'))


def score_match(model,match):
    home,away,grid=model.distribution(match['home'],match['away'],match['kickoff']);hg,ag=match['hg'],match['ag']
    outcomes=[float(np.tril(grid,-1).sum()),float(np.trace(grid)),float(np.triu(grid,1).sum())]
    return {'season':match['season'],'gw':match['gw'],'fixture':match['id'],'home':match['home'],'away':match['away'],
            'hg':hg,'ag':ag,'home_goals':home,'away_goals':away,'home_win':outcomes[0],'draw':outcomes[1],
            'away_win':outcomes[2],'nll':-math.log(max(float(grid[hg,ag]),1e-15)),
            'brier':sum((p-y)**2 for p,y in zip(outcomes,[hg>ag,hg==ag,hg<ag])),
            'goal_mae':(abs(home-hg)+abs(away-ag))/2}


def model_for(config,all_matches,cutoff,trainings,season):
    return FeatureTeamModelV5(all_matches,cutoff,trainings[structure(config)],season,config)


def numeric_matches(config,all_matches,trainings,season,gw,target,deadline,bootstrap,include_grid=False):
    names={team['id']:team['name'] for team in bootstrap['teams']}
    model=model_for(config,all_matches,deadline,trainings,season)
    result=[]
    for fixture in target:
        class Bound:
            def distribution(self,home,away):return model.distribution(names[home],names[away],fixture['kickoff_time'])
        result.append(match_prediction(Bound(),fixture,gw,include_grid=include_grid))
    return result


def paired_bootstrap(candidate,base):
    differences=np.asarray([row['nll']-other['nll'] for row,other in zip(candidate,base)])
    rng=np.random.default_rng(20261111)
    draws=[float(np.mean(differences[rng.integers(0,len(differences),len(differences))])) for _ in range(4000)]
    return list(map(float,np.quantile(draws,[.025,.975])))


def aggregate_players(predictions,matches,rows):return player_metrics(predictions,matches,rows)


def main():
    prior=archive_matches(ROOT/'data/prior_2024_25.csv','2024-25')
    archive=archive_matches(ROOT/'data/prior_season.csv','2025-26')
    rows,fixtures,deadlines,finished,scoring,bootstrap=load_current();current=current_matches(rows,fixtures,bootstrap)
    for match in current:
        if match['gw'] in deadlines:match['deadline']=deadlines[match['gw']]
    all_matches=prior+archive+current
    structural={structure(config):config for config in MATCH_CANDIDATES.values()}
    trainings={key:training_rows(all_matches,config) for key,config in structural.items()}
    match_rows={name:[] for name in MATCH_CANDIDATES}
    targets=[('2025-26',archive,range(4,31)),('2026-27',current,range(1,11))]
    for season,matches,gws in targets:
        for gw in gws:
            target=[match for match in matches if match['gw']==gw and match['finished'] and match['hg'] is not None]
            if not target:continue
            if season=='2026-27':cutoff=deadlines[gw]
            else:
                # Training rows complete three hours after kickoff; archive decisions use the round's conservative 24h cutoff.
                import datetime as dt
                from models.v4 import utc
                cutoff=(utc(min(match['kickoff'] for match in target))-dt.timedelta(hours=24)).isoformat()
            for name,config in MATCH_CANDIDATES.items():
                model=model_for(config,all_matches,cutoff,trainings,season)
                match_rows[name]+=[score_match(model,match) for match in target]
    def subset(name,season,gws):return [row for row in match_rows[name] if row['season']==season and row['gw'] in gws]
    selection={}
    for name in MATCH_CANDIDATES:
        archive_metric=metrics(subset(name,'2025-26',range(4,31)))
        current_metric=metrics(subset(name,'2026-27',range(1,9)))
        selection[name]={'archive':archive_metric,'current':current_metric,
                         'score':(archive_metric['log_loss']+current_metric['log_loss'])/2}
    selected_match=min(selection,key=lambda name:selection[name]['score'])
    confirmation={name:metrics(subset(name,'2026-27',range(9,11))) for name in MATCH_CANDIDATES}
    selected_confirm=subset(selected_match,'2026-27',range(9,11));base_confirm=subset('v4','2026-27',range(9,11))
    per_gw={gw:{'candidate':metrics([row for row in selected_confirm if row['gw']==gw]),
                'v4':metrics([row for row in base_confirm if row['gw']==gw])} for gw in (9,10)}
    match_accepted=(selection[selected_match]['score']<=selection['v4']['score'] and
                    confirmation[selected_match]['log_loss']<confirmation['v4']['log_loss'] and
                    confirmation[selected_match]['brier']<=confirmation['v4']['brier']+.01 and
                    all(value['candidate']['log_loss']<=value['v4']['log_loss']+.08 for value in per_gw.values()))

    archive_rows,archive_fixtures,archive_deadlines=load_archive(scoring)[:3]
    minutes_training=combine_minutes(make_minutes_training(archive_rows,archive_fixtures,archive_deadlines),
                                     make_minutes_training(rows,fixtures,deadlines))
    player_config=json.loads((ROOT/'reports/current_results.json').read_text())['player_config']
    player_predictions={name:[] for name in MINUTES_CANDIDATES};base_match_predictions=[]
    target_matches=[]
    for gw in range(6,11):
        train,past,target=split(rows,fixtures,deadlines,gw)
        matches=numeric_matches(BASE,all_matches,trainings,'2026-27',gw,target,deadlines[gw],bootstrap)
        target_matches+=matches
        for name,config in MINUTES_CANDIDATES.items():
            minute_model=MinutesModel(minutes_training,gw,**config)
            player_predictions[name]+=forecast_players(train,past,target,gw,scoring,player_config,matches,minute_model=minute_model,blend=1.)
    def player_subset(name,gws):return [p for p in player_predictions[name] if p['gw'] in gws]
    minute_development={name:aggregate_players(player_subset(name,range(6,9)),[],rows) for name in MINUTES_CANDIDATES}
    selected_minutes=min(MINUTES_CANDIDATES,key=lambda name:minute_development[name]['prior_regulars']['rmse'])
    minute_confirmation={name:aggregate_players(player_subset(name,range(9,11)),[],rows) for name in MINUTES_CANDIDATES}
    minute_candidate=minute_confirmation[selected_minutes];minute_base=minute_confirmation['r3_h8']
    minutes_accepted=(minute_development[selected_minutes]['prior_regulars']['rmse']<minute_development['r3_h8']['prior_regulars']['rmse'] and
                      minute_candidate['prior_regulars']['rmse']<=minute_base['prior_regulars']['rmse']+.02 and
                      minute_candidate['p_start']['mse']<=minute_base['p_start']['mse']+.005 and
                      minute_candidate['p60']['mse']<=minute_base['p60']['mse']+.005)

    production_match=selected_match if match_accepted else 'v4';production_minutes=selected_minutes if minutes_accepted else 'r3_h8'
    combined={name:[] for name in ('candidate','v4')};combined_matches={name:[] for name in combined}
    for gw in (9,10):
        train,past,target=split(rows,fixtures,deadlines,gw)
        for label,match_name,minute_name in [('candidate',production_match,production_minutes),('v4','v4','r3_h8')]:
            matches=numeric_matches(MATCH_CANDIDATES[match_name],all_matches,trainings,'2026-27',gw,target,deadlines[gw],bootstrap)
            minute_model=MinutesModel(minutes_training,gw,**MINUTES_CANDIDATES[minute_name])
            combined[label]+=forecast_players(train,past,target,gw,scoring,player_config,matches,minute_model=minute_model,blend=1.)
            combined_matches[label]+=matches
    keys={(p['player'],p['fixture']) for p in combined['candidate']}&{(p['player'],p['fixture']) for p in combined['v4']}
    combined_metrics={label:aggregate_players([p for p in values if (p['player'],p['fixture']) in keys],combined_matches[label],rows)
                      for label,values in combined.items()}
    combined_accepted=combined_metrics['candidate']['prior_regulars']['rmse']<=combined_metrics['v4']['prior_regulars']['rmse']+.02
    if not combined_accepted:
        production_match='v4';production_minutes='r3_h8'
    frozen=json.loads(sorted((ROOT/'reports/v4/evaluations').glob('gw6_*.json'))[-1].read_text())
    source=ROOT/(ROOT/'data/latest.txt').read_text().strip()
    result={'protocol':'reports/v5/PROTOCOL.md','completed_gameweeks':finished,'frozen_gw6':frozen['results'],
            'input_snapshot':str(source.relative_to(ROOT)),'data_manifest_sha256':hashlib.sha256((source/'manifest.json').read_bytes()).hexdigest(),
            'match':{'selected':selected_match,'accepted':bool(match_accepted),'production':production_match,
                     'selection':selection,'confirmation':confirmation,'per_gw_confirmation':per_gw,
                     'nll_difference_match_bootstrap_ci95':paired_bootstrap(selected_confirm,base_confirm)},
            'minutes':{'selected':selected_minutes,'accepted':bool(minutes_accepted),'production':production_minutes,
                       'development':minute_development,'confirmation':minute_confirmation},
            'combined_confirmation':combined_metrics,'combined_player_gate':bool(combined_accepted),
            'production_config':{'match':MATCH_CANDIDATES[production_match],
                                 'minutes':MINUTES_CANDIDATES[production_minutes],
                                 'player':player_config},
            'limitations':['GW9-10 contain only 20 confirmation matches.','Confirmation follows researcher inspection of earlier rounds.',
                           'Historical availability and manager changes are not backfilled.','Prospective GW11 evidence is still required.'],
            'source_sha256':{str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in
                             [ROOT/'models/v5.py',ROOT/'run_v5.py',ROOT/'reports/v5/PROTOCOL.md',
                              ROOT/'data/prior_2024_25.csv',ROOT/'data/prior_season.csv']}}
    (OUT/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False))
    (OUT/'confirmation_predictions.json').write_text(json.dumps({'candidate':selected_confirm,'v4':base_confirm},indent=2))
    print(json.dumps({'match':result['match']|{'selection':'omitted','confirmation':'omitted'},
                      'minutes':{k:v for k,v in result['minutes'].items() if k not in ('development','confirmation')},
                      'combined_confirmation':combined_metrics,'production_config':result['production_config']},indent=2))


if __name__=='__main__':main()
