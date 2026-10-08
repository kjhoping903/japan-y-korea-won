"""Existing JPY/KRW board server. Run: python app.py"""
import argparse
import json
import os
import re
import socket
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fx_core import (ROOT, ASSETS, SOURCE, SIGNAL, UNIT, KST, Store, normalize_live,
                     normalize_replay, validate_reading, display, comparison,
                     fixture_expected_check, utc_now)

FETCH_POOL = ThreadPoolExecutor(max_workers=2,thread_name_prefix='upstream-read')
FIXTURES = {f['fixture_id']:f for f in
            [json.loads(p.read_bytes()) for p in sorted((ASSETS/'fixtures').glob('*.json'))]}


def fetch_source():
    request=Request(SOURCE,headers={'Accept':'application/json','User-Agent':'JPY-KRW-Daily/2.0'})
    with urlopen(request,timeout=20) as response:
        body=response.read(65537)
        if len(body)>65536: raise ValueError('upstream body exceeds limit')
        return body.decode('utf-8')


def refresh(store,fetcher=fetch_source,timeout=20):
    attempted=utc_now()
    ticket=store.begin_attempt(attempted,guard=True)
    if ticket is None: return store.snapshot()
    future=FETCH_POOL.submit(fetcher)
    transport={'mode':'http','status':200,'headers':{}}
    body=None
    try:
        body=future.result(timeout=timeout)
    except (FutureTimeout,socket.timeout,TimeoutError):
        future.cancel()  # In-flight I/O may finish, but cannot mutate state.
        transport={'mode':'timeout','status':None,'headers':{}}
    except HTTPError as exc:
        transport={'mode':'http','status':exc.code,'headers':{'retry-after':exc.headers.get('Retry-After')} if exc.headers else {}}
    except URLError as exc:
        transport={'mode':'timeout' if isinstance(exc.reason,(socket.timeout,TimeoutError)) else 'offline','status':None,'headers':{}}
    except (ConnectionError,OSError):
        transport={'mode':'offline','status':None,'headers':{}}
    except Exception:
        transport={'mode':'http','status':200,'headers':{}}
    return store.process(ticket,transport,body,normalize_live,utc_now())


def serve(port=8000,db_path=ROOT/'fx.sqlite3',host='127.0.0.1',runtime=None,public_origin=None):
    live=Store(db_path)
    runtime=Path(runtime or ROOT/'runtime')
    runtime.mkdir(parents=True,exist_ok=True)
    sessions={}
    session_lock=threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self,format,*args):
            # No request headers, client address, tokens or query strings in logs.
            pass

        def send(self,body,kind='application/json; charset=utf-8',status=200,cookie=None):
            body=body.encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type',kind)
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Length',str(len(body)))
            if cookie:
                secure='; Secure' if public_origin and public_origin.startswith('https://') else ''
                self.send_header('Set-Cookie','t04_replay='+cookie+'; Path=/; HttpOnly; SameSite=Strict'+secure)
            self.end_headers()
            self.wfile.write(body)

        def json(self,value,status=200,cookie=None):
            self.send(json.dumps(value,ensure_ascii=False,allow_nan=False),status=status,cookie=cookie)

        def session(self):
            cookie=SimpleCookie()
            try: cookie.load(self.headers.get('Cookie',''))
            except Exception: pass
            value=cookie['t04_replay'].value if 't04_replay' in cookie else ''
            new_cookie=None
            if not re.fullmatch('[a-f0-9]{32}',value):
                value=uuid.uuid4().hex
                new_cookie=value
            with session_lock:
                if value not in sessions:
                    sessions[value]={'store':Store(runtime/('replay-'+value+'.sqlite3'),synthetic=True),
                                     'baseline_id':None,'last_check':None,'lock':threading.Lock()}
                return sessions[value],new_cookie

        def do_GET(self):
            if self.path=='/api/records':
                self.json(live.snapshot())
            elif self.path=='/api/snapshots':
                self.json({'kind':'app_success_snapshot','official_receipt_count':0,
                           'mapping_status':'platform mapping not provided','snapshots':live.snapshots()})
            elif self.path=='/api/fixtures':
                self.json([{'fixture_id':f['fixture_id'],'description':f['description_ko']} for f in FIXTURES.values()])
            elif self.path=='/api/replay':
                s,cookie=self.session()
                result=s['store'].snapshot()
                result['expected_check']=s['last_check']
                self.json(result,cookie=cookie)
            elif self.path=='/health':
                self.json({'ok':True})
            elif self.path in ('/','/index.html'):
                self.send((ROOT/'index.html').read_text(encoding='utf-8'),'text/html; charset=utf-8')
            else:
                self.json({'error':'not_found'},404)

        def do_POST(self):
            origin=self.headers.get('Origin')
            allowed={public_origin} if public_origin else {'http://'+self.headers.get('Host',''),'https://'+self.headers.get('Host','')}
            if origin and origin not in allowed:
                self.json({'error':'origin_rejected'},403)
                return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if length<0 or length>8192: raise ValueError()
                body=json.loads(self.rfile.read(length) or b'{}')
                if not isinstance(body,dict): raise ValueError()
            except Exception:
                self.json({'error':'invalid_request'},400)
                return
            if self.path=='/api/refresh':
                result=refresh(live)
                failed=result.get('status') and result['status']['error_code']!='none'
                self.json(result,502 if failed else 200)
            elif self.path in ('/api/replay/run','/api/replay/reset'):
                s,cookie=self.session()
                with s['lock']:
                    if self.path.endswith('/reset'):
                        result=s['store'].reset()
                        s.update(baseline_id=None,last_check=None)
                    else:
                        fixture=FIXTURES.get(body.get('fixture_id'))
                        if not fixture:
                            self.json({'error':'unknown_fixture'},400,cookie=cookie)
                            return
                        prior=s['store'].snapshot()
                        result=s['store'].replay(fixture)
                        if fixture['fixture_id']=='T04-NORMAL-D1-A' and result['current']:
                            s['baseline_id']=result['current']['record_id']
                        check=fixture_expected_check(result,fixture,prior,s['baseline_id'])
                        s['last_check']=check
                        result['expected_check']=check
                self.json(result,cookie=cookie)
            else:
                self.json({'error':'not_found'},404)

    print(f'Open http://{host}:{port}',flush=True)
    ThreadingHTTPServer((host,port),Handler).serve_forever()


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=int(os.environ.get('PORT','8000')))
    parser.add_argument('--host',default=os.environ.get('BIND_HOST','127.0.0.1'))
    parser.add_argument('--db',type=Path,default=Path(os.environ.get('DB_PATH',str(ROOT/'fx.sqlite3'))))
    parser.add_argument('--runtime',type=Path,default=None)
    parser.add_argument('--public-origin',default=os.environ.get('PUBLIC_ORIGIN'))
    args=parser.parse_args()
    serve(args.port,args.db,args.host,args.runtime,args.public_origin)
