"""Configurable lagged-context goal model for the preregistered V5 experiment."""
import datetime as dt
import math
import numpy as np
from models.v2 import fit_glm
from models.v4 import before,utc
from models.engine import poisson


def _average(games,key,prior,base):
    return (sum(float(g[key]) for g in games)+prior*base)/(len(games)+prior)


def context(history,team,home,season,target_time,config):
    games=[]
    for match in history:
        if team not in (match['home'],match['away']):continue
        was_home=match['home']==team
        goals_for,goals_against=(match['hg'],match['ag']) if was_home else (match['ag'],match['hg'])
        xg_for,xg_against=(match['hxg'],match['axg']) if was_home else (match['axg'],match['hxg'])
        games.append({'gf':goals_for,'ga':goals_against,'xf':goals_for if xg_for is None else xg_for,
                      'xa':goals_against if xg_against is None else xg_against,'home':was_home,
                      'season':match['season'],'kickoff':match['kickoff'],
                      'points':3 if goals_for>goals_against else 1 if goals_for==goals_against else 0})
    games.sort(key=lambda game:game['kickoff'])
    long=games[-config['long_window']:];recent=games[-config['recent_window']:]
    venue=[game for game in games if game['home']==home][-config['venue_window']:]
    current=[game for game in games if game['season']==season]
    xf=_average(long,'xf',5,1.4);xa=_average(long,'xa',5,1.4)
    gf=_average(long,'gf',5,1.4);ga=_average(long,'ga',5,1.4)
    last=utc(games[-1]['kickoff']) if games else utc(target_time)-dt.timedelta(days=14)
    rest=float(np.clip((utc(target_time)-last).total_seconds()/86400,2,21))
    return {'xf':xf,'xa':xa,'gf':gf,'ga':ga,
            'recent_xf':_average(recent,'xf',5,xf),'recent_xa':_average(recent,'xa',5,xa),
            'venue_xf':_average(venue,'xf',8,xf),'venue_xa':_average(venue,'xa',8,xa),
            'ppg':_average(current,'points',5,1.35),'rest':rest,'games':len(games)}


def feature_names(config):
    names=['intercept','home','attack_xg','opponent_xga']
    if config['goals_features']:names+=['attack_goals','opponent_conceded']
    names+=['recent_attack_xg','recent_opponent_xga','venue_attack_xg','venue_opponent_xga']
    if config['rest']:names+=['rest_advantage']
    if config['ppg']:names+=['team_ppg','opponent_ppg']
    return names


def features(history,team,opponent,home,season,target_time,config):
    own=context(history,team,home,season,target_time,config)
    other=context(history,opponent,not home,season,target_time,config)
    values=[1.,float(home),math.log(own['xf']/1.4),math.log(other['xa']/1.4)]
    if config['goals_features']:values += [math.log(own['gf']/1.4),math.log(other['ga']/1.4)]
    values += [math.log(own['recent_xf']/own['xf']),math.log(other['recent_xa']/other['xa']),
               math.log(own['venue_xf']/own['xf']),math.log(other['venue_xa']/other['xa'])]
    if config['rest']:values += [float(np.clip((own['rest']-other['rest'])/7,-1.5,1.5))]
    if config['ppg']:values += [own['ppg']-1.35,other['ppg']-1.35]
    return np.asarray(values,float)


def training_rows(matches,config):
    """Construct labels and features using only matches completed before round cutoff."""
    groups={}
    for match in matches:
        if match.get('gw') is not None and match.get('kickoff') and match.get('finished'):
            groups.setdefault((match['season'],match['gw']),[]).append(match)
    output=[]
    for (season,_),group in sorted(groups.items()):
        cutoff=group[0].get('deadline') or (utc(min(match['kickoff'] for match in group))-dt.timedelta(hours=24)).isoformat()
        history=before(matches,cutoff)
        for match in group:
            for home in (True,False):
                team,opponent=(match['home'],match['away']) if home else (match['away'],match['home'])
                output.append({'x':features(history,team,opponent,home,season,match['kickoff'],config),
                               'y':match['hg'] if home else match['ag'],
                               'completed':utc(match['kickoff'])+dt.timedelta(hours=3)})
    return output


class FeatureTeamModelV5:
    def __init__(self,matches,cutoff,training,season,config):
        self.history=before(matches,cutoff);self.season=season;self.config=dict(config)
        end=utc(cutoff);rows=[row for row in training if row['completed']<end]
        weights=[2**(-((end-row['completed']).total_seconds()/86400)/config['half_days']) for row in rows]
        self.beta=fit_glm([row['x'] for row in rows],[row['y'] for row in rows],weights,config['ridge'],family='poisson')

    def predict(self,home,away,kickoff):
        return tuple(float(np.clip(math.exp(float(features(self.history,team,opponent,is_home,self.season,kickoff,self.config)@self.beta)),.15,5))
                     for team,opponent,is_home in [(home,away,True),(away,home,False)])

    def distribution(self,home,away,kickoff):
        home_goals,away_goals=self.predict(home,away,kickoff)
        grid=np.outer([poisson(home_goals,i) for i in range(26)],[poisson(away_goals,i) for i in range(26)])
        rho=float(np.clip(self.config['rho'],max(-1/home_goals,-1/away_goals)+1e-8,min(1/(home_goals*away_goals),1)-1e-8))
        grid[0,0]*=1-home_goals*away_goals*rho;grid[0,1]*=1+home_goals*rho
        grid[1,0]*=1+away_goals*rho;grid[1,1]*=1-rho
        return home_goals,away_goals,grid/grid.sum()

    def explain(self,home,away,kickoff):
        names=feature_names(self.config)
        def side(team,opponent,is_home):
            vector=features(self.history,team,opponent,is_home,self.season,kickoff,self.config)
            return {'team':team,'opponent':opponent,'home':is_home,'features':dict(zip(names,vector.tolist())),
                    'log_goal_contributions':dict(zip(names,(vector*self.beta).tolist())),
                    'history':context(self.history,team,is_home,self.season,kickoff,self.config)}
        return {'home':side(home,away,True),'away':side(away,home,False),'config':self.config,
                'lineup_adjusted':False,'table_position_used':False,
                'table_points_per_game_used':self.config['ppg']}
