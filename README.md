# 오늘의 엔화 환율 — T04 기존 프로젝트 개선

기존 Python HTTP 서버·SQLite·HTML/JavaScript 그래프를 유지했습니다. 실제 지표는 일본 엔화 100 JPY에 해당하는 KRW 금액이며 실제·합성 저장소를 분리합니다.

## 실행

Python 3.10 이상:

```powershell
python -m pip install -r requirements.txt
python app.py
```

로컬 주소는 http://127.0.0.1:8000 입니다. 실제 저장 파일은 fx.sqlite3입니다. 버튼을 누르면 실제 API를 조회합니다. 자동 수집은 없습니다.
브라우저 저장소를 실제 기록 보관에 사용하지 않습니다. 새 브라우저 컨텍스트도 서버의 실제 기록을 조회합니다.

## 원천 선택과 실제 의미

공식 문서: https://frankfurter.dev/
실제 HTTPS 호출: https://api.frankfurter.dev/v2/providers/ecb/rate/jpy/krw
ECB 설명: https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html

API 키 없는 비개인 공개 동적 환율을 제공하고, ECB provider 경로로 출처를 한정할 수 있어 선택했습니다.
일별 기준환율이며 실시간/은행 현찰 매매율이 아닙니다. ECB는 영업일 약16:00 CET에 발표하고 TARGET 휴무일은 제외합니다. API 반영 지연이 있을 수 있습니다.
공식 API 문서상 고정 일/월 할당량은 없지만 남용 방지 rate limiting이 있습니다. 사용 조건은 해당 공급자의 조건을 따릅니다.
실제 응답의 Access-Control-Allow-Origin=*도 확인했으나 이 앱은 서버에서 호출합니다.
원천이 날짜만 제공하므로 source_time=null이며 화면에 “출처 시각 미제공 · 원천 기준일”을 표시합니다. 발표 예정 시각을 실제 관측 시각으로 저장하지 않습니다.

## 정본과 공통 형식

고정자산: assets/studio-task-assets/t04-real-information-board/
공개 계약2.0.0, package ID aleph-t04-real-information-board-public-contract-v2, fixture 계약1.1.0, 조건35개.
manifest 자체를 제외한17개 파일의 원본 바이트 수·SHA-256 모두 일치. 원본/작업 사본의 값을 변경하지 않았습니다.
fixture canonicalization 이름만 제공되어 알고리즘 정의가 없는 canonical hash 검증은 미실행입니다.

fx_core.py는 제공 JSON Schema를 Draft202012Validator와 FormatChecker로 직접 적용합니다.
정규화 reading은 정확히9개 필드:
signal_id, normalized_value, unit, source_name, source_url, source_time, fetched_at, record_timezone, record_date.
숫자 문자열·bool·NaN·Infinity·누락/추가 필드·잘못된 타입/URL/시각을 거절합니다.
record_date는 시간대가 포함된 fetched_at을 KST로 변환하며 기기 기본 시간대나 UTC 문자열 자르기를 사용하지 않습니다.
실제·합성 경로는 Store.process → 공통 검증 → 원자 저장 → 상태 갱신 → Decimal 비교 → 공통 snapshot을 사용합니다.

## 정밀도·환산·비교

실제 signal_id=jpy-krw-per-100-jpy, unit=KRW/100 JPY.
원자료 JSON의 소수 토큰을 직접 Decimal로 읽습니다.
JPY 기준 KRW면100×rate, KRW 기준 JPY면100÷rate. 다른 통화 쌍·0 이하·필요값 누락은 거절합니다.
곱셈은 원자료 자리수를 수용하는 정밀도로 계산합니다. 나눗셈은 최소60자리 유효숫자와 ROUND_HALF_EVEN을 사용합니다.
정본 normalized_value는 유한한 숫자(binary64 인터페이스)이고, 별도 decimal_value TEXT에 계산 정밀도를 보존합니다. float에서 원본 정밀도가 복원된다고 주장하지 않습니다.
표시만 소수점 둘째 자리 ROUND_HALF_UP으로 반올림하며, 비교는 decimal_value로 계산합니다.
signed_change=나중값−이전값, magnitude=절대값, direction=증가/감소/동일을 별도로 반환합니다.
last_delta와 대응되는 magnitude는 절대 변화량이므로 부호를 대신하지 않습니다.
단위가 다르면 비교 불가, 이전 기록이 없으면 비교 자료 부족.
비교 날짜를 표시하며 누락일이 있으면 어제 값이라고 부르지 않습니다.
아주 작은 비영 변화는0.00원 상승/하락으로 보일 수 있고 원본 차이는 검증 영역에 남습니다.

