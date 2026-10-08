"""Tests use temporary stores only; no invented production dates or receipts."""
import copy
import json
import math
import sqlite3
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone,timedelta
from email.utils import format_datetime
from pathlib import Path
from urllib.error import HTTPError
from app import refresh,FIXTURES
from fx_core import (Store,normalize_live,validate_reading,kst_date,comparison,display,
                     fixture_expected_check,retry_after,SOURCE,SIGNAL,UNIT,STATUS_VALIDATOR)

class TrackerTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.path=Path(self.folder.name)/'replay.sqlite3'
        self.store=Store(self.path,synthetic=True)
    def tearDown(self):self.folder.cleanup()
    def f(self,key):return copy.deepcopy(FIXTURES['T04-'+key])
    def baseline(self):
        a=self.store.replay(self.f('NORMAL-D1-A'))
        b=self.store.replay(self.f('NORMAL-D1-B'))
        return a,b

    def test_exact_schema_and_reject_invalid_types(self):
        for key in ['NORMAL-D1-A','NORMAL-D1-B','NORMAL-D2','RECOVER-D2']:
            validate_reading(self.f(key)['payload'])
        base=self.f('NORMAL-D1-A')['payload']
        bad=[]
        for value in ['105',True,None,float('nan'),float('inf'),float('-inf')]:
            r=copy.deepcopy(base);r['normalized_value']=value;bad.append(r)
        for value in ['http://x.test','https://','https://u:secret@x.test','https://x.test:wrong']:
            r=copy.deepcopy(base);r['source_url']=value;bad.append(r)
        for key,value in [('source_time','2026-08-24'),('fetched_at','invalid'),
                          ('record_timezone','UTC'),('record_date','2026-08-25')]:
            r=copy.deepcopy(base);r[key]=value;bad.append(r)
        r=copy.deepcopy(base);r['extra']=1;bad.append(r)
        r=copy.deepcopy(base);del r['unit'];bad.append(r)
        bad.append(self.f('SCHEMA-BREAK')['payload'])
        for reading in bad:
            with self.subTest(reading=repr(reading)[:90]):
                with self.assertRaises(Exception):validate_reading(reading)

    def test_decimal_direct_input_directions_and_rounding(self):
        raw='{"date":"2026-10-07","base":"JPY","quote":"KRW","rate":8.46567890123456789}'
        reading,exact,meta=normalize_live(raw,'2026-10-08T03:00:00Z')
        self.assertEqual(exact,'846.56789012345678900')
        self.assertIsInstance(reading['normalized_value'],float)
        self.assertEqual(set(reading),{'signal_id','normalized_value','unit','source_name','source_url','source_time','fetched_at','record_timezone','record_date'})
        self.assertEqual(display(exact),'846.57')
        self.assertEqual(meta['raw_rate'],'8.46567890123456789')
        inverse=raw.replace('"JPY","quote":"KRW"','"KRW","quote":"JPY"').replace('8.46567890123456789','0.12')
        _,value,meta=normalize_live(inverse,'2026-10-08T03:00:00Z')
        self.assertEqual(value,'833.'+'3'*57)
        self.assertEqual(meta['formula'],'100 ÷ rate')
        for rate in ['"105"','0','-1','NaN','Infinity','null','true']:
            with self.assertRaises(Exception):
                normalize_live(raw.replace('8.46567890123456789',rate),'2026-10-08T03:00:00Z')
        self.assertEqual(display('1.005'),'1.01')

    def test_kst_boundary(self):
        self.assertEqual(kst_date('2026-10-08T14:59:59Z'),'2026-10-08')
        self.assertEqual(kst_date('2026-10-08T15:00:00Z'),'2026-10-09')
        self.assertEqual(kst_date('2026-10-09T00:00:00+09:00'),'2026-10-09')

    def test_normal_three_same_day_then_next_day_and_expected(self):
        baseline_id=None
        for key in ['NORMAL-D1-A','NORMAL-D1-B','NORMAL-D1-B','NORMAL-D2']:
            fixture=self.f(key);prior=self.store.snapshot();out=self.store.replay(fixture)
            if baseline_id is None:baseline_id=out['current']['record_id']
            self.assertTrue(fixture_expected_check(out,fixture,prior,baseline_id)['passed'])
            if key=='NORMAL-D1-B':
                self.assertEqual(out['current']['record_id'],baseline_id)
                self.assertEqual(out['current']['first_fetched_at'],self.f('NORMAL-D1-A')['virtual_now'])
                self.assertEqual(len(out['records']),1)
        self.assertEqual(len(out['records']),2)
        self.assertEqual(out['current']['comparison']['signed_change'],15)
        self.assertEqual(out['current']['comparison']['direction'],'증가')
        self.assertEqual(out['current']['reading']['unit'],'pt')
        self.assertEqual(Store(self.path,synthetic=True).snapshot(),out)

    def test_all_five_failures_preserve_and_expected_independent(self):
        for key,code in [('TIMEOUT','timeout'),('AUTH-401','auth'),('RATE-429','rate_limit'),
                         ('OFFLINE','offline'),('SCHEMA-BREAK','schema_error')]:
            self.store.reset();_,prior=self.baseline()
            fixture=self.f(key);out=self.store.replay(fixture)
            self.assertEqual(out['records'],prior['records'])
            self.assertEqual(out['status'],{'freshness':'stale','error_code':code})
            STATUS_VALIDATOR.validate(out['status'])
            self.assertTrue(fixture_expected_check(out,fixture,prior)['passed'])
            if code=='rate_limit':
                self.assertEqual(out['attempt']['retry_after_seconds'],60)
                self.assertEqual(out['attempt']['retry_after_provenance'],'upstream_seconds')
        fixture=self.f('NORMAL-D2');fixture['expected']['stored_value']=999
        # A private test copy with wrong expected never changes the result.
        out=self.store.replay(fixture)
        self.assertEqual(out['current']['reading']['normalized_value'],120)
        self.assertFalse(fixture_expected_check(out,fixture)['passed'])

    def test_recovery_retry_and_repeated_input(self):
        self.baseline();before=self.store.replay(self.f('TIMEOUT'))
        self.assertEqual(before['status']['error_code'],'timeout')
        after=self.store.replay(self.f('RECOVER-D2'))
        self.assertEqual(after['status'],{'freshness':'fresh','error_code':'none'})
        self.assertEqual(len(after['records']),2)
        self.assertEqual(after['current']['reading']['normalized_value'],120)
        record_id=after['current']['record_id']
        repeat=self.store.replay(self.f('RECOVER-D2'))
        self.assertEqual(len(repeat['records']),2)
        self.assertEqual(repeat['current']['record_id'],record_id)

    def test_concurrent_upsert_multiple_store_instances(self):
        a,_=self.baseline()
        def worker(_):return Store(self.path,synthetic=True).replay(self.f('NORMAL-D1-B'))
        with ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(worker,range(24)))
        out=self.store.snapshot()
        self.assertEqual(len(out['records']),1)
        self.assertEqual(out['current']['record_id'],a['current']['record_id'])
        with self.store.connect() as db:
            sql=db.execute("SELECT sql FROM sqlite_master WHERE name='daily_readings'").fetchone()[0]
        self.assertIn('UNIQUE(signal_id,record_date)',sql.replace(' ',''))

    def test_late_success_and_failure_cannot_overwrite_newer(self):
        from fx_core import normalize_replay
        self.baseline()
        old=self.store.begin_attempt('2026-08-24T10:00:00Z')
        new=self.store.begin_attempt('2026-08-25T00:00:00Z')
        f=self.f('RECOVER-D2')
        recent=self.store.process(new,f['transport'],f['payload'],normalize_replay,f['virtual_now'])
        late=self.store.process(old,{'mode':'timeout'},None,normalize_replay,'2026-08-24T10:00:00Z')
        self.assertEqual(late['records'],recent['records'])
        self.assertEqual(late['status'],recent['status'])
        old=self.store.begin_attempt('2026-08-25T01:00:00Z')
        new=self.store.begin_attempt('2026-08-25T02:00:00Z')
        failed=self.store.process(new,{'mode':'offline'},None,normalize_replay,'2026-08-25T02:00:00Z')
        late=self.store.process(old,f['transport'],f['payload'],normalize_replay,f['virtual_now'])
        self.assertEqual(late['records'],failed['records'])
        self.assertEqual(late['status'],failed['status'])

    def test_timeout_discards_background_result_and_click_guard(self):
        live=Store(Path(self.folder.name)/'isolated-live.sqlite3')
        def slow():
            time.sleep(.15)
            return '{"date":"2026-10-07","base":"JPY","quote":"KRW","rate":8.4606}'
        out=refresh(live,slow,timeout=.01)
        self.assertEqual(out['status']['error_code'],'timeout')
        time.sleep(.2)
        self.assertEqual(live.snapshot()['records'],[])
        calls=[]
        guarded=refresh(live,lambda:calls.append(1))
        self.assertEqual(calls,[])
        self.assertEqual(guarded['status']['error_code'],'timeout')

    def test_retry_after_formats_and_missing(self):
        at='2026-10-08T00:00:00Z'
        self.assertEqual(retry_after('60',at),(60,'upstream_seconds'))
        self.assertEqual(retry_after('Thu, 08 Oct 2026 00:01:00 GMT',at),(60,'upstream_http_date'))
        self.assertEqual(retry_after(None,at),(None,'not_provided'))
        self.assertEqual(retry_after('wrong',at),(None,'invalid_upstream_header'))

    def test_compare_precision_decrease_equal_insufficient_unit_mismatch(self):
        def row(value,unit='pt',day='2026-08-25'):
            return {'decimal_value':value,'reading':{'unit':unit,'record_date':day}}
        self.assertEqual(comparison(row('105'),row('120'))['direction'],'감소')
        self.assertEqual(comparison(row('105'),row('120'))['signed_change'],-15)
        self.assertEqual(comparison(row('105'),row('105'))['direction'],'동일')
        self.assertEqual(comparison(row('105'),None)['state'],'insufficient')
        self.assertEqual(comparison(row('105'),row('100','KRW'))['state'],'unit_mismatch')
        tiny=comparison(row('846.062',UNIT),row('846.061',UNIT))
        self.assertEqual(tiny['signed_change_decimal'],'0.001')
        self.assertEqual(tiny['text'],'이전 기록보다 100엔당 0.00원 상승')

    def test_legacy_migration_immutable_snapshots_and_reset_isolation(self):
        from fx_core import normalize_live
        path=Path(self.folder.name)/'legacy.sqlite3'
        raw='{"date":"2026-10-07","base":"JPY","quote":"KRW","rate":8.4606}'
        old={'raw_response':raw,'queried_at':'2026-10-08T06:25:08Z','normalized_value':'846.0600'}
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE fx_daily(query_date TEXT PRIMARY KEY,payload TEXT)')
            db.execute('INSERT INTO fx_daily VALUES(?,?)',('2026-10-08',json.dumps(old)))
        db.close()
        live=Store(path);before=live.snapshot();snapshots=live.snapshots()
        self.assertEqual(before['current']['decimal_value'],'846.0600')
        self.assertTrue(before['current']['metadata']['legacy_first_success_unknown'])
        self.baseline();self.store.reset()
        self.assertEqual(live.snapshot(),before)
        self.assertEqual(live.snapshots(),snapshots)
        self.assertEqual(Store(path).snapshot(),before)
        with live.connect() as db:
            self.assertEqual(json.loads(db.execute('SELECT payload FROM fx_daily').fetchone()[0]),old)
        with self.assertRaises(ValueError):live.reset()
        with self.assertRaises(sqlite3.IntegrityError):
            with live.connect() as db:db.execute("UPDATE success_snapshots SET payload='{}'")
        with self.assertRaises(sqlite3.IntegrityError):
            with live.connect() as db:db.execute('DELETE FROM success_snapshots')


    def test_live_http_network_errors_and_rate_cooldown(self):
        from urllib.error import URLError
        for status,code in [(401,'auth'),(403,'auth'),(429,'rate_limit')]:
            live=Store(Path(self.folder.name)/('http-'+str(status)+'.sqlite3'))
            def denied():
                raise HTTPError(SOURCE,status,'private upstream diagnostic',{'Retry-After':'60'},None)
            out=refresh(live,denied)
            self.assertEqual(out['status'],{'freshness':'stale','error_code':code})
            self.assertEqual(out['records'],[])
            self.assertNotIn('private upstream diagnostic',json.dumps(out))
            if status==429:
                calls=[]
                refresh(live,lambda:calls.append(1))
                self.assertEqual(calls,[])
                self.assertEqual(out['attempt']['retry_after_seconds'],60)
        live=Store(Path(self.folder.name)/'network.sqlite3')
        def disconnected():raise URLError('server upstream connection failed')
        self.assertEqual(refresh(live,disconnected)['status']['error_code'],'offline')

if __name__=='__main__':unittest.main()
