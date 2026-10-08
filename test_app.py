import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal
from app import Store, normalize, display, comparison

# Synthetic responses stay in temporary test storage, never in the live database.
def raw(rate='8.4606', base='JPY', quote='KRW', observed='2026-10-07'):
    return '{"date":"%s","base":"%s","quote":"%s","rate":%s}' % (observed, base, quote, rate)

class TrackerTests(unittest.TestCase):
    def test_same_day_next_day_failure_preserves_records(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder)/'test.sqlite3')
            t1=datetime(2026,10,7,16,tzinfo=timezone.utc) # Oct 8 KST
            a=store.refresh(lambda:raw(), t1)
            self.assertEqual(a['records'][0]['query_date'],'2026-10-08')
            self.assertEqual(a['records'][0]['normalized_value'],'846.0600')
            b=store.refresh(lambda:raw('8.46567890123456789'),datetime(2026,10,8,14,59,tzinfo=timezone.utc))
            self.assertEqual(len(b['records']),1)
            self.assertEqual(b['records'][0]['normalized_value'],'846.56789012345678900')
            self.assertEqual(b['records'][0]['display_value'],'846.57')
            self.assertEqual(b['records'][0]['comparison'],'이전 기록보다 100엔당 0.51원 상승')
            c=store.refresh(lambda:raw('8.46567890123456789'),datetime(2026,10,8,15,tzinfo=timezone.utc))
            self.assertEqual([r['query_date'] for r in c['records']],['2026-10-08','2026-10-09'])
            self.assertEqual(c['records'][1]['comparison'],'이전 기록과 동일')
            def fail(): raise OSError('test network failure')
            d=store.refresh(fail,datetime(2026,10,9,15,tzinfo=timezone.utc))
            self.assertFalse(d['status']['ok'])
            self.assertEqual(c['records'],d['records'])
            self.assertEqual(Store(Path(folder)/'test.sqlite3').snapshot()['records'],c['records'])

    def test_directions_validation_and_precision(self):
        t=datetime(2026,10,8,tzinfo=timezone.utc)
        inverse=normalize(raw('0.12','KRW','JPY'),t)
        self.assertEqual(inverse['normalized_value'],str(Decimal('833.'+'3'*57)))
        self.assertEqual(inverse['formula'],'100 ÷ rate')
        for response in [raw('0'),raw('-1'),raw('1','USD','KRW'),raw(observed='2026-10-10')]:
            with self.assertRaises(ValueError):normalize(response,t)
        # Direction must be determined before rounding; equal display is not equal data.
        self.assertEqual(display('846.061'),'846.06')
        self.assertEqual(display('846.062'),'846.06')
        self.assertEqual(comparison('846.062','846.061'),'이전 기록보다 100엔당 0.00원 상승')
        self.assertEqual(comparison('846','847'),'이전 기록보다 100엔당 1.00원 하락')

if __name__=='__main__':unittest.main()
