# T04 정본 고정자산 확인 후 통과기준 검사

전체 통과가 아닙니다. 이번에는 실제 정본 criterion-registry의 35개 조건을 모두 읽고 정확한 조건 문구로 검사표를 갱신했습니다. 이전의 “고정자산 누락” 사유는 해소됐습니다. 기존 앱 코드는 보존하고 검증 코드·증거·보고서를 갱신했습니다.

## 고정자산 검증 결과

- 사용자 지정 Downloads README.md·public-contract.json·asset-manifest.json과 같은 폴더의 t04-real-information-board-public-v1.zip을 확인했습니다.
- 압축파일 18개 entry 중 manifest 자체를 제외한 17개 파일의 바이트 수·원본 바이트 SHA-256 모두 일치했습니다. 제공된 세 파일도 ZIP 내부 파일과 바이트 단위로 일치했습니다.
- 공개 계약 2.0.0, package ID aleph-t04-real-information-board-public-contract-v2, fixture 계약 1.1.0, T04-C01~C35의 35개 조건 확인.
- 해시/바이트 불일치 0건, 계약 버전 충돌 0건, 누락 0건.
- 원본 Downloads 파일은 변경하지 않았습니다. 작업용 사본은 assets/studio-task-assets/t04-real-information-board/ 아래에 원본 바이트 그대로 배치했습니다.
- fixture-manifest는 canonicalization=aleph-json-canonical-v1이라는 이름만 제공합니다. 이 패키지에는 키 순서·문자열 escaping·숫자 직렬화 등의 알고리즘 정의가 없습니다. canonical hash 검증은 미실행입니다. 원본 바이트 해시로 대신 검사하지 않았습니다.
- 증거: T04-assets-verification.json. 재검증: python import_t04_assets.py

## 실제 수행한 검사와 한계

- AGENTS.md 파일 없음. 대화의 AGENTS 지침 적용. 기존 README·app.py·index.html·테스트와 정본 18개 파일 확인.
- Python 표준 라이브러리 HTTP 서버/SQLite/HTML·JavaScript SVG 스택 보존.
- git status 및 git log -1 실패: Git 저장소 아님. commit 식별자/공개 소스 주소 생성 안 함.
- Python 자체 테스트 2개 통과, JavaScript DOM 모형 테스트 통과. 해당 결과는 T04-audit-evidence.json에 있습니다. 공식 fixture 앱 재생/실제 브라우저 렌더링/공개 시크릿 창 검증의 통과로 표시하지 않았습니다.
- 실제 원자료 8.4606 × 100 = DB 정밀 문자열 846.0600 → API display_value 846.06 대조. 실제 DB 날짜는 2026-10-08 하루 1행. source 관측 날짜는 2026-10-07, 정확한 관측 시각은 미제공/null.
- 현재 공개 API 응답은 T04-source-response.json에 보존돼 있습니다. 이 파일은 실제 날짜별 앱 기록 또는 플랫폼 봉인 영수증이 아닙니다.
- 공식 정상 fixture의 signal_id/값/pt 단위는 그대로 보존했습니다. 앱에 적용·재생하는 경로는 현재 없습니다. 참고 adapter만 실행해 앱이 통과한 것으로 대체하지 않았습니다.
- 원자료·정규화·저장 구조를 정본 스키마와 비교했습니다. normalized_value는 number 필수이나 앱은 문자열입니다. source_name/source_time/fetched_at/record_timezone/record_date 필드가 없고 additionalProperties=false에도 불구하고 별도 필드들을 포함합니다. 상태도 freshness/error_code가 아닌 ok/error 형식입니다.
- 문자열 raw rate를 숫자로 자동 변환하는 별도 진단 probe는 기존 코드에서 성공합니다. 공식 schema-break의 normalized_value="105"를 실제 앱 경로로 재생한 결과라고 주장하지 않습니다.
- 현재 소스5개에서 비밀키 패턴 0건. 공개 배포·네트워크 전 범위·Git 기록·최종 제출물 검사 미완료. 소스 패턴 검사는 비밀값 부재의 완전한 증명이 아닙니다.
- 브라우저가 연결되지 않아 실제 화면·모바일·새 시크릿 창 접근 검사는 미실행입니다.

## 주요 보완 사항

