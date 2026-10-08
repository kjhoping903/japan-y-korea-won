# 오늘의 엔화 환율

Python 3.10 이상, 외부 패키지·API 키 없이 실행합니다.

```powershell
python app.py
```

http://127.0.0.1:8000 에서 **환율 조회 및 저장**을 누릅니다. 로컬 서버는 현재 실행 중입니다.
저장 파일: `fx.sqlite3`. 프로그램 재시작 후에도 유지됩니다. 자동 수집은 없습니다.

## 원천 확인

- API 공식 문서: https://frankfurter.dev/
- 선택한 endpoint: https://api.frankfurter.dev/v2/providers/ecb/rate/jpy/krw
- ECB 공식 갱신 설명: https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html
- 2026-10-08 실제 확인 응답:
  `{"date":"2026-10-07","base":"JPY","quote":"KRW","rate":8.4606}`
- ECB 일별 기준환율을 Frankfurter가 전달합니다. 기본 혼합 환율 대신 ECB provider 경로를 사용합니다.
- ECB는 영업일 약 16:00 CET에 발표하며 TARGET 휴무일은 제외됩니다. Frankfurter 반영 시각은 보장하지 않습니다.
- 실시간 환율 또는 은행 현찰 매매율이 아닙니다.

## 데이터와 정밀도

`signal_id=jpy-krw-per-100-jpy`, `unit=KRW/100 JPY`.
JPY 기준이면 rate × 100, KRW 기준이면 100 ÷ rate로 환산합니다. 응답 통화 쌍, 양수 유한 환율, 관측 날짜를 검증합니다.
JSON 수치를 Decimal로 읽고 SQLite JSON의 소수점 문자열에 저장합니다. 곱셈은 원자료 정밀도를 보존하고 무한소수 나눗셈은 유효숫자 60자리로 계산합니다.
화면은 ROUND_HALF_UP으로 소수점 둘째 자리까지 표시합니다. 변화량은 저장값끼리 뺀 뒤 표시합니다. 아주 작은 비영 변화는 0.00원 상승/하락으로 표시될 수 있으며 방향은 반올림 전 값으로 판정합니다.

KST 조회 날짜마다 한 행을 저장하며 같은 날 정상 조회는 갱신합니다. 원천 날짜가 동일해도 정상 응답을 기록합니다.
API는 관측 날짜만 제공하므로 관측 시각은 null로 남깁니다. 조회 완료 시각은 별도로 저장하고 KST로 표시합니다.
오늘 값은 마지막 정상 조회와, 일별 표 및 점 상세는 직전 저장 날짜와 비교합니다.
그래프와 표는 /api/records의 동일한 records 배열을 사용합니다.
일별 점은 시간 간격을 반영하고 누락 날짜의 점을 만들지 않습니다. Y축 확대 범위와 5개 숫자 눈금을 표시합니다.
네트워크·검증 실패는 상태만 기록하며 정상 환율 행을 추가하거나 덮어쓰지 않습니다.
원자료, 환산 공식, 정밀 저장값, 이전 저장값, 화면값은 펼침 영역과 JSON 다운로드에서 확인합니다.

## 검증

```powershell
python -m unittest -v
node test_ui.mjs
```

Python 테스트: KST 자정 경계, 같은 날 갱신, 다음 날 추가, 실패 후 보존, 재시작 영속성, 양방향 환산, 무효 응답, 반올림 전 변화.
JS 테스트: 기록 0/1/2건, 같은 날 점 및 표 갱신, 누락 날짜 미생성, 점 상세, 실패 후 보존, Y축 눈금, 그래프·표 표시값 일치.
시험 데이터는 임시 DB와 격리된 DOM 모형에서만 사용하며 실제 DB에 합성 기록을 넣지 않습니다.
작업 시작 시 app.py는 빈 파일이었고 제공된 fixture 파일은 없었습니다. 기존 fixture의 signal_id·값·pt 단위를 바꾸는 로직을 추가하지 않았습니다.
실제 API 조회·SQLite 저장 및 HTTP 응답 확인 완료. 연결된 브라우저가 없어 실제 브라우저 렌더링·모바일 시각 검증은 미실시입니다.

## T04 통과기준 감사

현재 T04 전체 통과 상태가 아닙니다. 공식 고정자산은 작업 폴더에 배치했고 17개 파일의 바이트·SHA-256이 모두 일치했습니다. 공통 스키마·실패 5종·공개 배포·실제 이틀/영수증은 미완료입니다. 상세 검증표는 [T04-AUDIT.md](T04-AUDIT.md), 재현 가능한 검사 코드는 [audit_t04.py](audit_t04.py)에 있습니다. 기존 Python/DOM 테스트 통과는 공식 fixture와 35개 조건 통과를 의미하지 않습니다.
