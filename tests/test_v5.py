import copy
import json
import unittest
from unittest.mock import patch
import numpy as np
from freeze_v5 import verify_selection
from models.v5 import FeatureTeamModelV5,training_rows
from pipeline.publication import ROOT,build
from run_v5 import BASE
from score_freeze import verify_freeze


class V5Tests(unittest.TestCase):
    def matches(self):
        rows=[]
        for gw in range(1,9):
            rows.append({'id':gw,'season':'2025-26','gw':gw,'kickoff':f'2025-09-{gw:02}T12:00:00Z',
                         'deadline':f'2025-09-{gw:02}T08:00:00Z','finished':True,'home':'A','away':'B',
                         'hg':gw%3,'ag':(gw+1)%3,'hxg':1+gw/20,'axg':.8+gw/30})
        return rows

    def test_future_results_cannot_change_prediction(self):
        matches=self.matches();cutoff='2025-09-06T08:00:00Z'
        original=FeatureTeamModelV5(matches,cutoff,training_rows(matches,BASE),'2025-26',BASE)
        changed=copy.deepcopy(matches)
        for row in changed:
            if row['gw']>=6:row.update(hg=20,ag=0,hxg=30,axg=0)
        altered=FeatureTeamModelV5(changed,cutoff,training_rows(changed,BASE),'2025-26',BASE)
        np.testing.assert_allclose(original.predict('A','B','2025-09-07T12:00:00Z'),
                                   altered.predict('A','B','2025-09-07T12:00:00Z'),atol=1e-11)

    def test_distribution_is_normalized_and_preserves_goal_means(self):
        matches=self.matches();model=FeatureTeamModelV5(matches,'2025-09-08T08:00:00Z',training_rows(matches,BASE),'2025-26',BASE)
        home,away,grid=model.distribution('A','B','2025-09-09T12:00:00Z')
        self.assertGreaterEqual(float(grid.min()),0);self.assertAlmostEqual(float(grid.sum()),1)
        self.assertAlmostEqual(float(np.arange(26)@grid.sum(axis=1)),home,places=8)
        self.assertAlmostEqual(float(np.arange(26)@grid.sum(axis=0)),away,places=8)

    def test_saved_selection_retains_match_model_and_promotes_minutes_only(self):
        result=json.loads((ROOT/'reports/v5/results.json').read_text())
        self.assertFalse(result['match']['accepted']);self.assertEqual(result['match']['production'],'v4')
        self.assertTrue(result['minutes']['accepted']);self.assertEqual(result['minutes']['production'],'r3_h26')
        self.assertTrue(result['combined_player_gate'])

    def test_tampered_selection_cannot_freeze(self):
        from freeze_v5 import read
        def tampered(path):
            value=read(path)
            if path.name=='results.json':value['minutes']['accepted']=False
            return value
        with patch('freeze_v5.read',side_effect=tampered):
            with self.assertRaises(ValueError):verify_selection()

    def test_v5_publication_and_freeze_checksums(self):
        payload=build();self.assertEqual(payload['meta']['model_version'],'v5-experimental')
        freeze=ROOT/json.loads((ROOT/'reports/v5/latest_freeze.json').read_text())['path']
        manifest=verify_freeze(freeze);self.assertEqual(manifest['forecast_file'],'v5.json')
        self.assertEqual(payload['meta']['gameweek'],11);self.assertEqual(len(payload['matches']),10)


if __name__=='__main__':unittest.main()
