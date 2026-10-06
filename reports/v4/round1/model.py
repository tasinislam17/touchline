"""Cross-season, opponent-adjusted team rates. Inputs are strictly past matches.

Club names, not season-local numeric IDs, carry strength between seasons. Current
injury flags and future lineups are deliberately not retrofitted to historical games.
"""
import datetime as dt
import math
import numpy as np
from models.v2 import fit_glm
from models.engine import poisson


def utc(value):
    return dt.datetime.fromisoformat(value.replace('Z', '+00:00'))


def before(matches, cutoff):
    end=utc(cutoff)
    return [m for m in matches if m.get('finished') and m.get('kickoff') and utc(m['kickoff'])+dt.timedelta(hours=3)<end]


class ContextTeamModel:
    def __init__(self, matches, cutoff, ridge=4., half_days=180., xg_weight=.5, venue=False, promoted=True):
        self.matches=before(matches,cutoff)
        self.config=dict(ridge=ridge,half_days=half_days,xg_weight=xg_weight,venue=venue,promoted=promoted)
        self.teams={t:i for i,t in enumerate(sorted({m[k] for m in self.matches for k in ('home','away')}))}
        self.n=len(self.teams);self.venue=venue;self.promoted=promoted
        self.beta=np.zeros(2+(4 if venue else 2)*self.n)
        self.beta[0]=math.log(1.25);self.beta[1]=math.log(1.5/1.25)
        if not self.matches:return
        x=[];y=[];weights=[]
        for m in self.matches:
            age=max(0,(utc(cutoff)-utc(m['kickoff'])).total_seconds()/86400)
            for home in (True,False):
                team,opp=(m['home'],m['away']) if home else (m['away'],m['home'])
                goals=m['hg'] if home else m['ag'];xg=m['hxg'] if home else m['axg']
                x.append(self.design(team,opp,home));y.append((1-xg_weight)*goals+xg_weight*(goals if xg is None else xg))
                weights.append(2**(-age/half_days))
        self.beta=fit_glm(x,y,weights,ridge,family='poisson')

    def design(self,team,opponent,home):
        x=np.zeros_like(self.beta);x[0]=1;x[1]=int(home)
        if team in self.teams:
            i=self.teams[team];x[2+i]=1
            if self.venue:x[2+2*self.n+i]=.5 if home else -.5
        if opponent in self.teams:
            i=self.teams[opponent];x[2+self.n+i]=1
            if self.venue:x[2+3*self.n+i]=-.5 if home else .5
        return x

    def predict(self,home,away):
        result=[]
        for t,o,h in [(home,away,True),(away,home,False)]:
            eta=float(self.design(t,o,h)@self.beta)
            # Explicit broad prior for clubs with no top-flight record in these inputs.
            if self.promoted:
                if t not in self.teams:eta+=math.log(.85)
                if o not in self.teams:eta+=math.log(1.15)
            result.append(float(np.clip(math.exp(eta),.15,5)))
        return tuple(result)

    def distribution(self,home,away):
        h,a=self.predict(home,away)
        grid=np.outer([poisson(h,i) for i in range(26)],[poisson(a,i) for i in range(26)])
        return h,a,grid/grid.sum()

    def explain(self,home,away):
        def side(t,o,h):
            i=self.teams.get(t);j=self.teams.get(o)
            return {'team':t,'opponent':o,'home':h,
                    'attack_multiplier':math.exp(self.beta[2+i]) if i is not None else (.85 if self.promoted else 1),
                    'opponent_defence_multiplier':math.exp(self.beta[2+self.n+j]) if j is not None else (1.15 if self.promoted else 1),
                    'prior_matches':sum(t in (m['home'],m['away']) for m in self.matches),
                    'new_club_prior':i is None}
        return {'home':side(home,away,True),'away':side(away,home,False),'config':self.config,
                'lineup_adjusted':False,'table_position_used':False}
