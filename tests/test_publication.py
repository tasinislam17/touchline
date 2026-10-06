import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from pipeline.publication import atomic, build, encode, normalize, publish, validate_forecast, ROOT
from fetch_data import snapshot


def source():
    b={'events':[{'id':1,'deadline_time':'2026-08-21T17:30:00Z','finished':False}],
       'teams':[{'id':1,'name':'Home','short_name':'HOM'},{'id':2,'name':'Away','short_name':'AWY'}],
       'element_types':[{'id':1}], 'elements':[{'id':1,'web_name':'Example','team':1,'element_type':1,'now_cost':45}]}
    f=[{'id':1,'event':1,'team_h':1,'team_a':2,'kickoff_time':None,'finished':False}]
    return b,f

class PublicationTests(unittest.TestCase):
    def test_normalizes_null_kickoff_and_unknown_gameweek(self):
        b,f=source();f[0]['event']=None
        d=normalize(b,f,'20260820T120000Z')
        self.assertEqual(d['players'][0]['key'],'2026-27:player:1')
        self.assertIsNone(d['fixtures'][0]['event'])
        self.assertIsNone(d['fixtures'][0]['kickoff_time'])

    def test_duplicate_and_schema_failure(self):
        b,f=source();b['elements']*=2
        with self.assertRaises(ValueError):normalize(b,f,'20260820T120000Z')
        b,f=source();del b['teams']
        with self.assertRaises(ValueError):normalize(b,f,'20260820T120000Z')

    def test_nan_price_fails(self):
        b,f=source();b['elements'][0]['now_cost']=float('nan')
        with self.assertRaises(ValueError):normalize(b,f,'20260820T120000Z')

    def test_failed_download_keeps_last_pointer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);atomic(root/'data/latest.txt',b'previous')
            b,f=source()
            def fetch(path,dest):
                if 'element-summary' in path:raise RuntimeError('upstream unavailable')
                val=b if path=='bootstrap-static/' else f;atomic(dest,encode(val));return val
            with self.assertRaises(RuntimeError):snapshot(root,fetch,1)
            self.assertEqual((root/'data/latest.txt').read_text(),'previous')
            self.assertFalse(list((root/'data/raw').glob('*/manifest.json')))

    def test_successful_download_commits_validated_pointer(self):
        with tempfile.TemporaryDirectory() as tmp:
            b,f=source()
            def fetch(path,dest):
                val=b if path=='bootstrap-static/' else f if path=='fixtures/' else {'history':[],'fixtures':[]}
                atomic(dest,encode(val));return val
            directory=snapshot(Path(tmp),fetch,1)
            self.assertTrue((directory/'manifest.json').exists())
            self.assertEqual((Path(tmp)/'data/latest.txt').read_text(),str(directory.relative_to(tmp)))

    def test_atomic_publish_previous_and_idempotence(self):
        with tempfile.TemporaryDirectory() as tmp:
            p={'meta':{'observed_at':'2026-01-01T00:00:00Z'}}
            a=publish(p,tmp);b=publish(p,tmp)
            self.assertEqual(a['current'],b['current']);self.assertIsNone(b['previous'])
            p['value']=2;c=publish(p,tmp);self.assertEqual(c['previous'],a['current'])
            old=(Path(tmp)/'manifest.json').read_bytes()
            with patch('pipeline.publication.atomic',side_effect=OSError('disk full')):
                with self.assertRaises(OSError):publish(p,tmp)
            self.assertEqual((Path(tmp)/'manifest.json').read_bytes(),old)

class SavedForecastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        freeze=ROOT/json.loads((ROOT/'reports/v3/latest_freeze.json').read_text())['path']
        cls.payload=build(freeze=freeze)
        freeze=ROOT/json.loads((ROOT/'reports/v3/latest_freeze.json').read_text())['path']
        cls.raw=json.loads((freeze/'v3.json').read_text())
        cls.meta=json.loads((freeze/'manifest.json').read_text())
        cls.catalog=cls.payload['catalog']

    def test_real_artifact_and_coverage(self):
        self.assertGreater(len(self.payload['player_forecasts']),500)
        self.assertGreater(len(self.payload['matches']),0)
        self.assertEqual(len(self.payload['gameweek_totals']),len(self.catalog['players']))

    def test_bad_probabilities_and_component_sum(self):
        for field in ['points','p_play']:
            raw=copy.deepcopy(self.raw);raw['players'][0][field]=999
            with self.assertRaises(ValueError):validate_forecast(raw,self.catalog,self.meta)
        raw=copy.deepcopy(self.raw);raw['matches'][0]['score_grid'][0][0]=2
        with self.assertRaises(ValueError):validate_forecast(raw,self.catalog,self.meta)

    def test_future_observation_and_season_mismatch(self):
        c=copy.deepcopy(self.catalog);c['observed_at']='2027-01-01T00:00:00Z'
        with self.assertRaises(ValueError):validate_forecast(self.raw,c,self.meta)
        m=copy.deepcopy(self.meta);m['season_start_deadline']='2025-01-01T00:00:00Z'
        with self.assertRaises(ValueError):validate_forecast(self.raw,self.catalog,m)

    def test_duplicate_missing_forecast_and_fixture(self):
        raw=copy.deepcopy(self.raw);raw['players'].pop()
        with self.assertRaises(ValueError):validate_forecast(raw,self.catalog,self.meta)
        raw=copy.deepcopy(self.raw);raw['players'].append(raw['players'][0])
        with self.assertRaises(ValueError):validate_forecast(raw,self.catalog,self.meta)
        raw=copy.deepcopy(self.raw);raw['matches'].pop()
        with self.assertRaises(ValueError):validate_forecast(raw,self.catalog,self.meta)

    def test_tampered_checksum_rejected(self):
        with patch('pipeline.publication.digest',return_value='invalid'):
            with self.assertRaises(ValueError):build()

    def test_double_gameweek_is_not_collapsed(self):
        raw=copy.deepcopy(self.raw);c=copy.deepcopy(self.catalog)
        match=copy.deepcopy(raw['matches'][0]);fid=match['fixture'];match['fixture']=999;raw['matches'].append(match)
        f=copy.deepcopy(next(f for f in c['fixtures'] if f['id']==fid));f['id']=999;c['fixtures'].append(f)
        for p in list(raw['players']):
            if p['fixture']==fid:
                p=copy.deepcopy(p);p['fixture']=999;raw['players'].append(p)
        validate_forecast(raw,c,self.meta)

if __name__=='__main__':unittest.main()
