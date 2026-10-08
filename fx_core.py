"""Shared validation, precision, persistence and transport pipeline for live/replay."""
import json
import math
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, localcontext, ROUND_HALF_UP, ROUND_HALF_EVEN
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / 'assets/studio-task-assets/t04-real-information-board'
SOURCE = 'https://api.frankfurter.dev/v2/providers/ecb/rate/jpy/krw'
SIGNAL = 'jpy-krw-per-100-jpy'
UNIT = 'KRW/100 JPY'
KST = timezone(timedelta(hours=9), 'Asia/Seoul')
ERRORS = {
 'timeout': ('응답 지연으로 제한시간을 초과했습니다.', '잠시 후 다시 시도하세요.'),
 'auth': ('외부 원천이 요청을 거절했습니다 (401/403).', '원천 상태를 확인하고 다시 시도하세요.'),
 'rate_limit': ('외부 원천의 호출 제한에 도달했습니다.', '안내된 대기 시간이 지난 뒤 다시 시도하세요.'),
 'offline': ('서버와 외부 원천 사이의 연결에 실패했습니다.', '서버 또는 원천의 네트워크 상태를 확인하고 다시 시도하세요.'),
 'schema_error': ('응답 형식 검증에 실패했습니다.', '원천 형식을 확인하고 다시 시도하세요.')
}
READING_SCHEMA = json.loads((ASSETS/'normalized-reading.schema.json').read_bytes())
STATUS_SCHEMA = json.loads((ASSETS/'reading-status.schema.json').read_bytes())
FIXTURE_SCHEMA = json.loads((ASSETS/'fixture.schema.json').read_bytes())
READING_VALIDATOR = Draft202012Validator(READING_SCHEMA, format_checker=FormatChecker())
STATUS_VALIDATOR = Draft202012Validator(STATUS_SCHEMA)
FIXTURE_VALIDATOR = Draft202012Validator(FIXTURE_SCHEMA, format_checker=FormatChecker())


def iso_time(value):
    if not isinstance(value, str) or not FormatChecker().conforms(value, 'date-time'):
        raise ValueError('valid RFC3339 timestamp required')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('timezone required')
    return parsed


def kst_date(value):
    return iso_time(value).astimezone(KST).date().isoformat()


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def validate_reading(reading):
    READING_VALIDATOR.validate(reading)
    value = reading['normalized_value']
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('finite numeric value required; numeric strings rejected')
    parsed = urlsplit(reading['source_url'])
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('valid HTTPS URL without credentials required')
    parsed.port  # Reject an invalid port.
    iso_time(reading['fetched_at'])
    if reading['source_time'] is not None:
        iso_time(reading['source_time'])
    if reading['record_date'] != kst_date(reading['fetched_at']):
        raise ValueError('record_date must derive from fetched_at in Asia/Seoul')
    return reading


def display(value):
    value = Decimal(str(value))
    with localcontext() as ctx:
        ctx.prec = max(80, len(value.as_tuple().digits) + abs(value.adjusted()) + 5)
        return format(value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP), 'f')


