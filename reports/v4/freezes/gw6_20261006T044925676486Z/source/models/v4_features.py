"""Small global Poisson model on lagged football context, with auditable features."""
import datetime as dt
import math
import numpy as np
from models.v2 import fit_glm
from models.v4 import before,utc
from models.engine import poisson

FEATURES=['intercept','home','attack_xg','opponent_xga','attack_goals','opponent_conceded',
          'recent_attack_xg','recent_opponent_xga','venue_attack_xg','venue_opponent_xga',
          'team_ppg','opponent_ppg']


def context(history,team,home,season):
    games=[]
    for m in history:
        if team not in (m['home'],m['away']):continue
        h=m['home']==team
        gf,ga=(m['hg'],m['ag']) if h else (m['ag'],m['hg'])
        xf,xa=(m['hxg'],m['axg']) if h else (m['axg'],m['hxg'])
        games.append({'gf':gf,'ga':ga,'xf':gf if xf is None else xf,'xa':ga if xa is None else xa,
                      'home':h,'season':m['season'],'kickoff':m['kickoff'],'points':3 if gf>ga else 1 if gf==ga else 0})
    games.sort(key=lambda g:g['kickoff'])
    def avg(key,group,prior=5,base=1.4):return (sum(g[key] for g in group)+prior*base)/(len(group)+prior)
    long=games[-30:];short=games[-5:];venue=[g for g in games if g['home']==home][-15:]
    current=[g for g in games if g['season']==season]
    return {'xf':avg('xf',long),'xa':avg('xa',long),'gf':avg('gf',long),'ga':avg('ga',long),
            'short_xf':avg('xf',short,5,avg('xf',long)),'short_xa':avg('xa',short,5,avg('xa',long)),
            'venue_xf':avg('xf',venue,8,avg('xf',long)),'venue_xa':avg('xa',venue,8,avg('xa',long)),
            'ppg':avg('points',current,5,1.35),'games':len(games)}


def features(history,team,opp,home,season,standings=True):
    t=context(history,team,home,season);o=context(history,opp,not home,season)
    x=[1.,float(home),math.log(t['xf']/1.4),math.log(o['xa']/1.4),math.log(t['gf']/1.4),math.log(o['ga']/1.4),
       math.log(t['short_xf']/t['xf']),math.log(o['short_xa']/o['xa']),
       math.log(t['venue_xf']/t['xf']),math.log(o['venue_xa']/o['xa'])]
    if standings:x.extend([t['ppg']-1.35,o['ppg']-1.35])
    return np.array(x)


def training_rows(matches):
    """Each feature row uses only completed matches before its round's cutoff."""
    groups={}
    for m in matches:
        if m.get('gw') is not None and m.get('kickoff') and m.get('finished'):
            groups.setdefault((m['season'],m['gw']),[]).append(m)
    output=[]
    for _,group in sorted(groups.items()):
        cutoff=group[0].get('deadline') or (utc(min(m['kickoff'] for m in group))-dt.timedelta(hours=24)).isoformat()
        past=before(matches,cutoff)
        for m in group:
            for h in [True,False]:
                t,o=(m['home'],m['away']) if h else (m['away'],m['home'])
                output.append({'x':features(past,t,o,h,m['season']),'y':m['hg'] if h else m['ag'],
                               'completed':utc(m['kickoff'])+dt.timedelta(hours=3)})
    return output


class FeatureTeamModel:
    def __init__(self, matches, cutoff, training, season, ridge=5.,standings=True,rho=0.):
        self.rho=rho
        self.history=before(matches,cutoff);self.season=season;self.standings=standings
        end=utc(cutoff);train=[r for r in training if r['completed']<end]
        x=[r['x'] if standings else r['x'][:10] for r in train]
        y=[r['y'] for r in train]
        weights=[2**(-((end-r['completed']).total_seconds()/86400)/365) for r in train]
        self.beta=fit_glm(x,y,weights,ridge,family='poisson')
        self.config={'ridge':ridge,'standings':standings,'family':'lagged_context','rho':rho}

    def predict(self,home,away):
        return tuple(float(np.clip(math.exp(float(features(self.history,t,o,h,self.season,self.standings)@self.beta)),.15,5))
                     for t,o,h in [(home,away,True),(away,home,False)])

    def distribution(self,home,away):
        h,a=self.predict(home,away);g=np.outer([poisson(h,i) for i in range(26)],[poisson(a,i) for i in range(26)])
        rho=float(np.clip(self.rho,max(-1/h,-1/a)+1e-8,min(1/(h*a),1)-1e-8))
        g[0,0]*=1-h*a*rho;g[0,1]*=1+h*rho
        g[1,0]*=1+a*rho;g[1,1]*=1-rho
        return h,a,g/g.sum()

    def explain(self,home,away):
        def one(t,o,h):
            x=features(self.history,t,o,h,self.season,self.standings)
            return {'team':t,'opponent':o,'home':h,'features':dict(zip(FEATURES,x.tolist())),
                    'log_goal_contributions':dict(zip(FEATURES,(x*self.beta).tolist())),
                    'history':context(self.history,t,h,self.season)}
        return {'home':one(home,away,True),'away':one(away,home,False),'config':self.config,
                'lineup_adjusted':False,'table_position_used':False,'table_points_per_game_used':self.standings}
