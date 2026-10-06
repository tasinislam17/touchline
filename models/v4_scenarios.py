"""Audited, opt-in sensitivity scenarios. Never fitted or applied to baseline forecasts."""
import math
from models.v4 import utc


def scenario_rates(home,away,fixture,rates,events,as_of):
    """Attack/concession multipliers are subjective assumptions, not learned effects.

    Positive concession multipliers weaken defence. Confidence is recorded only;
    it is not silently converted into a statistical weight. Expired events fail.
    """
    h,a=rates;seen=set();audit=[]
    for event in events:
        required={'id','fixture','team','kind','reason','source','observed_at','expires_at','attack_multiplier','concession_multiplier','confidence'}
        if not required<=event.keys():raise ValueError('Incomplete scenario provenance')
        if event['id'] in seen:raise ValueError('Duplicate scenario event')
        seen.add(event['id'])
        if not utc(event['observed_at'])<=utc(as_of)<utc(event['expires_at']):raise ValueError('Future or expired scenario')
        if event['kind'] not in ('injury','manager_change','other') or event['confidence'] not in ('low','medium','high'):
            raise ValueError('Unknown scenario category')
        if not all(isinstance(event[k],str) and event[k].strip() for k in ('id','reason','source')):raise ValueError('Missing scenario evidence')
        if event['fixture']!=fixture:continue
        if event['team'] not in (home,away):raise ValueError('Scenario team not in fixture')
        attack=event['attack_multiplier'];concede=event['concession_multiplier']
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not .7<=v<=1.3 for v in (attack,concede)):
            raise ValueError('Scenario multipliers must be between 0.7 and 1.3')
        if event['team']==home:h*=attack;a*=concede
        else:a*=attack;h*=concede
        audit.append(dict(event))
    if not all(.7<=x/y<=1.3 for x,y in zip((h,a),rates)):raise ValueError('Combined scenario exceeds sensitivity bounds')
    return {'home_goals':h,'away_goals':a,'baseline_home_goals':rates[0],'baseline_away_goals':rates[1],
            'scenario_only':True,'calibrated':False,'events':audit}
