"""Opponent-adjusted goals and chronological appearance/minutes models.

Only arrays assembled from earlier matches are accepted by fit methods. No current
injury, cumulative season statistics, prices or target outcomes are feature inputs.
"""
import datetime as dt
import math
import numpy as np
from models.engine import PlayerModel, poisson


def timestamp(value):
    return dt.datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()


def sigmoid(z):
    return 1 / (1 + np.exp(-np.clip(z, -30, 30)))


def fit_glm(x, y, weight, ridge, family='logistic'):
    """Penalized Newton iterations with line search; first column is intercept."""
    x, y, weight = np.asarray(x, float), np.asarray(y, float), np.asarray(weight, float)
    beta = np.zeros(x.shape[1]); penalty = np.full(x.shape[1], ridge); penalty[0] = 1e-6
    avg = np.clip(np.average(y, weights=weight), 1e-5, 1-1e-5) if family == 'logistic' else max(.01, np.average(y, weights=weight))
    beta[0] = math.log(avg/(1-avg)) if family == 'logistic' else math.log(avg)

    def objective(b):
        z = np.clip(x @ b, -20, 20)
        loss = np.logaddexp(0, z)-y*z if family == 'logistic' else np.exp(z)-y*z
        return float(weight @ loss + .5*np.sum(penalty*b*b))

    for _ in range(35):
        z = np.clip(x @ beta, -20, 20)
        mu = sigmoid(z) if family == 'logistic' else np.exp(z)
        variance = mu*(1-mu) if family == 'logistic' else mu
        grad = x.T @ (weight*(mu-y)) + penalty*beta
        hess = x.T @ ((weight*np.maximum(variance, 1e-7))[:, None]*x) + np.diag(penalty)
        step = np.linalg.solve(hess, grad)
        old = objective(beta); scale = 1.
        while scale > 1e-6 and objective(beta-scale*step) > old:
            scale *= .5
        beta -= scale*step
        if np.max(np.abs(scale*step)) < 1e-6: break
    if not np.all(np.isfinite(beta)): raise ValueError('Nonfinite GLM fit')
    return beta


class AdjustedTeamModel:
    """Ridge Poisson attack + opponent defence, home advantage and time decay."""
    def __init__(self, fixtures, rows, ridge=8., half_life=12., rho=0., xg_weight=.5):
        self.rho = rho
        self.teams = {t:i for i,t in enumerate(sorted({f[k] for f in fixtures for k in ('team_h','team_a')}))}
        self.size = 2 + 2*len(self.teams)
        self.beta = np.zeros(self.size); self.beta[0]=math.log(1.3); self.beta[1]=math.log(1.5/1.3)
        if not fixtures: return
        xgs = {}
        for r in rows:
            key=(r['fixture'],r['team']);xgs[key]=xgs.get(key,0)+float(r.get('expected_goals',0))
        latest=max(f['event'] for f in fixtures)
        x=[];y=[];w=[]
        for f in fixtures:
            for home in (True,False):
                t,o=(f['team_h'],f['team_a']) if home else (f['team_a'],f['team_h'])
                goals=f['team_h_score'] if home else f['team_a_score']
                x.append(self.design(t,o,home));y.append((1-xg_weight)*goals+xg_weight*xgs.get((f['id'],t),goals))
                w.append(2**(-(latest-f['event'])/half_life))
        self.beta=fit_glm(x,y,w,ridge,family='poisson')

    def design(self, team, opponent, home):
        x=np.zeros(self.size);x[0]=1;x[1]=int(home)
        if team in self.teams:x[2+self.teams[team]]=1
        if opponent in self.teams:x[2+len(self.teams)+self.teams[opponent]]=1
        return x

    def predict(self, home, away):
        return tuple(float(np.clip(math.exp(float(self.design(t,o,h)@self.beta)),.15,5))
                     for t,o,h in [(home,away,True),(away,home,False)])

    def distribution(self, home, away):
        h,a=self.predict(home,away)
        grid=np.outer([poisson(h,i) for i in range(26)],[poisson(a,i) for i in range(26)])
        # Dixon-Coles low-score correction; preserve nonnegativity and Poisson marginals.
        rho=float(np.clip(self.rho,max(-1/h,-1/a)+1e-8,min(1/(h*a),1)-1e-8))
        grid[0,0]*=1-h*a*rho;grid[0,1]*=1+h*rho
        grid[1,0]*=1+a*rho;grid[1,1]*=1-rho
        return h,a,grid


