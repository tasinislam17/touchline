import copy
import datetime as dt
import hashlib
import json
import pathlib
import tempfile
import unittest
from unittest import mock
import numpy as np
from availability import connect, ingest, at_or_before
from models.v2 import MinutesModel, PlayerModelV2, make_minutes_training
from models.v3 import availability_assumption, project_starters, LineupInfeasible, role_moments, adjust_team, score_players
from run_experiments import load_current, split
from run_v2 import team_forecasts, forecast_players
import score_v3

class AvailabilityTests(unittest.TestCase):
    def test_percentage_is_not_start_probability(self):
        self.assertEqual(availability_assumption({'status':'d','chance_of_playing_next_round':75})['factor'],.75)
        self.assertFalse(availability_assumption({'status':'a'})['calibrated'])

    def test_future_return_percentage_beats_current_injury_status(self):
        self.assertEqual(availability_assumption({'status':'i','chance_of_playing_next_round':100})['factor'],1)
        self.assertEqual(availability_assumption({'status':'s','chance_of_playing_next_round':100})['factor'],1)

    def test_unselectable_and_missing_data_rules(self):
        self.assertEqual(availability_assumption({'can_select':False,'chance_of_playing_next_round':100})['factor'],0)
        for status,q in [('a',1),('d',.75),('i',0),('s',0),('u',0)]:
            self.assertEqual(availability_assumption({'status':status,'chance_of_playing_next_round':None})['factor'],q)
        self.assertEqual(availability_assumption({'status':'a','chance_of_playing_next_round':float('nan')})['factor'],1)

    def test_asof_is_observation_time_not_news_date_and_import_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            directory=pathlib.Path(temp);season='2026-08-21T17:30:00Z'
            b={'events':[{'deadline_time':season}],'elements':[{'id':1,'status':'i','news_added':'2026-01-01T00:00:00Z'}]}
            (directory/'bootstrap.json').write_text(json.dumps(b))
            raw=(directory/'bootstrap.json').read_bytes()
            (directory/'manifest.json').write_text(json.dumps({'retrieved_at':'20261004T080000Z','sha256':{'bootstrap.json':hashlib.sha256(raw).hexdigest()}}))
            db=connect(directory/'test.sqlite');ingest(db,directory);ingest(db,directory)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM snapshots').fetchone()[0],1)
            self.assertIsNone(at_or_before(db,season,'2026-10-03T00:00:00Z'))
            self.assertEqual(at_or_before(db,season,'2026-10-04T08:00:00Z')['players'][1]['status'],'i')
            db.close()

class LineupTests(unittest.TestCase):
    def test_projection_respects_caps_and_exact_cardinality(self):
        rng=np.random.default_rng(42)
        for _ in range(30):
            p=rng.uniform(.01,.95,25);q=rng.choice([0,.5,.75,1],25)
            if q.sum()<10:continue
            x=project_starters(p,q,10)
            self.assertAlmostEqual(x.sum(),10,places=7)
            self.assertTrue(np.all(x<=q+1e-10));self.assertTrue(np.all(x>=0))

    def test_injury_increases_teammate_starts(self):
        p=np.array([.9,.7,.6,.3]);allfit=project_starters(p,np.ones(4),2)
        injured=project_starters(p,[0,1,1,1],2)
        self.assertEqual(injured[0],0)
        self.assertTrue(np.all(injured[1:]>allfit[1:]))

    def test_infeasible_does_not_silently_relax_caps(self):
        with self.assertRaises(LineupInfeasible):project_starters([.8,.1],[0,.5],1)
        np.testing.assert_array_equal(project_starters([.2,.3],[.5,.5],1),[.5,.5])