공통 스키마 정규화/검증과 별도의 정밀 저장값, live/replay 공유 처리 함수, 실제/합성 분리 저장소, 공식 fixture 재생 UI/reset, 실패5종 상태·안내·Retry-After·복구, signal_id+record_date 복합 고유키, 유지되는 record ID와 최초 조회 시각, 단위 일치 비교, 봉인 시점의 불변 스냅샷을 구현해야 합니다.
화면에는 실제 출처 직접 링크와 Asia/Seoul (KST, UTC+09:00), 명시적인 신선도와 오류를 보완해야 합니다. 현재 그래프/표는 같은 records를 사용하며 일반 실패 후 기존 기록을 보존하지만 공식 다섯 실패 경로는 미검증입니다.

## 35개 정본 조건별 검사표

판정 “미충족”에는 아직 실행하지 못한 검사와 공개 제출 증거 대기가 포함됩니다. 현재 앱에 이미 구현된 기능이 전부 잘못됐다는 뜻이 아닙니다. 검증 근거가 충분하지 않은 공식 조건을 충족으로 추정하지 않습니다.

| 조건 ID | 정본 조건 | 실제 확인한 내용 | 검증 방법·증거 위치 | 판정 | 다음 행동 |
|---|---|---|---|---|---|
| T04-C01 | 제출한 모든 URL(결과물·소스)은 계정 생성 없이 새 시크릿 창에서 열린다. | 공개 결과물·소스 URL 미확보; 새 시크릿 창에서 계정 생성 없는 접근 미실행. | 정본 조건과 앱 코드/README/저장값 비교; T04-audit-evidence.json; T04-source-response.json | 미충족 | 실제 HTTPS 두 주소 확보 후 새 시크릿 창 확인. |
| T04-C02 | 제출한 모든 URL(결과물·소스)은 로그인 없이 새 시크릿 창에서 열린다. | 공개 결과물·소스 URL 미확보; 로그인 없는 접근 미실행. | 정본 조건과 앱 코드/README/저장값 비교; T04-audit-evidence.json; T04-source-response.json | 미충족 | 배포 후 결과물·전체 소스 두 주소에 로그인 없이 접근 확인. |
| T04-C03 | 비개인 공개 원천의 실제 동적 값을 조회할 수 있다. | 실제 공개 환율 API 응답과 로컬 정상 저장 1건 확인. verification_mode=live_receipt_and_review의 공개 심사·봉인 증거는 미완료. | 정본 조건과 앱 코드/README/저장값 비교; T04-audit-evidence.json; T04-source-response.json | 미충족 | 공개 실제 조회 화면과 정식 영수증 증거 확보. |
| T04-C04 | 실제 조회 화면에 값이 표시된다. | 현재 저장값 846.0600, API display_value 846.06 및 화면 render 로직 확인. 실제 브라우저 화면·공식 fixture 경로는 미검증. | 정본 조건과 앱 코드/README/저장값 비교; T04-audit-evidence.json; T04-source-response.json | 미충족 | 브라우저 실제 조회 화면과 공식 정상 fixture 재생 확인. |
| T04-C05 | 실제 조회 화면에 단위가 표시된다. | KRW/100 JPY와 KRW 화면 단위 구현 확인. 실제 브라우저 화면·pt 공식 fixture 경로는 미검증. | 정본 조건과 앱 코드/README/저장값 비교; T04-audit-evidence.json; T04-source-response.json | 미충족 | 실제 화면 및 분리 합성 영역의 pt 단위 보존 확인. |
| T04-C06 | 실제 조회 화면에 출처가 표시된다. | Frankfurter/ECB 설명과 공식 문서 링크 구현 확인. 첫 화면에 실제 조회 endpoint를 직접 가리키는 출처 링크가 없음. | 정본 조건과 앱 코드/README/저장값 비교; T04-audit-evidence.json; T04-source-response.json | 미충족 | 첫 화면에 실제 출처 링크 추가하고 실제 렌더링 확인. |
| T04-C07 | 실제 조회 화면에 출처 시각이 표시된다. | 관측 날짜 2026-10-07와 관측 시각 미제공 표시 로직 확인. 공통 source_time 필드와 공식 null fixture 처리 없음. | 정본 조건과 앱 코드/README/저장값 비교; T04-audit-evidence.json; T04-source-response.json | 미충족 | source_time=null 공통 형식 및 출처 시각 미제공 표시, D1-B 앱 재생 확인. |
| T04-C08 | 실제 조회 화면에 조회 시각이 표시된다. | 마지막 정상 queried_at을 별도로 저장하며 실패 후 보존하는 자체 테스트 통과. 공통 fetched_at 형식·공식 재생·실제 화면 미검증. | 정본 조건과 앱 코드/README/저장값 비교; T04-audit-evidence.json; T04-source-response.json | 미충족 | 정규화 fetched_at 매핑, 실제 화면 및 실패 후 정상 시각 불변 확인. |
| T04-C09 | 실제 조회 화면에 기준 시간대가 표시된다. | 그래프 설명에 Asia/Seoul와 표시 시각 KST가 있음. 요청한 Asia/Seoul (KST, UTC+09:00) 명시와 실제 브라우저 검증 부족. | 정본 조건과 앱 코드/README/저장값 비교; T04-audit-evidence.json; T04-source-response.json | 미충족 | 첫 화면 시간대 전체 표기 후 실제 화면 확인. |
| T04-C10 | 정상 한 건의 원자료·저장값·화면값이 일치한다. | 원자료 8.4606 × 100 = 저장 846.0600 → API 화면값 846.06 대조 확인. 공통 스키마 불일치·공식 fixture 재생·실제 화면 대조는 미완료. | 정본 조건과 앱 코드/README/저장값 비교; T04-audit-evidence.json; T04-source-response.json | 미충족 | 공통 정규화 스키마를 만족하고 실제 화면값 및 공식 정상 입력 대조. |
| T04-C11 | 브라우저 코드·배포 파일·네트워크 응답·Git 기록에 비밀키 원문이 0건이다. | 기존 소스 5개 키 패턴 0건. Git 저장소·공개 배포·제출물이 없어 전체 범위 검사 미완료. | 정본 조건과 앱 코드/README/저장값 비교; T04-audit-evidence.json; T04-source-response.json | 미충족 | 브라우저 코드·배포 산출물·네트워크·Git 기록·제출물 전체 검사. |
| T04-C12 | 느린 외부 응답을 합성 재생하면 별도 실패 상태가 표시된다. | 공식 TIMEOUT은 delay 5000ms/deadline 1500ms. 앱에 공식 재생 경로와 timeout 상태 없음. | 정본 fixture·스키마와 app.py/index.html 비교; T04-audit-evidence.json 기존 테스트 결과 | 미충족 | 같은 공유 처리 함수에 timeout 입력 연결, 별도 설명·다시 시도 표시. |
| T04-C13 | 외부 원천의 401 또는 403 거절을 합성 재생하면 별도 실패 상태가 표시된다. | 공식 AUTH-401 원본 확인. 앱은 외부 401/403을 auth 상태로 분리하지 않음. | 정본 fixture·스키마와 app.py/index.html 비교; T04-audit-evidence.json 기존 테스트 결과 | 미충족 | 외부 401/403 처리와 원천 거절 안내 구현. 제출 앱 로그인은 추가하지 않음. |
| T04-C14 | 외부 원천의 호출 제한을 합성 재생하면 별도 실패 상태가 표시된다. | 공식 RATE-429와 Retry-After=60 확인. 앱에 rate_limit 및 대기 안내 없음. | 정본 fixture·스키마와 app.py/index.html 비교; T04-audit-evidence.json 기존 테스트 결과 | 미충족 | 429 상태 분리 및 Retry-After 초/시각 해석과 대기 후 재시도 구현. |
| T04-C15 | 오프라인 상태를 합성 재생하면 별도 실패 상태가 표시된다. | 공식 OFFLINE 입력 확인. 앱에 offline 상태와 별도 안내 없음. | 정본 fixture·스키마와 app.py/index.html 비교; T04-audit-evidence.json 기존 테스트 결과 | 미충족 | 연결 중단 상태와 네트워크 확인·재시도 안내 구현. |
| T04-C16 | 응답 형식 변경을 합성 재생하면 별도 실패 상태가 표시된다. | 공식 SCHEMA-BREAK의 normalized_value="105" 원본 확인. 앱에 공통 정규화 검증/fixture 경로 없음. 별도 raw rate 문자열 probe는 자동 숫자 변환됨. | 정본 fixture·스키마와 app.py/index.html 비교; T04-audit-evidence.json 기존 테스트 결과 | 미충족 | 숫자 문자열을 자동 변환하지 않는 공통 스키마 검증과 schema_error 재생 구현. |
| T04-C17 | 실패 뒤 마지막 정상값이 지워지지 않는다. | 자체 일반 OSError 실패 후 값 보존 테스트 통과. 공식 다섯 실패를 앱 저장 함수로 재생하지 못함. | 정본 fixture·스키마와 app.py/index.html 비교; T04-audit-evidence.json 기존 테스트 결과 | 미충족 | reset→D1-A→D1-B→각 실패 후 105/1행과 정상시각 보존 확인. |
| T04-C18 | 실패 뒤 마지막 정상값에 오래된 값 표시가 붙는다. | 일반 실패 시 오래된 값일 수 있다는 표시 존재. freshness=stale, error_code와 공식 다섯 실패 화면 없음. | 정본 fixture·스키마와 app.py/index.html 비교; T04-audit-evidence.json 기존 테스트 결과 | 미충족 | 각 실패에서 stale와 오래된 값 · 마지막 정상 조회값을 표시하고 확인. |
| T04-C19 | 실패 상태에 다시 시도 행동이 보이며, 공개 asset T04-RECOVER-D2를 재생하면 상태가 fresh, error_code가 none으로 돌아오고 다음 날짜의 일별 기록이 정확히 한 건 추가된다. | 조회 버튼은 있으나 TIMEOUT→사용자 다시 시도→RECOVER-D2 공식 재생 경로 없음. | 정본 fixture·스키마와 app.py/index.html 비교; T04-audit-evidence.json 기존 테스트 결과 | 미충족 | 복구 입력 후 fresh/none, 120pt, 2행, 다음 날짜 신규1행과 중복 재생 방지 확인. |
| T04-C20 | 기준 시간대의 같은 날짜에 여러 번 성공해도 일별 기록은 한 건이다. | 자체 KST 같은 날 갱신 1행 테스트 통과. 공식 D1-A→D1-B→D1-B 경로, 안정 record ID·최초시각·복합키·동시성 검증 없음. | 정본 fixture·스키마와 app.py/index.html 비교; T04-audit-evidence.json 기존 테스트 결과 | 미충족 | 공식 입력을 실제 저장 함수에 연결하고 3회 성공 및 동시 요청 시험. |
| T04-C21 | 기준 시간대의 다음 날짜에 성공하면 새 일별 기록이 생긴다. | 자체 KST 다음 날짜 추가 2행 테스트 통과. 공식 D2 공통 경로와 record_date 정규화는 미구현. | 정본 fixture·스키마와 app.py/index.html 비교; T04-audit-evidence.json 기존 테스트 결과 | 미충족 | 공식 D1-A→D1-B→D1-B→D2 앱 저장 2행 확인. |
| T04-C22 | 서로 다른 Asia/Seoul 실제 날짜에 조회한 공개 원천 기록이 정확히 2건 보존되어 있다. | 실제 KST 2026-10-08 1건. t04_day 봉인 영수증 0건. 실제 둘째 날 대기. | 정본 조건과 앱 코드/README/저장값 비교; T04-audit-evidence.json; T04-source-response.json | 미충족 | 다른 실제 KST 날짜 정상 조회 및 서로 다른 발급 KST 날짜 영수증 정확히2건 확보. |
| T04-C23 | 두 기록 각각의 공개 원천 URL·원천 관측 시각·정규화 값·단위가 저장된 일별 값과 화면 표시값에서 일치한다. | 실제 2건·봉인 payload·불변 정상 스냅샷 없음. source_time→source_observed_at 플랫폼 매핑 미확인. | 정본 조건과 앱 코드/README/저장값 비교; T04-audit-evidence.json; T04-source-response.json | 미충족 | 발급 계약 확인 후 두 봉인 source_url/source_observed_at/normalized_value/unit과 스냅샷·화면값 대조. |
| T04-C24 | 두 기록을 조회 날짜순으로 놓고 같은 계산 규칙으로 어제 대비 변화값을 다시 계산하면 화면값과 일치한다. | 반올림 전 Decimal 변화 계산 자체 테스트 통과. 실제 두 날짜·영수증이 없어 실제 변화 재계산 불가. 단위 불일치 비교 방지 없음. | 정본 조건과 앱 코드/README/저장값 비교; T04-audit-evidence.json; T04-source-response.json | 미충족 | 두 봉인 server_created_at 순서로 같은 단위 저장값 변화 재계산, 날짜 공백 정직하게 표시. |
| T04-C25 | 공개 심사 화면과 제출 파일에 실제 개인정보 또는 개인 기록이 0건이다. | 현재 앱은 공개 환율만 취급. 공개 심사 화면과 최종 제출 파일이 없어 개인정보 0건 전체 검증 미완료. | 정본 조건과 앱 코드/README/저장값 비교; T04-audit-evidence.json; T04-source-response.json | 미충족 | 실제 공개 배포·전체 소스·제출물 개인정보/개인 기록 검사. |
| T04-C26 | 다섯 실패 재생에는 합성 시험값만 사용한다. | 공식 fixture의 signal_id=aleph-demo-index, 단위 pt와 원래 값 보존. 앱의 다섯 실패 공식 재생 자체가 없음. | 정본 조건과 앱 코드/README/저장값 비교; T04-audit-evidence.json; T04-source-response.json | 미충족 | 분리 합성 저장소와 합성 시험 데이터 · 실제 이틀 증거로 사용 불가 표시 구현. |
| T04-C27 | 짧은 확인 방법에 ① 어디로 가나요, ② 3단계 이내 무엇을 하나요, ③ 무엇이 보이면 통과인가요, ④ 안 될 때 무엇이 보이나요가 구분되어 있다. | 정확히4줄 초안은 아래에 있으나 실제 결과물 URL과 구현된 실패 재생 행동이 없음. | 정본 조건과 앱 코드/README/저장값 비교; T04-audit-evidence.json; T04-source-response.json | 미충족 | 공개 주소와 실제3단계 행동으로 최종4줄 확정. |
| T04-C28 | 제출문에 ① AI에게 맡긴 일, ② 학생이 직접 판단한 일, ③ AI 제안을 따르지 않은 일(없으면 없었던 이유)이 구분되어 있다. | 정확히3줄 초안은 아래에 있으나 학생 직접 판단과 거절 사례를 확인할 수 없음. | 정본 조건과 앱 코드/README/저장값 비교; T04-audit-evidence.json; T04-source-response.json | 미충족 | 학생이 실제 직접 판단·AI 제안을 따르지 않은 일 또는 없었던 이유 작성. |
| T04-C29 | 제출한 모든 URL(결과물·소스)은 인증 없이 새 시크릿 창에서 열린다. | 실제 공개 두 URL 없음; 인증 없는 새 시크릿 창 접근 미실행. | 정본 조건과 앱 코드/README/저장값 비교; T04-audit-evidence.json; T04-source-response.json | 미충족 | 공개 결과물·소스를 인증 없이 실제 접근 확인. |
| T04-C30 | 제출한 모든 URL(결과물·소스)은 초대 없이 새 시크릿 창에서 열린다. | 실제 공개 두 URL 없음; 초대 없는 새 시크릿 창 접근 미실행. | 정본 조건과 앱 코드/README/저장값 비교; T04-audit-evidence.json; T04-source-response.json | 미충족 | 공개 결과물·소스를 초대 없이 실제 접근 확인. |
| T04-C31 | 제출한 모든 URL(결과물·소스)은 비밀번호 입력 없이 새 시크릿 창에서 열린다. | 실제 공개 두 URL 없음; 비밀번호 없는 새 시크릿 창 접근 미실행. | 정본 조건과 앱 코드/README/저장값 비교; T04-audit-evidence.json; T04-source-response.json | 미충족 | 공개 결과물·소스를 비밀번호 없이 실제 접근 확인. |
| T04-C32 | 제출한 모든 URL(결과물·소스)은 OAuth 연결 없이 새 시크릿 창에서 열린다. | 실제 공개 두 URL 없음; OAuth 없는 새 시크릿 창 접근 미실행. | 정본 조건과 앱 코드/README/저장값 비교; T04-audit-evidence.json; T04-source-response.json | 미충족 | 공개 결과물·소스를 OAuth 연결 없이 실제 접근 확인. |
| T04-C33 | 제출한 모든 URL(결과물·소스)은 CAPTCHA 통과 없이 새 시크릿 창에서 열린다. | 실제 공개 두 URL 없음; CAPTCHA 없는 새 시크릿 창 접근 미실행. | 정본 조건과 앱 코드/README/저장값 비교; T04-audit-evidence.json; T04-source-response.json | 미충족 | 공개 결과물·소스를 CAPTCHA 없이 실제 접근 확인. |
| T04-C34 | 결과물 URL 필드에 HTTPS URL 한 개가 제출되어 있다. | 제출 결과물 HTTPS URL 미확보. 로컬 HTTP만 존재. | 정본 조건과 앱 코드/README/저장값 비교; T04-audit-evidence.json; T04-source-response.json | 미충족 | 영속 저장 가능한 공개 HTTPS 결과물을 배포하고 실제 주소1개 기록. |
| T04-C35 | 소스 URL 필드에 HTTPS URL 한 개가 제출되어 있고, URL에는 전체 소스 상태를 다시 받을 수 있는 40자리 또는 64자리 소문자 16진수 commit 식별자가 포함되어 있다. | Git 저장소·실제 commit 식별자·공개 전체 소스 HTTPS URL 없음. | 정본 조건과 앱 코드/README/저장값 비교; T04-audit-evidence.json; T04-source-response.json | 미충족 | 전체 소스를 실제 커밋으로 게시하고 전체40/64자리 소문자 식별자를 포함한 URL1개 기록. |