def minute_features(history, position, kickoff, home, team_last_kickoff=None):
    h=sorted(history,key=lambda r:r['kickoff_time'])
    last=h[-1] if h else {}
    def mean(key,n):return float(np.mean([float(r.get(key,0)) for r in h[-n:]])) if h else 0.
    def frequency(fn,n):return float(np.mean([fn(r) for r in h[-n:]])) if h else 0.
    def run(fn):
        count=0
        for r in reversed(h):
            if not fn(r):break
            count+=1
        return min(count,5)/5
    now=timestamp(kickoff)
    played=[r for r in h if r['minutes']>0]
    days=(now-timestamp(played[-1]['kickoff_time']))/86400 if played else 60
    rest=(now-timestamp(team_last_kickoff))/86400 if team_last_kickoff else 14
    recent_work=sum(r['minutes'] for r in h if 0<now-timestamp(r['kickoff_time'])<=7*86400)/270
    x=[1.,*[float(position==p) for p in (1,2,3)],float(bool(h)),min(len(h),10)/10,
       last.get('minutes',0)/90,float(last.get('starts',0)>0),float(last.get('minutes',0)>0),
       float(last.get('minutes',0)>=60),mean('minutes',3)/90,mean('starts',3),
       frequency(lambda r:r['minutes']>=60,3),mean('minutes',5)/90,mean('starts',5),
       mean('minutes',len(h) or 1)/90,mean('starts',len(h) or 1),
       frequency(lambda r:r['minutes']>0 and not r['starts'],3),
       run(lambda r:r['minutes']==0),run(lambda r:r['starts']>0),
       min(days,60)/60,min(rest,14)/14,recent_work,float(home)]
    for p in (1,2,3):x.extend([float(position==p)*v for v in (x[6],x[7],x[10])])
    return np.array(x,float)


def make_minutes_training(rows, fixtures, deadlines):
    """Each label's features are made before its GW; doubles share past history."""
    fmap={f['id']:f for f in fixtures};rounds=sorted({r['round'] for r in rows})
    x=[];labels=[];gws=[];positions=[];completed=[]
    grouped={}
    for r in rows:grouped.setdefault(r['round'],[]).append(r)
    for gw in rounds:
        if gw<2:continue
        cutoff=timestamp(deadlines[gw]);history={};last_team={}
        for r in rows:
            if r['round']<gw and timestamp(r['kickoff_time'])+3*3600<cutoff:
                history.setdefault(r['element'],[]).append(r)
                last_team[r['team']]=max(last_team.get(r['team'],''),r['kickoff_time'])
        for r in grouped[gw]:
            f=fmap[r['fixture']]
            x.append(minute_features(history.get(r['element'],[]),r['position'],f['kickoff_time'],r['was_home'],last_team.get(r['team'])))
            labels.append([r['starts']>0,r['minutes']>0,r['minutes']>=60,r['minutes']])
            gws.append(gw);positions.append(r['position']);completed.append(timestamp(r['kickoff_time'])+3*3600)
    return {'x':np.array(x),'y':np.array(labels,float),'gw':np.array(gws),'position':np.array(positions),
            'completed':np.array(completed),'deadlines':deadlines}