class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows,cls.fixtures,cls.deadlines,_,cls.scoring,cls.b=load_current()
        cls.train,cls.past,cls.target=split(cls.rows,cls.fixtures,cls.deadlines,4)
        cls.minute=MinutesModel(make_minutes_training(cls.rows,cls.fixtures,cls.deadlines),4)

    def team(self,blend=1):
        model=PlayerModelV2(self.train,self.scoring,self.minute,prior=90,recent=.65,xg_weight=1)
        model.minute_blend=blend;team=self.target[0]['team_h']
        roster={p['id']:dict(p,status='a',chance_of_playing_next_round=100,can_select=True,removed=False) for p in self.b['elements'] if p['team']==team}
        model.context={p:dict(kickoff=self.target[0]['kickoff_time'],home=True) for p in roster}
        raw=[model.raw(p,r['element_type']) for p,r in roster.items()]
        roles={p:role_moments(model,p,r['element_type']) for p,r in roster.items()}
        return model,roster,raw,roles

    def test_role_reconstruction_matches_v2_for_all_blends(self):
        for blend in [0,.5,1]:
            model,roster,raw,roles=self.team(blend)
            for r in raw:
                p=roles[r['player']]['probabilities'];m=roles[r['player']]['minute_moments']
                self.assertAlmostEqual(sum(p),r['p_play'])
                self.assertAlmostEqual(sum(p[:2]),r['p_start'])
                self.assertAlmostEqual(p[1]+p[3],r['p60'])
                self.assertAlmostEqual(sum(m),r['minutes'])

    def test_identity_overlay_matches_v2_and_does_not_mutate_inputs(self):
        model,roster,raw,roles=self.team()
        original=copy.deepcopy(raw)
        expected=model.predict_fixture([(p,r['element_type']) for p,r in roster.items()],1.5,1.2)
        actual,_=adjust_team(raw,roles,roster,1.5,1.2,self.scoring,constrain=False)
        for a,e in zip(actual,expected):
            self.assertAlmostEqual(a['points'],e['points']);self.assertAlmostEqual(a['minutes'],e['minutes'])
        self.assertEqual(raw,original)

    def test_exclusion_and_lineup_scoring_invariants(self):
        _,roster,raw,roles=self.team()
        victim=next(r['player'] for r in raw if r['position']!=1)
        roster[victim]['chance_of_playing_next_round']=0
        preds,audit=adjust_team(raw,roles,roster,1.5,1.2,self.scoring)
        self.assertAlmostEqual(audit['starter_sum'],11);self.assertAlmostEqual(audit['goalkeeper_starters'],1)
        for p in preds:
            self.assertLessEqual(p['p_start'],p['p_play']+1e-10)
            self.assertLessEqual(p['p_play'],p['availability']['factor']+1e-10)
            self.assertLessEqual(p['p60'],p['p_play']+1e-10)
            self.assertGreaterEqual(p['minutes'],60*p['p60']-1e-8)
            self.assertLessEqual(p['minutes'],90*p['p60']+59*(p['p_play']-p['p60'])+1e-8)
            self.assertAlmostEqual(sum(p['components'].values()),p['points'])
            if p['player']==victim:self.assertEqual(p['points'],0);self.assertEqual(p['minutes'],0)

    def test_completed_v3_comparison_scores_saved_payloads(self):
        teams=team_forecasts(self.train,self.past,self.target,4,{'prior':8,'xg_weight':.5},include_grid=True)
        players=forecast_players(self.train,self.past,self.target,4,self.scoring,
                                {'prior':360,'recent':.65,'xg_weight':.75},teams['v1'])
        with tempfile.TemporaryDirectory() as temp:
            root=pathlib.Path(temp);directory=root/'freeze';directory.mkdir();hashes={}
            for name in ['v2_same_snapshot','availability_only','v3']:
                p=directory/(name+'.json');p.write_text(json.dumps({'players':players,'matches':teams['v1']}))
                hashes[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
            (directory/'manifest.json').write_text(json.dumps({'gameweek':4,'season_start_deadline':self.b['events'][0]['deadline_time'],'files_sha256':hashes}))
            (root/'data').mkdir();(root/'data/latest.txt').write_text('test-actual-snapshot')
            (root/'reports/v3').mkdir(parents=True)
            with mock.patch.object(score_v3,'ROOT',root),mock.patch('sys.argv',['score_v3.py',str(directory)]),mock.patch('builtins.print'):
                score_v3.main()
            outputs=list((root/'reports/v3/evaluations').glob('*.json'));self.assertEqual(len(outputs),1)
            r=json.loads(outputs[0].read_text());self.assertEqual(len(r['results']),3)
            self.assertEqual(r['results']['v3.json'],r['results']['v2_same_snapshot.json'])
            self.assertTrue(all(hashlib.sha256((directory/p).read_bytes()).hexdigest()==h for p,h in hashes.items()))

if __name__=='__main__':unittest.main()
