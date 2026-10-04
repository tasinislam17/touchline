"""Uncalibrated availability overlay and feasible starter marginals for V2.

This model does not infer injury diagnoses from text and does not claim to be a
complete formation/lineup simulator. It constrains one GK and ten outfield starters.
"""
import copy
import math
import numpy as np
from models.engine import POSITIONS, poisson
from models.v2 import minute_features, sigmoid

class LineupInfeasible(ValueError):pass

def availability_assumption(player):
    status=player.get('status');chance=player.get('chance_of_playing_next_round')
    if player.get('removed') is True or player.get('can_select') is False:
        q,reason=0.,'Not selectable or removed in the source snapshot.'
    elif isinstance(chance,(int,float)) and not isinstance(chance,bool) and math.isfinite(chance) and 0<=chance<=100:
        q,reason=chance/100.,'Next-round API percentage used as a model availability factor; not a calibrated starting probability.'
    elif status in ('i','s','u'):
        q,reason=0.,'Flagged unavailable with no usable next-round percentage; conservative zero-availability assumption.'
    elif status=='d':
        q,reason=.75,'Doubtful with no usable percentage; assumed 75% availability, not an official percentage.'
    else:
        q,reason=1.,'No usable next-round restriction; assume available. This is not a guarantee of playing.'
    return {'factor':q,'reason':reason,'calibrated':False,'source_status':status,
            'source_next_round_percent':chance,'source_news':player.get('news',''),
            'source_news_added':player.get('news_added'),'source_can_select':player.get('can_select')}

def project_starters(base,capacity,target):
    """Minimum shared log-odds shift under per-player availability caps."""
    base=np.asarray(base,float);capacity=np.asarray(capacity,float)
    if np.any(~np.isfinite(base)) or np.any(~np.isfinite(capacity)) or np.any(capacity<0) or np.any(capacity>1):
        raise ValueError('Invalid lineup inputs')
    if capacity.sum()<target-1e-8:raise LineupInfeasible(f'Availability capacity {capacity.sum():.2f} is below {target} starters')
    if abs(capacity.sum()-target)<1e-8:return capacity.copy()
    logits=np.log(np.clip(base,1e-8,1-1e-8)/(1-np.clip(base,1e-8,1-1e-8)))
    lo,hi=-80.,80.
    for _ in range(100):
        mid=(lo+hi)/2;pred=capacity*sigmoid(logits+mid)
        if pred.sum()<target:lo=mid
        else:hi=mid
    return capacity*sigmoid(logits+(lo+hi)/2)

def role_moments(model,player,position):
    """Recover V2's four appearance categories without changing V2 source code."""
    history=sorted(model.hist.get(player,[]),key=lambda r:r['kickoff_time'])
    features=minute_features(history,position,**model.context[player])
    start,cameo,longstart,longsub=[float(sigmoid(features@b)) for b in model.minutes_model.coefficients]
    probabilities=np.array([start*(1-longstart),start*longstart,(1-start)*cameo*(1-longsub),(1-start)*cameo*longsub])
    conditions=[(1,0),(1,1),(0,0),(0,1)];means=[]
    for started,long in conditions:
        relevant=[r['minutes'] for r in history if r['minutes']>0 and int(r['starts']>0)==started and int(r['minutes']>=60)==long]
        pooled=model.minutes_model.conditional[position,started,long]
        means.append((sum(relevant[-5:])+4*pooled)/(len(relevant[-5:])+4))
    moments=probabilities*np.array(means)
    if history and model.minute_blend<1:
        weights=np.array([model.recent**(len(history)-1-i) for i in range(len(history))]);den=weights.sum()+.5
        group=model.pos[position];ep=[];em=[]
        for started,long in conditions:
            def indicator(r):return r['minutes']>0 and int(r['starts']>0)==started and int(r['minutes']>=60)==long
            ep.append((sum(w*indicator(r) for w,r in zip(weights,history))+.5*np.mean([indicator(r) for r in group]))/den)
            em.append((sum(w*indicator(r)*r['minutes'] for w,r in zip(weights,history))+.5*np.mean([indicator(r)*r['minutes'] for r in group]))/den)
        blend=model.minute_blend
        probabilities=blend*probabilities+(1-blend)*np.array(ep)
        moments=blend*moments+(1-blend)*np.array(em)
    return {'probabilities':probabilities.tolist(),'minute_moments':moments.tolist()}

