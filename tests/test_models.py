import copy, math, unittest
from models.engine import TeamModel, PlayerModel, defensive_award, poisson, score_actual
from run_experiments import load_current, split, predictions, evaluate

class ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows,cls.fixtures,cls.deadlines,_,cls.scoring,_=load_current()

    def test_scoring_reconstructs_live_history(self):
        for r in self.rows:
            self.assertEqual(score_actual(r,r['position'],self.scoring),r['total_points'])

    def test_defensive_thresholds(self):
        r={'clearances_blocks_interceptions':8,'tackles':1,'recoveries':3}
        self.assertEqual(defensive_award(r,2),0)
        self.assertEqual(defensive_award(r,3),1)
        self.assertEqual(defensive_award(r,1),0)
        r['tackles']=2
        self.assertEqual(defensive_award(r,2),1)

    def test_future_outcomes_cannot_change_forecast(self):
        args=(self.deadlines,4,self.scoring,{'prior':2,'xg_weight':.5},{'prior':90,'recent':.65,'xg_weight':1})
        a,_=predictions(self.rows,self.fixtures,*args)
        rows=copy.deepcopy(self.rows); fixtures=copy.deepcopy(self.fixtures)
        for r in rows:
            if r['round']>=4:
                for key in ['minutes','total_points','expected_goals','goals_scored']:r[key]=999
        for f in fixtures:
            if (f.get('event') or 0)>=4:f['team_h_score']=9;f['team_a_score']=9
        b,_=predictions(rows,fixtures,*args)
        self.assertEqual(a,b)

    def test_probability_and_team_goal_coherence(self):
        train,past,_=split(self.rows,self.fixtures,self.deadlines,4)
        t=TeamModel(past,train)
        h,a,g=t.distribution(1,2)
        self.assertAlmostEqual(float(g.sum()),1,places=8)
        p,_=predictions(self.rows,self.fixtures,self.deadlines,4,self.scoring,{'prior':2},{'prior':90})
        grouped={}
        for r in p:
            for key in ['p_play','p60','p_start','p_defcon','p_clean_sheet']:
                self.assertTrue(0<=r[key]<=1)
            self.assertLessEqual(r['p60'],r['p_play'])
            self.assertAlmostEqual(sum(r['components'].values()),r['points'])
            grouped.setdefault((r['fixture'],r['team']),[]).append(r)
        model=TeamModel(past,train,prior=2)
        for f in self.fixtures:
            if f.get('event')==4:
                hg,ag=model.predict(f['team_h'],f['team_a'])
                for team,lam in [(f['team_h'],hg),(f['team_a'],ag)]:
                    self.assertAlmostEqual(sum(x['goals'] for x in grouped[(f['id'],team)]),lam*.98)

    def test_double_gameweek_is_scored_as_one_player_week(self):
        ps,_=predictions(self.rows,self.fixtures,self.deadlines,4,self.scoring,{'prior':2},{'prior':90})
        p=next(p for p in ps if p['prior_minutes']>=45)
        actual=next(r for r in self.rows if r['element']==p['player'] and r['fixture']==p['fixture'])
        second=dict(p,fixture=99999);second_actual=dict(actual,fixture=99999)
        result=evaluate([p,second],[],[actual,second_actual])
        self.assertEqual(result['prior_regulars']['n'],1)
        self.assertAlmostEqual(result['prior_regulars']['mae'],2*abs(p['points']-actual['total_points']))

    def test_unfinished_or_late_matches_are_excluded(self):
        fixtures=copy.deepcopy(self.fixtures)
        f=next(f for f in fixtures if f['event']==3)
        excluded=f['id'];f['kickoff_time']=self.deadlines[4]
        train,past,_=split(self.rows,fixtures,self.deadlines,4)
        self.assertNotIn(excluded,{f['id'] for f in past})
        self.assertNotIn(excluded,{r['fixture'] for r in train})

if __name__=='__main__':unittest.main()