## 저장·기존 기록 보존

daily_readings: UNIQUE(signal_id,record_date), 불변 record_id, first_fetched_at, 갱신 last_fetched_at.
BEGIN IMMEDIATE와 ON CONFLICT upsert로 중복을 막습니다.
기존 fx_daily/fx_status 테이블은 변경/삭제하지 않고 새 구조로 복사했습니다.
백업은 backups/fx-before-t04-migration.sqlite3이며 Git 제외입니다.
이전 앱이 최초 성공 시각을 저장하지 않아 마이그레이션 첫 시각은 원본에 보존된 정상 조회 시각입니다. 그보다 앞선 성공 시각은 알 수 없다는 안내를 유지합니다.
신규 기록부터 최초/마지막 성공 시각을 정상적으로 구분합니다.
모든 정상 조회마다 success_snapshots에 불변 스냅샷을 남깁니다. SQL trigger로 수정·삭제를 차단합니다.
스냅샷은 app_success_snapshot이며 공식 t04_day 영수증이 아닙니다.
실패는 정상 행·정상 출처/시각을 건드리지 않고 attempts와 board_state만 갱신합니다.
조회 순번이 더 최근 시도와 다르면 늦게 온 성공·실패를 저장하지 않습니다.

## 오류·재시도

timeout: 실제20초 전체 대기 제한. 요청 I/O가 늦게 끝나도 상태를 바꾸는 callback은 없으며 결과를 폐기합니다.
auth: 외부401/403, 원천 거절 설명. 제출 앱 로그인은 없습니다.
rate_limit:429, Retry-After 숫자 초와 HTTP 날짜를 해석합니다. 미제공/무효는 별도 provenance이며 대기 시간을 지어내지 않습니다.
offline: 서버↔원천 연결 실패를 안내하며 사용자 기기 오프라인으로 단정하지 않습니다.
schema_error: HTTP200도 payload/정규화 검증에 실패하면 정상 저장하지 않습니다.
fresh/none 또는 stale/해당 error_code를 사용하고, 정상값이 있으면 “오래된 값 · 마지막 정상 조회값”, 없으면 “아직 정상 데이터 없음”을 표시합니다.
실제 조회의 in-flight/cooldown/최소3초 간격 guard와 클라이언트 버튼 비활성화로 반복 클릭을 제어합니다.
오류 응답에는 원천 에러 본문·비밀 헤더·내부 예외 문자열을 공개하지 않습니다.

TIMEOUT 시험 시작 버튼은 reset→D1-A→D1-B→TIMEOUT을 순서대로 실행합니다. 실제 조회→시험 시작→다시 시도의3번 행동으로 확인할 수 있습니다.

## 합성 시험 순서

별도 runtime/replay-<임의 세션>.sqlite3 저장소를 사용합니다. 쿠키는 인증이 아니라 시험 세션 구분이며 계정이 필요 없습니다.
reset은 그 세션의 합성 상태만 초기화합니다. 실제 기록·실제 상태·불변 스냅샷을 보존합니다.
fixture.expected는 fixture_expected_check 결과 비교에만 사용합니다. transport/payload 처리 결과를 화면에 표시합니다.

- 정상: reset → D1-A → D1-B → D2
- 같은 날3회: reset → D1-A → D1-B → D1-B → D2
- 각 실패: reset → D1-A → D1-B → 실패 fixture 하나
- 복구: reset → D1-A → D1-B → TIMEOUT → 다시 시도 · RECOVER-D2

D1-A100pt/1행, D1-B105pt/동일ID·최초시각/1행, 각 실패105pt/1행·stale/오류, D2120pt/2행·15pt 증가.
RECOVER-D2는 fresh/none·120pt·2행. 재실행도 신규 중복행이 없습니다.
RATE-429의60초는 합성 시계 기준입니다. RECOVER-D2의 다음 가상 날짜로 복구하며 현실60초를 기다릴 필요가 없습니다.
합성 UI는 “합성 시험 데이터 · 실제 이틀 증거로 사용 불가”와 원래 aleph-demo-index/pt를 유지합니다.

## 그래프·모바일

