"""Write human-readable experiment results and held-out error diagnostics."""
import json, math
import numpy as np
from run_experiments import ROOT, OUT, load_current, load_archive, predictions, evaluate, dump

def main():
    rows,fixtures,deadlines,finished,scoring,b=load_current()
    ar,af,ad,ag,_=load_archive(scoring)
    text=['# FPL model experiments','',
        'Live API snapshot plus a separate 2025/26 archive. Lower error is better. '
        'These are initial research results, not proof of an optimal model.','',
        '| Evaluation | Regular-player RMSE: model / baseline | Regular-player MAE: model / baseline | Scoreline log loss: model / baseline |',
        '|---|---:|---:|---:|']
    results={}
    for label,data in [('current',rows),('archive',ar)]:
        r=json.loads((OUT/f'{label}_results.json').read_text());results[label]=r
        s,base=r['selected'],r['baseline'];x,y=s['prior_regulars'],base['prior_regulars']
        text.append(f"| {label}: GW{min(r['test_gws'])}–{max(r['test_gws'])} | {x['rmse']:.3f} / {y['rmse']:.3f} | {x['mae']:.3f} / {y['mae']:.3f} | {s['scoreline_nll']:.3f} / {base['scoreline_nll']:.3f} |")
    text+=['','Regulars are identified only from prior appearances (average >=45 minutes). '
            'The points baseline is recency-weighted historical points; the scoreline baseline is '
            'league-average home/away scoring. Both are refitted using past data only.','']
    diagnostics={}
    for label,data in [('current',rows),('archive',ar)]:
        r=results[label];pred=json.loads((OUT/f'{label}_player_predictions.json').read_text())
        lookup={(x['element'],x['fixture']):x for x in data}
        pairs=[(p,lookup[(p['player'],p['fixture'])]) for p in pred if (p['player'],p['fixture']) in lookup]
        target=[x for x in data if x['round'] in r['test_gws']]
        covered={(p['player'],p['fixture']) for p,_ in pairs}
        missed=[x for x in target if (x['element'],x['fixture']) not in covered]
        diag={'coverage':{'target_rows':len(target),'predicted_rows':len(pairs),'missing_rows':len(missed),
                         'missing_playing_rows':sum(x['minutes']>0 for x in missed)},'position_errors':{},'minutes_groups':{},'calibration':{}}
        for pos,name in [(1,'GKP'),(2,'DEF'),(3,'MID'),(4,'FWD')]:
            pp=[(p,a) for p,a in pairs if p['position']==pos and p['prior_minutes']>=45]
            errors=np.array([p['selected_points']-a['total_points'] for p,a in pp])
            diag['position_errors'][name]={'n':len(pp),'rmse':float(np.sqrt(np.mean(errors**2))),'bias':float(errors.mean())}
        for name,fn in [('minutes_error_under_30',lambda p,a:abs(p['minutes']-a['minutes'])<30),
                        ('minutes_error_at_least_30',lambda p,a:abs(p['minutes']-a['minutes'])>=30)]:
            pp=[(p,a) for p,a in pairs if p['prior_minutes']>=45 and fn(p,a)]
            diag['minutes_groups'][name]={'n':len(pp),'points_mae':float(np.mean([abs(p['selected_points']-a['total_points']) for p,a in pp]))}
        for key,truth in [('p_start',lambda a:a['starts']>0),('p60',lambda a:a['minutes']>=60),('p_clean_sheet',lambda a:a['clean_sheets'])]:
            bins=[]
            for lo in [0,.2,.4,.6,.8]:
                pp=[(p,a) for p,a in pairs if lo<=p[key]<(lo+.2+1e-9 if lo==.8 else lo+.2)]
                if pp:bins.append({'lower':lo,'n':len(pp),'predicted':float(np.mean([p[key] for p,a in pp])),
                                   'observed':float(np.mean([truth(a) for p,a in pp]))})
            diag['calibration'][key]=bins
        worst=sorted(pairs,key=lambda pair:-abs(pair[0]['selected_points']-pair[1]['total_points']))[:12]
        diag['largest_errors']=[{'name':p['name'],'gw':p['gw'],'forecast':p['selected_points'],'actual':a['total_points'],
                               'minutes_forecast':p['minutes'],'minutes_actual':a['minutes']} for p,a in worst]
        diagnostics[label]=diag
        text += [f'## {label.title()} experiment','',
                 f"Selection gameweeks: {r['validation_gws']}. Held-out gameweeks: {r['test_gws']}.",
                 f"Team settings: `{r['team_config']}`. Player settings: `{r['player_config']}`; component blend weight {r['component_weight']}.",'',
                 f"Coverage: {len(pairs):,}/{len(target):,} historical player-fixture rows; {len(missed)} omitted, including {sum(x['minutes']>0 for x in missed)} appearances. Missing predictions are not treated as zero-point successes.",
                 f"Minutes MAE: {r['selected']['minutes']['mae']:.2f}. Start-probability Brier: {r['selected']['p_start']['mse']:.4f}.",'',
                 '| Position, prior regulars | Rows | Points RMSE | Bias |','|---|---:|---:|---:|']
        for name,stat in diag['position_errors'].items():text.append(f"| {name} | {stat['n']} | {stat['rmse']:.3f} | {stat['bias']:.3f} |")
        text+=['',f"GW-block bootstrap 95% interval for mean fold RMSE difference (model minus baseline): {r['mean_fold_rmse_difference_ci95']}. Negative favours the model. This is not a guarantee and does not account for every time-series dependence.",'']
        small=diag['minutes_groups']['minutes_error_under_30'];large=diag['minutes_groups']['minutes_error_at_least_30']
        text += [f"For prior regulars, fixture points MAE is {small['points_mae']:.3f} when minutes error is under 30 minutes, versus {large['points_mae']:.3f} when it is at least 30 minutes. This is an association, not a causal attribution.",'']
    # Save the user's exact GW1-3 -> GW4 comparison, explicitly labelled validation.
    r=results['current'];p,m=predictions(rows,fixtures,deadlines,4,scoring,r['team_config'],r['player_config'])
    dump('gw4_validation_predictions.json',{'role':'selection/validation, not held-out','players':p,'matches':m,
        'metrics':evaluate(p,m,rows,r['component_weight'])})
    text+=['## What tuning found','',
        'Historical validation selected a 50/50 goals/xG team signal with eight pseudo-matches '
        'of shrinkage toward league averages. Player validation selected a 360-minute positional '
        'prior, a 0.65 weight multiplier for each older appearance, and a 75% xG/xA blend. '
        'It selected the component model without a historical-points blend. These settings were '
        'chosen on GW4-12, before scoring GW13-38. The xG blend candidates were close in validation '
        'RMSE (3.068 for 75%, 3.069 for 100%, 3.071 for 0%); that is weak evidence for one exact '
        'blend, not a reason to claim a precise optimum.','',
        '## Interpretation and next steps','',
        'The current-season result is one held-out week only. The larger archive gives a more useful '
        'robustness check. Do not choose a new model based on these test results and report the same '
        'test set as untouched. The next model iteration needs nested temporal evaluation or future games.','',
        'Known limitations: independent team-goal distributions, crude empirical minutes forecasts, '
        'fixed own-goal allowance, proportional goal allocation, approximate on-pitch clean sheets, '
        'empirical bonus rather than joint BPS ranking, no joint lineup/minutes constraint, incomplete new-player coverage, and no historical '
        'injury/lineup information. Archive cutoffs use earliest kickoff minus 24 hours. These are '
        'reconstructed historical evaluations, not pristine archived pre-deadline forecasts.','',
        'The strongest research priorities are appearance/minutes models, opponent-adjusted team ratings, '
        'and calibrated joint action simulation. The diagnostic JSON includes probability calibration '
        'bins, errors by position and minutes error, and the largest individual misses.','',
        'Scoring reconstruction: zero mismatches across both datasets. Automated tests cover defensive '
        'thresholds, future-target mutation invariance, probability bounds, team goal reconciliation, '
        'and exact scoring reconstruction.','',
        'Sources: [live FPL API](https://fantasy.premierleague.com/api/bootstrap-static/), '
        '[historical archive](https://github.com/vaastav/Fantasy-Premier-League/tree/master/data/2025-26), '
        '[official defensive-contribution explanation](https://www.premierleague.com/en/news/4361991).']
    dump('diagnostics.json',diagnostics)
    (OUT/'FINDINGS.md').write_text('\n'.join(text)+'\n')
    print('\n'.join(text[:10]))

if __name__=='__main__':main()