## 실제 둘째 날과 영수증

현재 실제 KST 날짜는 2026-10-08 하나입니다. 상태: 실제 둘째 날 기록 대기. 다른 실제 KST 날짜에 정상 재조회해야 하며 구현 작업시간과 기다리는 시간을 구분합니다. 과거 날짜를 수동 입력하거나 과거 API/합성 시각으로 실제 둘째 날 조회를 대신하지 않습니다.

정본 계약은 제출정보.json.과정영수증[]에 canonical kind=t04_day 봉인 영수증 정확히2건, 서로 다른 KST server_created_at 날짜, payload의 source_url/source_observed_at/normalized_value/unit 대조를 요구합니다. 현재 영수증은0건입니다. 제공된 정본은 발급 API·서명 절차·source_time→source_observed_at 매핑 정의를 제공하지 않습니다.
과제 플랫폼의 공식 발급 경로와 매핑 계약을 확인한 뒤 정상 데이터의 불변 스냅샷과 봉인 payload를 보존해야 합니다. 임의 영수증·서명·server_created_at을 만들지 않았습니다. 별도 학생 생성 증거 ZIP도 요구하지 않습니다.

## 공개 배포·소스 상태

결과물 HTTPS 주소: 미확보. 전체 commit 고정 소스 HTTPS 주소: 미확보. Git 저장소/실제 commit: 없음.
Git/Python/Node/Docker 실행파일과 Sites/GitHub 관련 도구의 존재는 확인했으나 현재 프로젝트의 배포 대상·원격 저장소·권한·스택 호환성 검사는 미실행입니다. 배포가 불가능하거나 권한이 거절됐다고 단정하지 않습니다.
정본에 맞게 구현·로컬 검증을 완료한 뒤 서버 실행과 영속 저장을 지원하는 환경에 배포하고, 공개 소스를 실제 전체 commit 식별자에 고정해 두 HTTPS 주소를 새 시크릿 창에서 검증해야 합니다.