현재 값·표·그래프는 동일한 서버 records에서 생성합니다.
KST 조회 날짜당 점 하나, 같은 날 갱신/다음 날 추가, 실패 시 보존, 미수집 날짜는 만들지 않습니다.
0건 빈 상태,1건 점과 둘째 날짜 대기,2건 이상 날짜순 연결선.
축 최소/최대/5개 눈금과 단위를 표시합니다. 누락 날짜의 연결선은 중간 관측값/보간을 뜻하지 않습니다.
점의 날짜·금액·출처 관측 시각/기준일·정상 조회 시각을 hover/click/키보드로 확인합니다.
그래프는 화면 폭에 반응하며 넓은 표는 가로 스크롤합니다.

## 검증

```powershell
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python -m unittest -v
node test_ui.mjs
python test_browser.py
python audit_t04.py
```

Python13개 테스트: 정본 스키마·문자열 거절·Decimal, 공식 정상/실패5종/복구,3회 동일날/다음날,24개 동시 요청, 늦은 응답, timeout 폐기, 실제HTTP오류 분류/제한, KST 경계, 단위 비교, 마이그레이션·스냅샷·실제/합성 격리.
실제Chromium9개 검사: 실제 API조회/저장/표/그래프, 공식 정상 순서, 실패5종, 사용자가 누르는 복구, 새 컨텍스트 데이터/합성 분리, 모바일과 키보드.
Node DOM 시험은 누락 날짜를 포함한 그래프 상태를 격리 합성 입력으로 검사하며 실제 이틀 증거가 아닙니다.
이 결과는 artifacts/browser-results.json과 T04-audit-evidence.json에 있습니다. 공개 HTTPS 시크릿 창 검증은 별개입니다.

## 배포

기존 Python 스택을 유지하는 Dockerfile/compose.yaml/Caddyfile을 준비했습니다.
SQLite와 시험 데이터는 fx-data 영속 볼륨, HTTPS 인증서도 별도 영속 볼륨을 사용합니다.
첫 실행 시 보존된 실제 seed DB를 빈 영속 볼륨에 한 번만 복사하며 기존 볼륨을 덮어쓰지 않습니다.
실제 소유 도메인을 서버 IP로 연결하고 BOARD_DOMAIN 환경변수를 설정한 뒤 docker compose up -d --build.
컨테이너 재생성·서버 재시작 후 기록 유지와 공개 접근을 실제로 검증해야 합니다.
현재 Docker CLI는 있으나 엔진이 실행되지 않아 이미지 빌드/컨테이너 배포 검증은 미실행입니다.
이 환율 프로젝트의 기존 원격 배포 서버·도메인은 확인되지 않았습니다. 다른 Sites 프로젝트를 변경하지 않았습니다.
공개 HTTPS 결과물 주소를 지어내지 않습니다.

## 실제 둘째 날·공식 영수증·제출

현재 확인된 실제 KST 날짜와 수는 T04-audit-evidence.json에 기록합니다. 실제2026-10-08 기록을 보존했고 이번 실제 조회도 같은 KST 날짜로 갱신했습니다.
다른 실제 KST 날짜에 실제 정상 재조회해야 합니다. 같은 원천 값이어도 저장할 수 있습니다. 실제 둘째 날 대기를 구현 시간과 구분합니다.
제출정보.json.과정영수증[]에 t04_day 공식 봉인 영수증 정확히2건, 서로 다른 server_created_at KST 날짜가 필요합니다.
발급 경로와 source_time→source_observed_at 플랫폼 매핑은 제공 문서/도구에서 확인되지 않았습니다.
원천 관측 시각 미제공은 앱에서null로 보존하지만 플랫폼 매핑/서명 유효성은 공식 문서 확인 후 대조해야 합니다.
일반 스냅샷/JSON/자체해시를 공식 영수증으로 만들지 않습니다. 현재 공식 영수증0건.
각 영수증의4필드를 해당 불변 스냅샷/표시값과 대조하고 두 봉인server_created_at 순서로 같은 단위 변화값을 재계산해야 합니다.
확인 방법4줄/학생 판단3줄 초안은 SUBMISSION.md에 있으며 학생 미확인 판단은 작성 필요로 남깁니다.
35개 조건의 실제 충족/미충족과 다음 행동은 T04-AUDIT.md와 T04-criteria-audit.json을 확인하세요.