def adjust_minutes(raw,roles,start,availability):
    r=copy.deepcopy(raw);p=np.array(roles['probabilities']);moments=np.array(roles['minute_moments'])
    oldstart=float(p[:2].sum());sub=float(p[2:].sum())
    cameo=sub/max(1-oldstart,1e-12)
    newsub=max(0,availability-start)*min(1,cameo)
    new=p.copy();new[:2]*=start/max(oldstart,1e-12);new[2:]*=newsub/max(sub,1e-12)
    means=np.divide(moments,p,out=np.array([35.,80.,15.,70.]),where=p>1e-12)
    minutes=float(new@means);ratio=minutes/max(raw['minutes'],1e-12)
    for key in ['goals','assists','saves','bonus','yellow_cards','red_cards','own_goals','penalties_saved','penalties_missed','defensive_actions']:
        r[key]*=ratio
    r.update(minutes=minutes,p_start=start,p_play=float(new.sum()),p60=float(new[1]+new[3]))
    r['p_defcon']=min(r['p_play'],raw['p_defcon']*ratio)
    return r

def score_players(raw,team_lambda,opponent_lambda,scoring):
    result=copy.deepcopy(raw);total=sum(r['goals'] for r in result)
    factor=.98*team_lambda/max(total,1e-12)
    for r in result:
        r['goals']*=factor;r['assists']*=factor
        r['p_clean_sheet']=r['p60']*math.exp(-opponent_lambda);r['team_clean_sheet']=math.exp(-opponent_lambda)
        pos=POSITIONS[r['position']];s=scoring
        pieces={'appearance':s['short_play']*r['p_play']+(s['long_play']-s['short_play'])*r['p60'],
                'goals':s['goals_scored'][pos]*r['goals'],'assists':s['assists']*r['assists'],
                'clean_sheet':s['clean_sheets'][pos]*r['p_clean_sheet'],
                'defensive_contribution':s['defensive_contribution'][pos]*r['p_defcon']}
        conceded=opponent_lambda*r['minutes']/max(r['p_play'],1e-12)/90
        saves=r['saves']/max(r['p_play'],1e-12)
        pieces['conceded']=s['goals_conceded'][pos]*r['p_play']*sum((i//2)*poisson(conceded,i) for i in range(40))
        pieces['saves']=s['saves']*r['p_play']*sum((i//3)*poisson(saves,i) for i in range(50))
        for key in ['bonus','yellow_cards','red_cards','own_goals','penalties_saved','penalties_missed']:pieces[key]=s[key]*r[key]
        r['components']=pieces;r['points']=sum(pieces.values())
    return result

def adjust_team(raw,roles,roster,team_lambda,opponent_lambda,scoring,constrain=True):
    availability=[availability_assumption(roster[r['player']]) for r in raw]
    q=np.array([x['factor'] for x in availability]);starts=np.array([r['p_start'] for r in raw])*q
    if constrain:
        for gk,target in [(True,1),(False,10)]:
            ix=[i for i,r in enumerate(raw) if (r['position']==1)==gk]
            starts[ix]=project_starters([raw[i]['p_start'] for i in ix],q[ix],target)
    adjusted=[]
    for i,r in enumerate(raw):
        p=adjust_minutes(r,roles[r['player']],float(starts[i]),float(q[i]))
        p['availability']=availability[i];p['availability_adjusted']=True
        p['lineup_adjusted']=constrain
        adjusted.append(p)
    scored=score_players(adjusted,team_lambda,opponent_lambda,scoring)
    checks={'starter_sum':sum(r['p_start'] for r in scored),'goalkeeper_starters':sum(r['p_start'] for r in scored if r['position']==1),
            'expected_minutes_sum':sum(r['minutes'] for r in scored),'availability_capacity':float(q.sum()),
            'players_excluded':sum(q==0).item(),'lineup_constrained':constrain}
    return scored,checks