class MinutesModel:
    """Start -> substitute if not starting -> 60-minute threshold -> minutes mixture."""
    def __init__(self, training, before_gw, ridge=10., half_life=8.):
        mask=(training['gw']<before_gw)&(training['completed']<timestamp(training['deadlines'][before_gw]))
        x=training['x'][mask];y=training['y'][mask];gw=training['gw'][mask]
        if not len(x):raise ValueError('Minutes model needs at least one earlier feature/label round')
        weight=2**(-(before_gw-1-gw)/half_life)
        self.coefficients=[]
        for subset,target in [(np.ones(len(y),bool),y[:,0]),(y[:,0]==0,y[:,1]),
                              (y[:,0]>0,y[:,2]),((y[:,0]==0)&(y[:,1]>0),y[:,2])]:
            if subset.sum()<10:
                coef=np.zeros(x.shape[1]);rate=(target[subset].sum()+.5)/(subset.sum()+1)
                coef[0]=math.log(rate/(1-rate))
            else:coef=fit_glm(x[subset],target[subset],weight[subset],ridge)
            self.coefficients.append(coef)
        self.conditional={}
        pos=training['position'][mask]
        for position in range(1,5):
            for started in (0,1):
                for long in (0,1):
                    subset=(pos==position)&(y[:,0]==started)&(y[:,1]>0)&(y[:,2]==long)
                    default=80 if long else 35 if started else 15
                    self.conditional[position,started,long]=(float((weight[subset]*y[subset,3]).sum())+3*default)/(float(weight[subset].sum())+3)

    def predict(self, features, history, position):
        start,cameo,longstart,longsub=[float(sigmoid(features@coef)) for coef in self.coefficients]
        probabilities={(1,0):start*(1-longstart),(1,1):start*longstart,
                       (0,0):(1-start)*cameo*(1-longsub),(0,1):(1-start)*cameo*longsub}
        minutes=0
        for (started,long),p in probabilities.items():
            relevant=[r['minutes'] for r in history if r['minutes']>0 and int(r['starts']>0)==started and int(r['minutes']>=60)==long]
            pooled=self.conditional[position,started,long]
            conditional=(sum(relevant[-5:])+4*pooled)/(len(relevant[-5:])+4)
            minutes+=p*conditional
        return {'minutes':minutes,'p_start':start,'p_play':start+(1-start)*cameo,
                'p60':probabilities[1,1]+probabilities[0,1]}


class PlayerModelV2(PlayerModel):
    def __init__(self, rows, scoring, minutes_model, **kwargs):
        super().__init__(rows,scoring,**kwargs)
        self.minutes_model=minutes_model;self.context={};self.minute_blend=1.

    def raw(self, player, position):
        old=super().raw(player,position);h=self.hist.get(player,[])
        context=self.context[player]
        learned=self.minutes_model.predict(minute_features(h,position,**context),h,position)
        if old is not None:
            new={k:self.minute_blend*learned[k]+(1-self.minute_blend)*old[k] for k in learned}
            ratio=new['minutes']/max(old['minutes'],1e-8)
            for key in ['goals','assists','saves','bonus','yellow_cards','red_cards','own_goals','penalties_saved','penalties_missed','defensive_actions']:
                old[key]*=ratio
            old['p_defcon']=min(new['p_play'],old['p_defcon']*ratio)
            old.update(new,cold_start=False)
            return old
        # Prospective roster is known from the timestamped bootstrap; historical
        # experiments never infer a debutant's pre-deadline registration from outcomes.
        pool=self.pool[position];rates=pool['rates'];mins=learned['minutes']
        out=dict(player=player,position=position,**learned,cold_start=True,baseline=0.,defensive_actions=0.)
        out['goals']=mins*((1-self.xg_weight)*rates['goals_scored']+self.xg_weight*rates['expected_goals'])
        out['assists']=mins*((1-self.xg_weight)*rates['assists']+self.xg_weight*rates['expected_assists'])
        out['p_defcon']=min(learned['p_play'],pool['defcon']*mins/max(pool['minutes'],1))
        for key in ['saves','bonus','yellow_cards','red_cards','own_goals','penalties_saved','penalties_missed']:
            out[key]=mins*rates[key]
        return out
