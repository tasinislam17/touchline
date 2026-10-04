import copy
import math
import hashlib
import json
import pathlib
import tempfile
from unittest import mock
import unittest
import numpy as np
from models.v2 import AdjustedTeamModel, MinutesModel, PlayerModelV2, make_minutes_training, minute_features
from run_experiments import load_current, split
from run_v2 import choose_player, choose_team, forecast_players, team_forecasts
from score_freeze import verify_freeze
import score_freeze


class V2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows,cls.fixtures,cls.deadlines,_,cls.scoring,cls.bootstrap=load_current()
        cls.training=make_minutes_training(cls.rows,cls.fixtures,cls.deadlines)
        cls.train,cls.past,cls.target=split(cls.rows,cls.fixtures,cls.deadlines,4)

    def test_future_labels_cannot_change_minutes_fit(self):
        original=MinutesModel(self.training,4)
        changed=copy.deepcopy(self.training)
        changed['y'][changed['gw']>=4]=999
        changed['x'][changed['gw']>=4]=-999
        refit=MinutesModel(changed,4)
        for a,b in zip(original.coefficients,refit.coefficients):np.testing.assert_array_equal(a,b)

    def test_late_match_label_cannot_enter_fit(self):
        changed=copy.deepcopy(self.training)
        i=np.flatnonzero(changed['gw']==3)[0]
        changed['completed'][i]=float('inf')
        a=MinutesModel(changed,4)
        changed['x'][i]=999;changed['y'][i]=999
        b=MinutesModel(changed,4)
        for x,y in zip(a.coefficients,b.coefficients):np.testing.assert_array_equal(x,y)

    def test_minutes_mixture_is_coherent(self):
        model=MinutesModel(self.training,4)
        for pos in range(1,5):
            for hist in [[],[r for r in self.train if r['position']==pos][:3]]:
                features=minute_features(hist,pos,self.target[0]['kickoff_time'],True)
                p=model.predict(features,hist,pos)
                self.assertLessEqual(p['p_start'],p['p_play'])
                self.assertLessEqual(p['p60'],p['p_play'])
                self.assertGreaterEqual(p['minutes'],60*p['p60'])
                self.assertLessEqual(p['minutes'],90*p['p60']+59*(p['p_play']-p['p60'])+1e-8)
                for key in ('p_start','p_play','p60'):self.assertTrue(0<=p[key]<=1)

    def test_adjusted_score_distribution_preserves_marginals(self):
        for rho in (0,-.08,-1,1):
            model=AdjustedTeamModel(self.past,self.train,rho=rho)
            h,a,g=model.distribution(1,2)
            self.assertGreaterEqual(g.min(),0)
            self.assertAlmostEqual(float(g.sum()),1,places=8)
            self.assertAlmostEqual(float(g[:,0].sum()),math.exp(-a),places=8)
            self.assertAlmostEqual(float(g[0,:].sum()),math.exp(-h),places=8)
            self.assertAlmostEqual(float((g.sum(axis=1)*np.arange(26)).sum()),h,places=7)
            self.assertAlmostEqual(float((g.sum(axis=0)*np.arange(26)).sum()),a,places=7)

    def test_new_registered_player_gets_fallback(self):
        minute=MinutesModel(self.training,4)
        player=PlayerModelV2(self.train,self.scoring,minute)
        player.context={99999:dict(kickoff=self.target[0]['kickoff_time'],home=True)}
        result=player.predict_fixture([(99999,3)],1.5,1.)[0]
        self.assertTrue(result['cold_start'])
        self.assertTrue(math.isfinite(result['points']))
        self.assertGreater(result['minutes'],0)
        self.assertLessEqual(result['p_defcon'],result['p_play'])

    def test_forecast_universe_does_not_use_future_registrations(self):
        teams=team_forecasts(self.train,self.past,self.target,4,{'prior':8,'xg_weight':.5})
        model=MinutesModel(self.training,4)
        p=forecast_players(self.train,self.past,self.target,4,self.scoring,{'prior':360,'recent':.65,'xg_weight':.75},teams['v1'],model)
        self.assertLessEqual({x['player'] for x in p},{r['element'] for r in self.train})

    def test_empty_selection_retains_incumbent(self):
        self.assertEqual(choose_team([]),'v1')
        self.assertEqual(choose_player([]),'v1')

    def test_frozen_grid_can_score_without_refitting(self):
        teams=team_forecasts(self.train,self.past,self.target,4,{'prior':8,'xg_weight':.5},include_grid=True)
        for name,matches in teams.items():
            for m in matches:
                self.assertAlmostEqual(-math.log(m['score_grid'][m['actual_home']][m['actual_away']]),m['nll'])

    def test_freeze_checksum_detects_changes(self):
        with tempfile.TemporaryDirectory() as name:
            directory=pathlib.Path(name);p=directory/'v1.json';p.write_text('{"players": []}')
            (directory/'manifest.json').write_text(json.dumps({'files_sha256':{'v1.json':hashlib.sha256(p.read_bytes()).hexdigest()}}))
            verify_freeze(directory)
            p.write_text('{"players": [1]}')
            with self.assertRaises(ValueError):verify_freeze(directory)

    def test_completed_gameweek_scorer_uses_frozen_forecast(self):
        teams=team_forecasts(self.train,self.past,self.target,4,{'prior':8,'xg_weight':.5},include_grid=True)
        players=forecast_players(self.train,self.past,self.target,4,self.scoring,
                                {'prior':360,'recent':.65,'xg_weight':.75},teams['v1'])
        with tempfile.TemporaryDirectory() as name:
            root=pathlib.Path(name);directory=root/'freeze';directory.mkdir()
            forecast=directory/'v1.json';forecast.write_text(json.dumps({'players':players,'matches':teams['v1']}))
            digest=hashlib.sha256(forecast.read_bytes()).hexdigest()
            (directory/'manifest.json').write_text(json.dumps({'gameweek':4,
                'season_start_deadline':self.bootstrap['events'][0]['deadline_time'],
                'files_sha256':{'v1.json':digest}}))
            (root/'data').mkdir();(root/'data/latest.txt').write_text('test-snapshot')
            (root/'reports/v2').mkdir(parents=True)
            with mock.patch.object(score_freeze,'ROOT',root),mock.patch('sys.argv',['score_freeze.py',str(directory)]),mock.patch('builtins.print'):
                score_freeze.main()
            reports=list((root/'reports/v2/live_evaluations').glob('*.json'))
            self.assertEqual(len(reports),1)
            result=json.loads(reports[0].read_text())['results']['v1.json']
            self.assertTrue(result['scoreline_log_loss_available'])
            self.assertAlmostEqual(result['metrics']['scoreline_nll'],np.mean([m['nll'] for m in teams['v1']]))
            self.assertEqual(hashlib.sha256(forecast.read_bytes()).hexdigest(),digest)


if __name__=='__main__':unittest.main()
