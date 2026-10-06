import copy
import json
import unittest
import tempfile
from pathlib import Path
from run_v4 import archive_matches
from unittest.mock import patch
import numpy as np
from models.v4 import before
from models.v4_features import FeatureTeamModel,training_rows
from models.v4_scenarios import scenario_rates
from freeze_v4 import verify_acceptance
from pipeline.publication import ROOT,build

class V4Tests(unittest.TestCase):
    def setUp(self):
        self.history=[{'season':'2025-26','id':i,'gw':i,'kickoff':f'2025-09-{i:02}T12:00:00Z','finished':True,
                       'home':'A','away':'B','hg':i%3,'ag':1,'hxg':1.2,'axg':.8} for i in range(1,8)]
        self.cutoff='2025-09-05T10:00:00Z'
    def model(self,history,rho=-.15):
        return FeatureTeamModel(history,self.cutoff,training_rows(history),'2025-26',ridge=20,standings=False,rho=rho)
    def test_future_labels_and_features_cannot_change_prediction(self):
        altered=copy.deepcopy(self.history)
        for m in altered[4:]:m.update(hg=20,ag=0,hxg=25,axg=0)
        np.testing.assert_allclose(self.model(self.history).predict('A','B'),self.model(altered).predict('A','B'),atol=1e-12)
        self.assertEqual(len(before(self.history,self.cutoff)),4)
    def test_archive_club_alias_preserves_continuity(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'matches.csv'
            p.write_text('fixture,round,kickoff_time,was_home,team,team_h_score,team_a_score,expected_goals\n1,1,2024-08-20T12:00:00Z,True,Ipswich,1,2,1.0\n1,1,2024-08-20T12:00:00Z,False,Arsenal,1,2,2.0\n')
            self.assertEqual(archive_matches(p,'2024-25')[0]['home'],'Ipswich Town')
    def test_distribution_preserves_means_and_clean_sheet_marginals(self):
        m=self.model(self.history)
        for teams in [('A','B'),('New club','A')]:
            h,a,g=m.distribution(*teams)
            self.assertGreaterEqual(g.min(),0);self.assertAlmostEqual(g.sum(),1)
            self.assertAlmostEqual(float(np.arange(26)@g.sum(axis=1)),h,places=9)
            self.assertAlmostEqual(float(np.arange(26)@g.sum(axis=0)),a,places=9)
            self.assertAlmostEqual(g[:,0].sum(),np.exp(-a),places=9)
            self.assertAlmostEqual(g[0,:].sum(),np.exp(-h),places=9)
    def test_rejected_gate_prevents_freeze(self):
        from freeze_v4 import read
        def tampered(path):
            result=read(path)
            if path.name=='final_results.json':result['accepted_match_gate']=False
            return result
        with patch('freeze_v4.read',side_effect=tampered):
            with self.assertRaises(ValueError):verify_acceptance()
    def test_current_publication_and_points_consistency(self):
        p=build();self.assertEqual(p['meta']['model_version'],'v4-experimental')
        for r in p['player_forecasts']:
            m=next(m for m in p['matches'] if m['fixture']==r['fixture'])
            opp=m['away_goals'] if r['team']==m['home'] else m['home_goals']
            self.assertAlmostEqual(r['p_clean_sheet'],r['p60']*np.exp(-opp),places=10)
            self.assertAlmostEqual(sum(r['components'].values()),r['points'],places=10)
    def test_scenario_audit_and_temporal_boundaries(self):
        event=dict(id='example',fixture=1,team='A',kind='injury',reason='Sensitivity example',source='test',
                   observed_at='2025-09-01T00:00:00Z',expires_at='2025-09-06T00:00:00Z',
                   attack_multiplier=.9,concession_multiplier=1.1,confidence='low')
        result=scenario_rates('A','B',1,(2.,1.),[event],self.cutoff)
        self.assertAlmostEqual(result['home_goals'],1.8);self.assertAlmostEqual(result['away_goals'],1.1)
        self.assertFalse(result['calibrated']);self.assertEqual(result['baseline_home_goals'],2.)
        for events,as_of in [([event,event],self.cutoff),([event],'2025-08-01T00:00:00Z'),([event],'2025-09-07T00:00:00Z')]:
            with self.assertRaises(ValueError):scenario_rates('A','B',1,(2.,1.),events,as_of)
if __name__=='__main__':unittest.main()