def normalize_live(raw, fetched_at):
    # Direct Decimal parsing preserves upstream lexical decimal precision.
    data = json.loads(raw, parse_float=Decimal, parse_int=Decimal,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
    if not isinstance(data, dict) or (data.get('base'), data.get('quote')) not in [('JPY','KRW'),('KRW','JPY')]:
        raise ValueError('JPY/KRW base and quote required')
    rate = data.get('rate')
    if not isinstance(rate, Decimal) or not rate.is_finite() or rate <= 0:
        raise ValueError('positive numeric upstream rate required')
    reference_date = date.fromisoformat(data['date']).isoformat()
    if reference_date > kst_date(fetched_at):
        raise ValueError('future upstream reference date')
    with localcontext() as ctx:
        ctx.prec = max(60, len(rate.as_tuple().digits)+4)
        ctx.rounding = ROUND_HALF_EVEN
        exact = rate*100 if data['base']=='JPY' else Decimal(100)/rate
    numeric = float(exact)
    if not math.isfinite(numeric) or numeric <= 0:
        raise ValueError('normalized value outside finite positive range')
    reading = dict(signal_id=SIGNAL, normalized_value=numeric, unit=UNIT,
                   source_name='Frankfurter · ECB 일별 기준환율', source_url=SOURCE,
                   source_time=None, fetched_at=fetched_at, record_timezone='Asia/Seoul',
                   record_date=kst_date(fetched_at))
    validate_reading(reading)
    metadata = dict(raw_response=raw, raw_rate=str(rate), base=data['base'], quote=data['quote'],
                    formula='100 × rate' if data['base']=='JPY' else '100 ÷ rate',
                    source_reference_date=reference_date, source_time_precision='date',
                    numeric_interface='binary64; calculations use separate decimal_value',
                    decimal_policy='direct decimal input; division >=60 significant digits, ROUND_HALF_EVEN')
    return reading, str(exact), metadata


def normalize_replay(payload, fetched_at):
    # Preserve the original nine-field fixture object; do not coerce values.
    reading = dict(payload) if isinstance(payload, dict) else payload
    validate_reading(reading)
    if reading['fetched_at'] != fetched_at:
        raise ValueError('fixture payload time must match virtual_now')
    return reading, str(Decimal(str(reading['normalized_value']))), {'synthetic': True, 'raw_payload':payload}


def comparison(current, previous):
    if previous is None:
        return dict(state='insufficient', direction=None, direction_code=None,
                    signed_change=None, magnitude=None, unit=None, text='비교 자료 부족')
    if current['reading']['unit'] != previous['reading']['unit']:
        return dict(state='unit_mismatch', direction=None, direction_code=None,
                    signed_change=None, magnitude=None, unit=None, text='단위가 달라 비교 불가')
    a, b = Decimal(current['decimal_value']), Decimal(previous['decimal_value'])
    with localcontext() as ctx:
        ctx.prec = max(80,len(a.as_tuple().digits)+abs(a.adjusted())+abs(a.as_tuple().exponent)+5,
                       len(b.as_tuple().digits)+abs(b.adjusted())+abs(b.as_tuple().exponent)+5)
        signed = a-b
    magnitude = signed.copy_abs()
    code = 'increase' if signed>0 else 'decrease' if signed<0 else 'unchanged'
    direction = {'increase':'증가','decrease':'감소','unchanged':'동일'}[code]
    unit = current['reading']['unit']
    if signed == 0:
        text = '이전 기록과 동일'
    elif unit == UNIT:
        text = f'이전 기록보다 100엔당 {display(magnitude)}원 {"상승" if signed>0 else "하락"}'
    else:
        text = f'이전 기록보다 {display(magnitude)}{unit} {direction}'
    return dict(state='comparable',direction=direction,direction_code=code,
                signed_change=float(signed),magnitude=float(magnitude),unit=unit,
                signed_change_decimal=str(signed),magnitude_decimal=str(magnitude),
                previous_record_date=previous['reading']['record_date'],
                current_record_date=current['reading']['record_date'],text=text)


def retry_after(header, attempted_at):
    if header is None:
        return None, 'not_provided'
    if re.fullmatch(r'[0-9]+', str(header).strip()):
        return int(str(header).strip()), 'upstream_seconds'
    try:
        observed = parsedate_to_datetime(str(header))
        if observed.tzinfo is None:
            raise ValueError()
        return max(0,math.ceil((observed-iso_time(attempted_at)).total_seconds())), 'upstream_http_date'
    except (ValueError,TypeError,OverflowError):
        return None, 'invalid_upstream_header'


def classify_transport(transport):
    if transport.get('mode') == 'timeout' or transport.get('delay_ms',0)>transport.get('deadline_ms',20000):
        return 'timeout'
    if transport.get('mode') == 'offline':
        return 'offline'
    status = transport.get('status')
    if status in (401,403): return 'auth'
    if status == 429: return 'rate_limit'
    if not isinstance(status,int) or status < 200 or status >= 300: return 'schema_error'
    return None


class Store:
    def __init__(self, path, synthetic=False):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.synthetic = synthetic
        with self.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS daily_readings(
              record_id TEXT PRIMARY KEY, signal_id TEXT NOT NULL, record_date TEXT NOT NULL,
              reading_json TEXT NOT NULL, decimal_value TEXT NOT NULL, metadata_json TEXT NOT NULL,
              first_fetched_at TEXT NOT NULL, last_fetched_at TEXT NOT NULL,
              UNIQUE(signal_id,record_date));
            CREATE TABLE IF NOT EXISTS board_state(id INTEGER PRIMARY KEY CHECK(id=1),
              sequence INTEGER NOT NULL, payload TEXT NOT NULL);
            INSERT OR IGNORE INTO board_state VALUES(1,0,'{}');
            CREATE TABLE IF NOT EXISTS attempts(ticket INTEGER PRIMARY KEY,
              started_at TEXT NOT NULL, completed_at TEXT, outcome TEXT, error_code TEXT);
            CREATE TABLE IF NOT EXISTS success_snapshots(
              snapshot_id TEXT PRIMARY KEY, record_id TEXT NOT NULL,
              fetched_at TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TRIGGER IF NOT EXISTS snapshot_no_update BEFORE UPDATE ON success_snapshots
              BEGIN SELECT RAISE(ABORT,'immutable success snapshot'); END;
            CREATE TRIGGER IF NOT EXISTS snapshot_no_delete BEFORE DELETE ON success_snapshots
              BEGIN SELECT RAISE(ABORT,'immutable success snapshot'); END;
            CREATE TABLE IF NOT EXISTS migrations(name TEXT PRIMARY KEY,payload TEXT NOT NULL);
            """)
        self._migrate_legacy()
        self._retain_legacy_provenance()

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path,timeout=30)
        db.row_factory = sqlite3.Row
        try:
            with db: yield db
        finally: db.close()

    def _migrate_legacy(self):
        if self.synthetic: return
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute("SELECT 1 FROM migrations WHERE name='legacy_fx_v1'").fetchone(): return
            exists = db.execute("SELECT 1 FROM sqlite_master WHERE name='fx_daily' AND type='table'").fetchone()
            migrated=0
            if exists:
                for old in db.execute('SELECT payload FROM fx_daily ORDER BY query_date').fetchall():
                    saved = json.loads(old['payload'])
                    reading,exact,meta=normalize_live(saved['raw_response'],saved['queried_at'])
                    if Decimal(exact)!=Decimal(saved['normalized_value']):
                        raise ValueError('legacy raw response/value mismatch; migration stopped')
                    # Preserve legacy exact decimal spelling too.
                    exact=saved['normalized_value']
                    meta['legacy_first_success_unknown']=True
                    meta['legacy_payload']=saved
                    self._save(db,reading,exact,meta)
                    migrated+=1
                previous=db.execute("SELECT payload FROM fx_status WHERE id=1").fetchone() if db.execute("SELECT 1 FROM sqlite_master WHERE name='fx_status'").fetchone() else None
                oldstatus=json.loads(previous[0]) if previous else {}
                state={'status':{'freshness':'fresh','error_code':'none'} if oldstatus.get('ok',True) else {'freshness':'stale','error_code':'schema_error'},
                       'last_attempt_at':oldstatus.get('last_attempt_at'),'in_progress':False,'migration':True}
                db.execute('UPDATE board_state SET payload=? WHERE id=1',(json.dumps(state),))
            db.execute('INSERT INTO migrations VALUES(?,?)',('legacy_fx_v1',json.dumps({'legacy_rows_preserved':migrated,'legacy_tables_unchanged':True})))


    def _retain_legacy_provenance(self):
        if self.synthetic: return
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute("SELECT 1 FROM migrations WHERE name='legacy_provenance_v2'").fetchone(): return
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='fx_daily'").fetchone():
                for old in db.execute('SELECT payload FROM fx_daily').fetchall():
                    saved=json.loads(old['payload'])
                    row=db.execute('SELECT record_id,metadata_json,first_fetched_at FROM daily_readings WHERE signal_id=? AND record_date=?',
                                   (SIGNAL,kst_date(saved['queried_at']))).fetchone()
                    if row and row['first_fetched_at']==saved['queried_at']:
                        meta=json.loads(row['metadata_json'])
                        meta['legacy_first_success_unknown']=True
                        db.execute('UPDATE daily_readings SET metadata_json=? WHERE record_id=?',
                                   (json.dumps(meta,ensure_ascii=False),row['record_id']))
            db.execute('INSERT INTO migrations VALUES(?,?)',('legacy_provenance_v2','{"values_and_times_unchanged":true}'))

    def _save(self,db,reading,exact,metadata):
        existing=db.execute('SELECT record_id,metadata_json FROM daily_readings WHERE signal_id=? AND record_date=?',
                            (reading['signal_id'],reading['record_date'])).fetchone()
        metadata=dict(metadata)
        if existing and json.loads(existing['metadata_json']).get('legacy_first_success_unknown'):
            metadata['legacy_first_success_unknown']=True
        record_id=existing['record_id'] if existing else str(uuid.uuid4())
        db.execute("""INSERT INTO daily_readings VALUES(?,?,?,?,?,?,?,?)
          ON CONFLICT(signal_id,record_date) DO UPDATE SET
          reading_json=excluded.reading_json,decimal_value=excluded.decimal_value,
          metadata_json=excluded.metadata_json,last_fetched_at=excluded.last_fetched_at""",
          (record_id,reading['signal_id'],reading['record_date'],json.dumps(reading,ensure_ascii=False),
           exact,json.dumps(metadata,ensure_ascii=False),reading['fetched_at'],reading['fetched_at']))
        if not self.synthetic:
            snapshot=dict(kind='app_success_snapshot',record_id=record_id,reading=reading,
                          decimal_value=exact,display_value=display(exact),metadata=metadata,
                          official_receipt=False)
            db.execute('INSERT INTO success_snapshots VALUES(?,?,?,?)',
                       (str(uuid.uuid4()),record_id,reading['fetched_at'],json.dumps(snapshot,ensure_ascii=False)))

    def begin_attempt(self,attempted_at,guard=False):
        iso_time(attempted_at)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT sequence,payload FROM board_state WHERE id=1').fetchone()
            state=json.loads(row['payload'])
            if guard:
                until=state.get('retry_not_before')
                if until and iso_time(attempted_at)<iso_time(until): return None
                last=state.get('last_attempt_at')
                elapsed=(iso_time(attempted_at)-iso_time(last)).total_seconds() if last else 999
                if state.get('in_progress') and elapsed<25: return None
                if elapsed<3: return None
            ticket=row['sequence']+1
            state.update(last_attempt_at=attempted_at,in_progress=True)
            db.execute('UPDATE board_state SET sequence=?,payload=? WHERE id=1',(ticket,json.dumps(state)))
            db.execute('INSERT INTO attempts(ticket,started_at) VALUES(?,?)',(ticket,attempted_at))
            return ticket

    def process(self,ticket,transport,payload,normalizer,at,metadata_extra=None):
        error=classify_transport(transport)
        reading=exact=metadata=None
        if error is None:
            try:
                reading,exact,metadata=normalizer(payload,at)
                validate_reading(reading)
                decimal=Decimal(exact)
                if not decimal.is_finite() or float(decimal)!=reading['normalized_value']:
                    raise ValueError('decimal/numeric mapping mismatch')
                if not self.synthetic and (reading['signal_id']!=SIGNAL or reading['unit']!=UNIT):
                    raise ValueError('live signal mismatch')
            except Exception:
                error='schema_error'
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT sequence,payload FROM board_state WHERE id=1').fetchone()
            if row['sequence'] != ticket:
                db.execute("UPDATE attempts SET completed_at=?,outcome='ignored_late' WHERE ticket=?",(at,ticket))
            else:
                state=json.loads(row['payload'])
                if error is None:
                    metadata.update(metadata_extra or {})
                    self._save(db,reading,exact,metadata)
                status={'freshness':'stale','error_code':error} if error else {'freshness':'fresh','error_code':'none'}
                STATUS_VALIDATOR.validate(status)
                seconds,provenance=retry_after(transport.get('headers',{}).get('retry-after'),at) if error=='rate_limit' else (None,None)
                state.update(status=status,in_progress=False,retry_after_seconds=seconds,
                             retry_after_provenance=provenance,
                             retry_not_before=(iso_time(at)+timedelta(seconds=seconds)).isoformat() if seconds is not None else None,
                             last_completed_at=at,last_fixture_id=(metadata_extra or {}).get('fixture_id'),
                             message=ERRORS[error][0] if error else '정상 조회값입니다.',
                             next_action=ERRORS[error][1] if error else None)
                db.execute('UPDATE board_state SET payload=? WHERE id=1',(json.dumps(state,ensure_ascii=False),))
                db.execute('UPDATE attempts SET completed_at=?,outcome=?,error_code=? WHERE ticket=?',
                           (at,'error' if error else 'success',error or 'none',ticket))
        return self.snapshot()

    def replay(self,fixture):
        if not self.synthetic: raise ValueError('replay restricted to synthetic store')
        FIXTURE_VALIDATOR.validate(fixture)
        at=fixture['virtual_now']
        ticket=self.begin_attempt(at)
        return self.process(ticket,fixture['transport'],fixture['payload'],normalize_replay,at,
                            {'fixture_id':fixture['fixture_id']})

    def reset(self):
        if not self.synthetic: raise ValueError('live reset prohibited')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM daily_readings')
            db.execute('DELETE FROM attempts')
            db.execute("UPDATE board_state SET sequence=sequence+1,payload='{}' WHERE id=1")
        return self.snapshot()

    def snapshot(self):
        with self.connect() as db:
            db.execute('BEGIN')
            rows=db.execute('SELECT * FROM daily_readings ORDER BY record_date,signal_id').fetchall()
            state=json.loads(db.execute('SELECT payload FROM board_state WHERE id=1').fetchone()[0])
            snapshot_count=db.execute('SELECT COUNT(*) FROM success_snapshots').fetchone()[0]
        records=[]
        for row in rows:
            r=dict(record_id=row['record_id'],reading=json.loads(row['reading_json']),decimal_value=row['decimal_value'],
                   metadata=json.loads(row['metadata_json']),first_fetched_at=row['first_fetched_at'],
                   last_fetched_at=row['last_fetched_at'],display_value=display(row['decimal_value']))
            previous=next((p for p in reversed(records) if p['reading']['signal_id']==r['reading']['signal_id']
                           and p['reading']['record_date']<r['reading']['record_date']),None)
            r['comparison']=comparison(r,previous)
            records.append(r)
        return dict(records=records,current=records[-1] if records else None,status=state.get('status'),
                    attempt={k:v for k,v in state.items() if k!='status'},synthetic=self.synthetic,
                    snapshot_count=snapshot_count,official_receipt_count=0,
                    actual_dates=sorted({r['reading']['record_date'] for r in records}) if not self.synthetic else [],
                    evidence_waiting=not self.synthetic and len(records)<2)

    def snapshots(self):
        with self.connect() as db:
            return [dict(snapshot_id=r['snapshot_id'],**json.loads(r['payload']))
                    for r in db.execute('SELECT * FROM success_snapshots ORDER BY fetched_at,snapshot_id')]


def fixture_expected_check(result,fixture,prior=None,baseline_id=None):
    """Compare independent pipeline output to expected; never supplies application state."""
    expected=fixture['expected']
    current=result['current']
    status=result['status'] or {}
    observed=dict(freshness=status.get('freshness'),error_code=status.get('error_code'),
                  row_count=len(result['records']),
                  stored_value=current['reading']['normalized_value'] if current else None,
                  delta=current['comparison'].get('magnitude') if current else None)
    checks={k:observed.get(k)==expected[k] for k in ['freshness','error_code','row_count','stored_value','delta']}
    if expected.get('record_date'): checks['record_date']=current is not None and current['reading']['record_date']==expected['record_date']
    if expected.get('same_record_id_as'): checks['same_record_id']=baseline_id is not None and current['record_id']==baseline_id
    if prior and status.get('freshness')=='stale':
        checks['preserve_last_good']=prior['records']==result['records']
    else:
        checks['preserve_last_good']=expected['preserve_last_good'] and (not prior or len(result['records'])>=len(prior['records']))
    return dict(observed=observed,checks=checks,passed=all(checks.values()))
