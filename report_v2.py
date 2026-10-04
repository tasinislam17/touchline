"""Produce V2 findings and forecast coverage from saved experiment outputs."""
import json
from collections import Counter
import numpy as np
from run_experiments import ROOT, load_current, load_archive

OUT=ROOT/'reports/v2'

def main():
    current=load_current();archive=load_archive(current[4])
    lines=['# Iteration 2: forecasts, validation and remaining gaps','',
           'V1 code and reports remain unchanged. V2 uses a refreshed, timestamped live API snapshot. '
           'These results are chronological development evidence, not a newly untouched historical test: '
           'the archive was inspected in iteration 1. Future saved forecasts provide the independent check.','',
           '## Results','',
           '| Dataset / metric | V1 | V2 | Relative error reduction |','|---|---:|---:|---:|']
    results={}
    for label in ('archive','current'):
        r=json.loads((OUT/f'{label}_results.json').read_text());results[label]=r
        name='2025/26 GW13–38' if label=='archive' else '2026/27 GW5 (one week)'
        for metric,path in [('Points RMSE, prior regulars',('prior_regulars','rmse')),
                            ('Minutes MAE, all covered players',('minutes','mae')),
                            ('Starting-probability Brier',('p_start','mse')),
                            ('Scoreline log loss',('scoreline_nll',))]:
            a=r['v1'];b=r['v2']
            for k in path:a=a[k];b=b[k]
            lines.append(f'| {name}: {metric} | {a:.4f} | {b:.4f} | {(a-b)/a*100:.2f}% |')
    lines+=['','Lower is better. Player points are aggregated across fixtures in double gameweeks. '
            '“Prior regulars” average at least 45 minutes before the predicted gameweek. Comparisons '
            'use the same player-fixture support. Probability Brier scores are squared probability errors.','',
            '## What changed','',
            '- **Minutes:** regularized logistic models for starting, coming on if benched, and reaching '
            '60 minutes conditional on starting/coming on. Their probabilities form a coherent minutes '
            'mixture. Features include recent minutes and starts, start/absence streaks, position, '
            'rest, recent workload and time since the last appearance.',
            '- **Team goals:** a regularized Poisson attack/defence model adjusts for opponent strength, '
            'home advantage and time decay. Candidate low-score corrections redistribute probability '
            'among 0–0, 0–1, 1–0 and 1–1 without changing expected goals or clean-sheet marginals.',
            '- **Player points:** predicted minutes feed the existing action-rate model. We compare '
            'full learned minutes, a 50% blend and unchanged V1 minutes. Bonus and defensive-contribution '
            'models remain approximate; they were not silently replaced by untested complex models.',
            '- **Little/no history:** prospective forecasts use the actual timestamped roster and '
            'positional priors. Historical tests do not invent pre-deadline registrations for debutants.','',
            '## Selection protocol','',
            'Five team configurations, three learned minutes configurations with two blend weights, '
            'and the V1 incumbent. For each outer gameweek, candidate team selection uses earlier '
            'scoreline log loss and player selection uses earlier regular-player points RMSE. '
            'Candidate fits and features exclude future labels and matches completing after the cutoff. '
            'The archive outer replay covers GW13–38, with inner validation beginning at GW4. '
            'Current-season minutes models can also train on earlier-season observations; no current '
            'future outcomes are included.',
            '', 'Archived fixture schedules/deadlines remain reconstructed: the archive cutoff is '
            'earliest kickoff minus 24 hours. This is conservative but not a complete historical '
            'as-of data system. Candidate architecture was informed by earlier results, so nested '
            'selection does not eliminate researcher hindsight.','',
            '## Diagnostics','']
    diagnostics={}
    for label,data in [('archive',archive[0]),('current',current[0])]:
        r=results[label];pred=json.loads((OUT/f'{label}_players.json').read_text())
        lookup={(x['element'],x['fixture']):x for x in data}
        pairs=[(p,lookup[p['player'],p['fixture']]) for p in pred if (p['player'],p['fixture']) in lookup]
        d={'position':{},'calibration':{}}
        for pos,name in [(1,'GKP'),(2,'DEF'),(3,'MID'),(4,'FWD')]:
            subset=[(p,a) for p,a in pairs if p['position']==pos and p['prior_minutes']>=45]
            err=np.array([p['points']-a['total_points'] for p,a in subset])
            d['position'][name]={'n':len(err),'fixture_points_rmse':float(np.sqrt(np.mean(err**2))),'bias':float(err.mean())}
        for key,truth in [('p_start',lambda a:a['starts']>0),('p60',lambda a:a['minutes']>=60)]:
            bins=[]
            for lo in (0,.2,.4,.6,.8):
                subset=[(p,a) for p,a in pairs if lo<=p[key]<(lo+.2+1e-8 if lo==.8 else lo+.2)]
                if subset:bins.append({'lower':lo,'n':len(subset),'predicted':float(np.mean([p[key] for p,a in subset])),
                                       'observed':float(np.mean([truth(a) for p,a in subset]))})
            d['calibration'][key]=bins
        diagnostics[label]=d
        c=r['coverage']
        lines += [f"**{label.title()}:** {c['covered_actual_rows']:,}/{c['target_rows']:,} target player-fixture rows covered; "
                  f"{c['omitted_appearances']} actual appearances remain outside historical coverage. "
                  'Prospective fallback support does not retroactively repair that gap.','',
                  f"Team selections: `{r['team_selection_counts']}`. Minutes selections: `{r['player_selection_counts']}`.",'',
                  f"Moving four-gameweek block bootstrap interval for mean fold RMSE difference (V2 − V1): "
                  f"{r['mean_fold_rmse_difference_block_ci95']}. Negative favours V2; this interval does not account for architecture-selection hindsight.",'']
    r=results['archive'];ab=r['ablations']
    lines += ['**Ablation:** keeping V1 minutes while using the selected team model gives points RMSE '
              f"{ab['v1']['prior_regulars']['rmse']:.4f}, compared with {r['v1']['prior_regulars']['rmse']:.4f} "
              'for the original V1 system. The points improvement comes from the minutes model; '
              'the new team model is not independently a demonstrated player-points improvement.','',
              'The scoreline gain is very small. Keep the team model experimental and compare it '
              'prospectively. Forwards and rare high-point games remain difficult; forecasting an '
              'expected mean does not imply forecasting each haul.','', '## Prospective forecasts','']
    freeze=ROOT/json.loads((OUT/'latest_freeze.json').read_text())['path']
    manifest=json.loads((freeze/'manifest.json').read_text())
    lines += [f"Saved **GW{manifest['gameweek']}** forecasts at `{freeze.relative_to(ROOT)}`.",
              f"Creation: `{manifest['created_at_utc']}`. Deadline: `{manifest['deadline_utc']}`.",'',
              'Files contain the V1 forecast, chronologically selected V2 forecast, and a fixed '
              'minutes challenger. Each freeze records source-code and input hashes and forecast '
              'checksums. Later runs create a new directory rather than replacing old forecasts.','']
    for label in ('v1','selected_v2','minutes_challenger'):
        payload=json.loads((freeze/f'{label}.json').read_text())
        lines.append(f"- {label}: {len(payload['players'])} player-fixture predictions, {len(payload['matches'])} matches; settings `{payload['configuration']}`.")
    lines += ['','These are early forecasts, not final deadline forecasts. Current availability '
              'status and news are attached but do not yet adjust probabilities. No deadline refresh '
              'or monitoring task has been scheduled.','',
              'After the GW is finished and data-checked:','',
              '```sh','python fetch_data.py','python score_freeze.py','```','',
              'The scorer verifies saved forecast hashes and scores without refitting. It reports '
              'coverage and common-support comparisons. If results are incomplete, it returns a '
              'waiting status. Refreshing before the deadline and rerunning V2 creates another '
              'separately timestamped early forecast.','',
              '## Remaining work','',
              '1. Capture and model point-in-time injuries, suspensions and predicted lineups.',
              '2. Enforce team lineup/minutes consistency, and improve transfer/debutant priors.',
              '3. Build joint bonus and defensive-action simulation, then calibrate player-point distributions.',
              '4. Test across more seasons and prospective gameweeks before promoting the scoreline model.',
              '', 'Method reference: [Dixon and Coles (1997)](https://academic.oup.com/jrsssc/article-abstract/46/2/265/6990546). '
              'The V2 team model is a ridge-regularized variant with fixed candidate low-score corrections; '
              'it is not a reproduction of that paper’s full estimation procedure.']
    (OUT/'diagnostics.json').write_text(json.dumps(diagnostics,indent=2))
    (OUT/'FINDINGS.md').write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines[:18]))

if __name__=='__main__':main()
