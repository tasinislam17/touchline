"""Small-sample, interpretable FPL forecast models. All fitting uses supplied past rows."""
import math
import numpy as np

POSITIONS = {1: 'GKP', 2: 'DEF', 3: 'MID', 4: 'FWD'}

def poisson(lam, n):
    return math.exp(-lam + n * math.log(max(lam, 1e-12)) - math.lgamma(n + 1))

def defensive_award(row, position):
    if position == 1: return 0
    count = float(row.get('clearances_blocks_interceptions', 0)) + float(row.get('tackles', 0))
    if position in (3, 4): count += float(row.get('recoveries', 0))
    return int(count >= (10 if position == 2 else 12))

def score_actual(row, position, scoring):
    """Reconstruct points to catch schema/rules misunderstandings before modelling."""
    pos = POSITIONS[position]
    m = row['minutes']
    total = (scoring['long_play'] if m >= 60 else scoring['short_play'] if m else 0)
    for stat in ['goals_scored', 'assists', 'clean_sheets', 'own_goals', 'penalties_saved',
                 'penalties_missed', 'yellow_cards', 'red_cards', 'bonus']:
        weight = scoring[stat]
        total += float(row.get(stat, 0)) * (weight[pos] if isinstance(weight, dict) else weight)
    total += (row['saves'] // 3) * scoring['saves']
    total += (row['goals_conceded'] // 2) * scoring['goals_conceded'][pos]
    total += defensive_award(row, position) * scoring['defensive_contribution'][pos]
    return total

class TeamModel:
    def __init__(self, fixtures, rows, prior=5, xg_weight=0.5):
        self.prior, self.xg_weight = prior, xg_weight
        self.base_home = np.mean([f['team_h_score'] for f in fixtures]) if fixtures else 1.5
        self.base_away = np.mean([f['team_a_score'] for f in fixtures]) if fixtures else 1.2
        self.base_home = max(.1, self.base_home); self.base_away = max(.1, self.base_away)
        xgs = {}
        for r in rows:
            key = (r['fixture'], r['team'])
            xgs[key] = xgs.get(key, 0) + float(r.get('expected_goals', 0))
        self.stats = {}
        for f in fixtures:
            for home in (True, False):
                t, o = (f['team_h'], f['team_a']) if home else (f['team_a'], f['team_h'])
                gf, ga = (f['team_h_score'], f['team_a_score']) if home else (f['team_a_score'], f['team_h_score'])
                base, oppbase = (self.base_home, self.base_away) if home else (self.base_away, self.base_home)
                signal = (1-xg_weight)*gf + xg_weight*xgs.get((f['id'],t),gf)
                against = (1-xg_weight)*ga + xg_weight*xgs.get((f['id'],o),ga)
                self.stats.setdefault(t, []).append((signal/base, against/oppbase))

    def predict(self, home, away):
        def strength(team, column):
            values = self.stats.get(team, [])
            return (sum(v[column] for v in values)+self.prior)/(len(values)+self.prior)
        return (float(np.clip(self.base_home*strength(home,0)*strength(away,1), .15, 5)),
                float(np.clip(self.base_away*strength(away,0)*strength(home,1), .15, 5)))

    def distribution(self, home, away):
        h,a = self.predict(home,away)
        grid = np.outer([poisson(h,i) for i in range(26)], [poisson(a,i) for i in range(26)])
        return h,a,grid

class PlayerModel:
    def __init__(self, rows, scoring, prior=270, recent=1.0, xg_weight=.75):
        self.rows, self.scoring = rows, scoring
        self.prior, self.recent, self.xg_weight = prior, recent, xg_weight
        self.hist = {}; self.pos = {}
        for r in rows:
            self.hist.setdefault(r['element'], []).append(r)
            self.pos.setdefault(r['position'], []).append(r)
        self.pool={}
        ratekeys=['goals_scored','expected_goals','assists','expected_assists','bonus','saves',
                  'yellow_cards','red_cards','own_goals','penalties_saved','penalties_missed']
        for position,group in self.pos.items():
            minutes=max(1,sum(r['minutes'] for r in group))
            self.pool[position]={'minutes':float(np.mean([r['minutes'] for r in group])),
                'play':float(np.mean([r['minutes']>0 for r in group])),
                'sixty':float(np.mean([r['minutes']>=60 for r in group])),
                'start':float(np.mean([r.get('starts',0)>0 for r in group])),
                'defcon':float(np.mean([defensive_award(r,position) for r in group])),
                'rates':{k:sum(float(r.get(k,0)) for r in group)/minutes for k in ratekeys}}

    def raw(self, player, position):
        h = sorted(self.hist.get(player, []), key=lambda r:(r['round'],r['kickoff_time']))
        group = self.pos.get(position, [])
        if not h: return None
        weights = np.array([self.recent ** (len(h)-1-i) for i in range(len(h))])
        sw = sum(weights)
        def mean(key): return sum(w*float(r.get(key,0)) for w,r in zip(weights,h))/sw
        def event(fn,kind):
            base = self.pool[position][kind]
            return (sum(w*fn(r) for w,r in zip(weights,h)) + .5*base)/(sw+.5)
        pplay = event(lambda r:r['minutes']>0,'play')
        p60 = event(lambda r:r['minutes']>=60,'sixty')
        mins = (mean('minutes')*sw+.5*self.pool[position]['minutes'])/(sw+.5)
        totalminutes = sum(w*r['minutes'] for w,r in zip(weights,h))
        def rate(key):
            base = self.pool[position]['rates'][key]
            return (sum(w*float(r.get(key,0)) for w,r in zip(weights,h)) + self.prior*base)/(totalminutes+self.prior)
        goals = mins*((1-self.xg_weight)*rate('goals_scored')+self.xg_weight*rate('expected_goals'))
        assists = mins*((1-self.xg_weight)*rate('assists')+self.xg_weight*rate('expected_assists'))
        out = dict(player=player, position=position, minutes=mins, p_play=pplay, p60=p60,
                   p_start=event(lambda r:r.get('starts',0)>0,'start'), goals=goals, assists=assists,
                   p_defcon=event(lambda r:defensive_award(r,position),'defcon'),
                   defensive_actions=mean('clearances_blocks_interceptions')+mean('tackles')+(mean('recoveries') if position in (3,4) else 0),
                   baseline=mean('total_points'))
        for key in ['bonus','saves','yellow_cards','red_cards','own_goals','penalties_saved','penalties_missed']:
            out[key] = mins*rate(key)
        return out

    def predict_fixture(self, members, team_lambda, opponent_lambda):
        raw = [self.raw(p,pos) for p,pos in members]
        raw = [r for r in raw if r is not None]
        totalgoals = sum(r['goals'] for r in raw)
        # Reconcile player goals to the team model, reserving 2% for own goals.
        factor = team_lambda*.98/max(totalgoals,1e-9)
        for r in raw:
            r['goals'] *= factor
            r['assists'] *= factor
            r['p_clean_sheet'] = r['p60']*math.exp(-opponent_lambda)
            r['team_clean_sheet'] = math.exp(-opponent_lambda)
            pos = POSITIONS[r['position']]; s=self.scoring
            pieces = {'appearance':s['short_play']*r['p_play']+(s['long_play']-s['short_play'])*r['p60'],
                      'goals':s['goals_scored'][pos]*r['goals'], 'assists':s['assists']*r['assists'],
                      'clean_sheet':s['clean_sheets'][pos]*r['p_clean_sheet'],
                      'defensive_contribution':s['defensive_contribution'][pos]*r['p_defcon']}
            # Count thresholds require E[floor(N/k)], not floor(E[N]/k).
            conditional_minutes = r['minutes']/max(r['p_play'],1e-9)
            conceded = opponent_lambda*conditional_minutes/90
            pieces['conceded'] = s['goals_conceded'][pos]*r['p_play']*sum((i//2)*poisson(conceded,i) for i in range(40))
            saves = r['saves']/max(r['p_play'],1e-9)
            pieces['saves'] = s['saves']*r['p_play']*sum((i//3)*poisson(saves,i) for i in range(50))
            for key in ['bonus','yellow_cards','red_cards','own_goals','penalties_saved','penalties_missed']:
                pieces[key] = s[key]*r[key]
            r['components'] = pieces
            r['points'] = sum(pieces.values())
        return raw
