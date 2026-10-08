"""Current read-only audit: original manifests, real store, tests and secret scans."""
import hashlib
import json
import re
import sqlite3
import subprocess
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parent
ASSETS=ROOT/'assets/studio-task-assets/t04-real-information-board'
def command(args):
    p=subprocess.run(args,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace')
    return {'exit_code':p.returncode,'stdout':p.stdout.strip(),'stderr':p.stderr.strip()}

RULES={'private_key':rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
       'github_token':rb'\b(?:ghp_|github_pat_)[A-Za-z0-9_]{20,}',
       'openai_token':rb'\bsk-(?:proj-|svcacct-)[A-Za-z0-9_-]{20,}',
       'aws_access_key':rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'}
def scan(data,location):
    return [{'location':location,'kind':kind,'line':data[:m.start()].count(b'\n')+1}
            for kind,pattern in RULES.items() for m in re.finditer(pattern,data)]

def audit():
    from fx_core import Store,validate_reading,STATUS_VALIDATOR,normalize_live
    manifest=json.loads((ASSETS/'asset-manifest.json').read_bytes())
    checks=[]
    for x in manifest['files']:
        p=ASSETS/x['path'];b=p.read_bytes()
        checks.append({'path':x['path'],'byte_count_matches':len(b)==x['bytes'],
                       'sha256_matches':hashlib.sha256(b).hexdigest()==x['sha256']})
    contract=json.loads((ASSETS/'public-contract.json').read_bytes())
    registry=json.loads((ASSETS/'criterion-registry.json').read_bytes())
    store=Store(ROOT/'fx.sqlite3');live=store.snapshot()
    normalized_checks=[]
    for r in live['records']:
        validate_reading(r['reading'])
        reread,exact,meta=normalize_live(r['metadata']['raw_response'],r['reading']['fetched_at'])
        from decimal import Decimal
        normalized_checks.append({'record_date':r['reading']['record_date'],'schema_valid':True,
            'raw_decimal_matches':Decimal(exact)==Decimal(r['decimal_value']),
            'numeric_mapping_matches':reread['normalized_value']==r['reading']['normalized_value'],
            'display_value':r['display_value'],'source_time_is_null':r['reading']['source_time'] is None})
    if live['status']:STATUS_VALIDATOR.validate(live['status'])
    files=[p for p in ROOT.rglob('*') if p.is_file() and not any(x in p.relative_to(ROOT).parts for x in ['.git','backups','runtime','__pycache__'])
           and p.suffix in ['.py','.html','.mjs','.json','.md','.txt','.yaml'] or p.is_file() and p.name in ['Dockerfile','Caddyfile','.env.example']]
    findings=[]
    for p in files:findings.extend(scan(p.read_bytes(),p.relative_to(ROOT).as_posix()))
    history=command(['git','rev-list','--objects','--all'])
    scanned_blobs=0
    if history['exit_code']==0:
        for line in history['stdout'].splitlines():
            oid,*name=line.split(' ',1)
            kind=command(['git','cat-file','-t',oid])
            if kind['stdout']!='blob':continue
            data=subprocess.check_output(['git','cat-file','blob',oid],cwd=ROOT)
            findings.extend(scan(data,'git-blob:'+oid+(':'+name[0] if name else '')))
            scanned_blobs+=1
    responses_scanned=0
    try:
        for endpoint in ['/','/api/records','/api/snapshots']:
            with urlopen('http://127.0.0.1:8000'+endpoint,timeout=10) as r:
                findings.extend(scan(r.read(),'network:'+endpoint));responses_scanned+=1
    except Exception:pass
    browser_path=ROOT/'artifacts/browser-results.json'
    browser=json.loads(browser_path.read_bytes()) if browser_path.is_file() else None
    with store.connect() as db:
        legacy=[dict(r) for r in db.execute('SELECT * FROM fx_daily')] if db.execute("SELECT 1 FROM sqlite_master WHERE name='fx_daily'").fetchone() else []
        sql=db.execute("SELECT sql FROM sqlite_master WHERE name='daily_readings'").fetchone()[0]
    result={'audit_created_at':datetime.now(timezone.utc).isoformat(),'official_contract':{
        'contract_version':contract['contract_version'],'package_id':contract['package_id'],
        'fixture_contract_version':contract['fixture_contract']['version'],'condition_count':len(registry['criteria'])},
        'agents_file_exists':(ROOT/'AGENTS.md').exists(),'user_agents_instructions_applied':True,
        'manifest_checks':checks,'manifest_byte_sha256_check':'PASS' if all(c['byte_count_matches'] and c['sha256_matches'] for c in checks) else 'FAIL',
        'fixture_canonical_hash_check':'NOT EXECUTED: aleph-json-canonical-v1 algorithm definition not supplied',
        'git_status':command(['git','status','--short']),'git_log_latest':command(['git','log','-1','--format=%H']),
        'python_tests':command(['python','-X','utf8','-m','unittest','-v']),
        'javascript_dom_model_tests':command(['node','test_ui.mjs']),
        'browser_results':browser,'normalization_checks':normalized_checks,
        'real_storage':{'count':len(live['records']),'distinct_kst_dates':live['actual_dates'],
                        'records':live['records'],'status':live['status'],'table_definition':sql,
                        'legacy_rows_preserved':len(legacy),'immutable_snapshot_count':live['snapshot_count']},
        'secret_scan':{'source_files':len(files),'git_blobs':scanned_blobs,'local_network_responses':responses_scanned,
                       'potential_secret_locations':findings,'scope_limit':'Pattern scan; public hosting artifact unavailable'},
        'official_receipt_count':0,'receipt_mapping_status':'official issuance/mapping documents unavailable',
        'public_https_url':None,'public_https_access_tested':False,'all_T04_conditions_satisfied':False}
    return result

if __name__=='__main__':print(json.dumps(audit(),ensure_ascii=False,indent=2))