## 짧은 확인 방법 — 미완료 초안

1. 위치: 실제 결과물 HTTPS 주소 미확보; 로컬 http://127.0.0.1:8000 의 실제 환율·일별 기록·검증 영역.
2. 행동: 실제 조회 → 합성 실패 재생(미구현) → 다시 시도(공식 복구 재생 미구현).
3. 통과 모습: 실제 값·단위·출처·두 시각, 실패 뒤 정상값 보존, 복구 fresh/none·120pt·2행; 현재 전체 통과 미확인.
4. 안 될 때 모습: 오류 설명·오래된 값·다시 시도 또는 실제 둘째 날 기록 대기; 현재 실패별 안내 보완 필요.

## AI와 본인 판단

1. AI에게 맡긴 일: 기존 앱 구현·원천 조사·테스트 및 정본 자산 검증과 조건별 검사표 작성.
2. 학생이 직접 판단한 일: 엔화100 JPY 지표 고정은 사용자 지시로 확인. 그 밖의 직접 판단은 학생 작성 필요.
3. AI 제안을 따르지 않은 일: 실제 이력과 없었던 이유를 확인할 수 없어 학생 작성 필요.

## 실행·증거 파일

앱: python app.py
검사: python -m unittest -v / node test_ui.mjs / python audit_t04.py
고정자산 원본 대조·작업 사본: python import_t04_assets.py

T04-assets-verification.json: 원본 바이트·해시·버전·복사 검증.
T04-audit-evidence.json: 실제 DB·정본 조건·테스트·키 패턴·스키마 차이 증거.
T04-criteria-audit.json: 실제 정본35개 조건의 문구와 항목별 판정.
T04-source-response.json: 실제 공개 원천 응답. 플랫폼 영수증 아님.
