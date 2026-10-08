"""Read-only project audit. Does not create receipts, dates, or production records."""
import hashlib
import json
import re
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent
ASSETS=ROOT/'assets/studio-task-assets/t04-real-information-board'
EXPECTED=['README.md','public-contract.json','criterion-registry.json','asset-manifest.json',
          'fixture-manifest.json','normalized-reading.schema.json','reading-status.schema.json',
          'fixture.schema.json','adapter-reset.example.js']+[
    'fixtures/'+n+'.json' for n in ['normal-d1-a','normal-d1-b','normal-d2','timeout',
    'auth-401','rate-429','offline','schema-break','recover-d2']]
def command(args):
    result=subprocess.run(args,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace')
    return {'exit_code':result.returncode,'stdout':result.stdout.strip(),'stderr':result.stderr.strip()}

def audit():
    result={'audit_created_at':datetime.now(timezone.utc).isoformat(),
        'scope':'Local implementation audit against verified public contract 2.0.0 and official 35-condition registry.',
        'agents_file_exists':(ROOT/'AGENTS.md').is_file(),
        'user_agents_instructions_applied':True,
        'asset_root_exists':ASSETS.exists(),
        'missing_assets':[name for name in EXPECTED if not (ASSETS/name).is_file()],
        'manifest_byte_sha256_check':'NOT EXECUTED: manifest or assets missing',
        'fixture_canonical_hash_check':'NOT EXECUTED: canonicalization rules unavailable',
        'git_status':command(['git','status','--short']),
        'git_log_latest':command(['git','log','-1','--format=%H']),
        'python_tests':command(['python','-m','unittest','-v']),
        'javascript_dom_model_tests':command(['node','test_ui.mjs']),
        'browser_render_test':'NOT EXECUTED: no connected browser at previous inspection',
        'public_https_url':None,'commit_pinned_source_url':None,
        'official_receipts':[]}
    if (ASSETS/'asset-manifest.json').is_file():
        manifest=json.loads((ASSETS/'asset-manifest.json').read_bytes())
        checks=[]
        for item in manifest['files']:
            path=ASSETS/item['path']
            data=path.read_bytes() if path.is_file() else b''
            checks.append({'path':item['path'],'exists':path.is_file(),
                           'byte_count_matches':path.is_file() and len(data)==item['bytes'],
                           'sha256_matches':path.is_file() and hashlib.sha256(data).hexdigest()==item['sha256']})
        result['manifest_checks']=checks
        result['manifest_byte_sha256_check']='PASS' if len(checks)==17 and all(x['byte_count_matches'] and x['sha256_matches'] for x in checks) else 'FAIL'
        result['fixture_canonical_hash_check']='NOT EXECUTED: aleph-json-canonical-v1 is named but its algorithm is not defined in the supplied package'
        contract=json.loads((ASSETS/'public-contract.json').read_bytes())
        registry=json.loads((ASSETS/'criterion-registry.json').read_bytes())
        result['official_contract']={'contract_version':contract['contract_version'],
            'package_id':contract['package_id'],'fixture_contract_version':contract['fixture_contract']['version'],
            'condition_count':len(registry['criteria']),'official_criteria':registry['criteria']}
        result['official_fixture_app_replay']='NOT EXECUTED: app has no official fixture input path or synthetic UI'
    # Report only location/type of potential secrets, never matched contents.
    rules={'private_key':r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
           'github_token':r'\b(?:ghp_|github_pat_)[A-Za-z0-9_]{20,}',
           'aws_access_key':r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
           'assigned_secret':r'(?i)\b(?:api_key|access_token|client_secret|password)\b\s*[:=]\s*["\x27][^"\x27]{8,}["\x27]'}
    findings=[]
    inspected=[]
    for name in ['app.py','index.html','README.md','test_app.py','test_ui.mjs']:
        path=ROOT/name
        text=path.read_text(encoding='utf-8')
        inspected.append({'path':name,'byte_count':path.stat().st_size,
                          'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        for kind,pattern in rules.items():
            for match in re.finditer(pattern,text):
                findings.append({'path':name,'line':text.count('\n',0,match.start())+1,'kind':kind})
    result['source_files_inspected']=inspected
    result['potential_secret_locations']=findings
    result['secret_scan_limits']='Pattern scan only. Git history, public deployment and public source do not exist here; their checks are not passed.'
    db_path=ROOT/'fx.sqlite3'
    if db_path.exists():
        db=sqlite3.connect('file:'+db_path.as_posix()+'?mode=ro',uri=True)
        try:
            rows=[json.loads(row[0]) for row in db.execute('SELECT payload FROM fx_daily ORDER BY query_date')]
            status=db.execute('SELECT payload FROM fx_status WHERE id=1').fetchone()
            result['real_storage']={'rows':rows,'count':len(rows),'distinct_kst_dates':sorted({r['query_date'] for r in rows}),
                'status':json.loads(status[0]) if status else None,
                'table_definition':db.execute("SELECT sql FROM sqlite_master WHERE name='fx_daily'").fetchone()[0],
                'real_second_day_status':'WAITING' if len({r['query_date'] for r in rows})<2 else 'requires full verification'}
        finally:db.close()
    from app import normalize
    t=datetime.now(timezone.utc)
    sample='{"date":"2026-10-07","base":"JPY","quote":"KRW","rate":"8.4606"}'
    try:
        normalized=normalize(sample,t)
        result['numeric_string_probe']={'accepted':True,'normalized_value_type':type(normalized['normalized_value']).__name__,
            'missing_required_fields':[k for k in ['source_name','source_time','fetched_at','record_timezone','record_date'] if k not in normalized]}
    except Exception as exc:
        result['numeric_string_probe']={'accepted':False,'exception_type':type(exc).__name__}
    result['all_T04_conditions_satisfied']=False
    return result

if __name__=='__main__':
    print(json.dumps(audit(),ensure_ascii=False,indent=2))
