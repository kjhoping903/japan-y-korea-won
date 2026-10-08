"""Import official bytes without modifying Downloads originals."""
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ARCHIVE = Path.home() / 'Downloads/t04-real-information-board-public-v1.zip'
PREFIX = 't04-real-information-board-public-v1/'
DEST = ROOT / 'assets/studio-task-assets/t04-real-information-board'
with zipfile.ZipFile(ARCHIVE) as archive:
    manifest = json.loads(archive.read(PREFIX+'asset-manifest.json'))
    assert len(manifest['files']) == 17
    assert len(archive.namelist()) == 18
    assert manifest['self_excluded'] == 'asset-manifest.json'
    contract = json.loads(archive.read(PREFIX+'public-contract.json'))
    assert contract['contract_version'] == '2.0.0'
    assert contract['package_id'] == 'aleph-t04-real-information-board-public-contract-v2'
    assert contract['fixture_contract']['version'] == '1.1.0'
    registry = json.loads(archive.read(PREFIX+'criterion-registry.json'))
    assert [x['id'] for x in registry['criteria']] == ['T04-C'+str(n).zfill(2) for n in range(1,36)]
    checks=[]
    for item in manifest['files']:
        data=archive.read(PREFIX+item['path'])
        digest=hashlib.sha256(data).hexdigest()
        checks.append(dict(path=item['path'],bytes_actual=len(data),bytes_expected=item['bytes'],
                           sha256_actual=digest,sha256_expected=item['sha256'],
                           matched=len(data)==item['bytes'] and digest==item['sha256']))
    assert all(x['matched'] for x in checks)
    download_matches=[]
    for name in ['README.md','public-contract.json','asset-manifest.json']:
        original=ARCHIVE.parent/name
        download_matches.append(dict(path=name,matches_archive=original.read_bytes()==archive.read(PREFIX+name)))
    assert all(x['matches_archive'] for x in download_matches)
    for name in archive.namelist():
        assert name.startswith(PREFIX)
        relative=Path(name[len(PREFIX):])
        assert not relative.is_absolute() and '..' not in relative.parts
        target=DEST/relative
        data=archive.read(name)
        assert not target.exists() or target.read_bytes()==data
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(data)
    report=dict(contract_version=contract['contract_version'],package_id=contract['package_id'],
                fixture_contract_version=contract['fixture_contract']['version'],
                condition_count=len(registry['criteria']),archive_entry_count=len(archive.namelist()),
                source_archive_sha256=hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),
                download_matches=download_matches,raw_byte_hash_checks=checks,all_17_matched=True,
                fixture_canonical_hash_check='NOT_EXECUTED: named aleph-json-canonical-v1 rules not defined in supplied files')
    (ROOT/'T04-assets-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('17/17 byte counts and SHA-256 matched; 18 working copies; originals unchanged')
    for item in registry['criteria']:
        print(item['id'],item['condition_text_ko'])
    for name in ['fixture.schema.json','fixtures/normal-d1-b.json','fixtures/rate-429.json','fixtures/schema-break.json']:
        print(name)
        print(archive.read(PREFIX+name).decode('utf-8'))
