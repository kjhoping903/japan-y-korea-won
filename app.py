"""100 JPY daily tracker. Run: python app.py (Python 3.10+; no dependencies)."""
import argparse
import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, localcontext, ROUND_HALF_UP
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
SOURCE = 'https://api.frankfurter.dev/v2/providers/ecb/rate/jpy/krw'
SIGNAL = 'jpy-krw-per-100-jpy'
UNIT = 'KRW/100 JPY'
KST = timezone(timedelta(hours=9), 'Asia/Seoul')


def display(value):
    with localcontext() as ctx:
        ctx.prec = max(60, len(str(value)) + 10)
        return format(Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP), 'f')


def comparison(current, previous):
    if previous is None:
        return '첫 저장 기록입니다.'
    with localcontext() as ctx:
        ctx.prec = 60
        delta = Decimal(current) - Decimal(previous)
    if delta == 0:
        return '이전 기록과 동일'
    return f'이전 기록보다 100엔당 {display(abs(delta))}원 {"상승" if delta > 0 else "하락"}'


def normalize(raw, queried_at):
    data = json.loads(raw, parse_float=Decimal, parse_int=Decimal)
    if not isinstance(data, dict):
        raise ValueError('원천 응답 형식 오류')
    base, quote = data.get('base'), data.get('quote')
    if (base, quote) not in [('JPY', 'KRW'), ('KRW', 'JPY')]:
        raise ValueError('기준 통화와 환산 방향이 JPY/KRW 쌍이 아닙니다.')
    rate = Decimal(str(data['rate']))
    if not rate.is_finite() or rate <= 0:
        raise ValueError('유효한 양수 환율이 아닙니다.')
    observed = date.fromisoformat(data['date'])
    if observed > queried_at.astimezone(KST).date():
        raise ValueError('출처 관측 날짜가 조회 날짜보다 미래입니다.')
    with localcontext() as ctx:
        ctx.prec = 60
        value = rate * 100 if base == 'JPY' else Decimal(100) / rate
    return dict(signal_id=SIGNAL, unit=UNIT, normalized_value=str(value),
                raw_rate=str(rate), base=base, quote=quote,
                formula='100 × rate' if base == 'JPY' else '100 ÷ rate',
                source_observed_date=observed.isoformat(),
                source_observed_at=None, source_time_precision='date',
                queried_at=queried_at.isoformat(),
                query_date=queried_at.astimezone(KST).date().isoformat(),
                raw_response=raw, source_url=SOURCE)


def fetch_source():
    request = Request(SOURCE, headers={'Accept': 'application/json', 'User-Agent': 'JPY-KRW-Daily/1.0'})
    with urlopen(request, timeout=20) as response:
        return response.read(65536).decode('utf-8')


class Store:
    def __init__(self, path):
        self.path = str(path)
        self.lock = threading.Lock()
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS fx_daily (query_date TEXT PRIMARY KEY, payload TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS fx_status (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        try:
            with db:
                yield db
        finally:
            db.close()

    def snapshot(self):
        with self.connect() as db:
            records = [json.loads(row[0]) for row in db.execute('SELECT payload FROM fx_daily ORDER BY query_date')]
            status = db.execute('SELECT payload FROM fx_status WHERE id=1').fetchone()
        for i, record in enumerate(records):
            record['display_value'] = display(record['normalized_value'])
            record['daily_comparison'] = comparison(record['normalized_value'], records[i-1]['normalized_value'] if i else None)
        return dict(records=records, status=json.loads(status[0]) if status else {})

    def refresh(self, fetcher=fetch_source, now=None):
        with self.lock:
            attempt = now or datetime.now(timezone.utc)
            try:
                raw = fetcher()
                queried_at = now or datetime.now(timezone.utc)
                if queried_at.tzinfo is None:
                    raise ValueError('조회 시각에 시간대가 필요합니다.')
                record = normalize(raw, queried_at)
                with self.connect() as db:
                    old = db.execute('SELECT payload FROM fx_daily ORDER BY query_date DESC LIMIT 1').fetchone()
                    previous = json.loads(old[0])['normalized_value'] if old else None
                    record['previous_normalized_value'] = previous
                    record['comparison'] = comparison(record['normalized_value'], previous)
                    db.execute('INSERT INTO fx_daily VALUES (?,?) ON CONFLICT(query_date) DO UPDATE SET payload=excluded.payload',
                               (record['query_date'], json.dumps(record, ensure_ascii=False)))
                    status = dict(ok=True, last_attempt_at=queried_at.isoformat())
                    db.execute('INSERT OR REPLACE INTO fx_status VALUES (1,?)', (json.dumps(status),))
            except Exception as exc:
                with self.connect() as db:
                    status = dict(ok=False, last_attempt_at=attempt.isoformat(), error=str(exc))
                    db.execute('INSERT OR REPLACE INTO fx_status VALUES (1,?)', (json.dumps(status),))
            return self.snapshot()


def serve(port=8000, db_path=ROOT / 'fx.sqlite3'):
    store = Store(db_path)

    class Handler(BaseHTTPRequestHandler):
        def send(self, body, kind='application/json; charset=utf-8', status=200):
            body = body.encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == '/api/records':
                self.send(json.dumps(store.snapshot(), ensure_ascii=False))
            elif self.path in ('/', '/index.html'):
                self.send((ROOT / 'index.html').read_text(encoding='utf-8'), 'text/html; charset=utf-8')
            else:
                self.send('{"error":"not found"}', status=404)

        def do_POST(self):
            if self.path != '/api/refresh':
                self.send('{"error":"not found"}', status=404)
                return
            # Reject cross-origin browser mutations; service is bound to loopback.
            origin = self.headers.get('Origin')
            if origin and origin != 'http://' + self.headers.get('Host', ''):
                self.send('{"error":"origin rejected"}', status=403)
                return
            result = store.refresh()
            self.send(json.dumps(result, ensure_ascii=False), status=200 if result['status']['ok'] else 502)

    print(f'Open http://127.0.0.1:{port}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--db', type=Path, default=ROOT / 'fx.sqlite3')
    args = parser.parse_args()
    serve(args.port, args.db)
