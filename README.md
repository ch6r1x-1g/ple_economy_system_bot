# Discord 포인트 봇

서버별 포인트 잔액을 SQLite 또는 Supabase PostgreSQL에 저장하는 슬래시 명령어 봇입니다. 모든 응답은 Discord Components V2의 카드 레이아웃으로 표시합니다. 메시지 내용을 읽지 않으므로 Message Content Intent가 필요하지 않습니다.

Components V2 메시지는 Discord의 기존 임베드와 함께 사용할 수 없습니다. 그래서 임베드처럼 보이도록 색상 테두리가 있는 `Container`와 `TextDisplay`를 사용합니다.

## 코드 구조

- `bot.py`: 봇 시작, Cog 로드, 슬래시 명령어 동기화 및 공통 오류 처리
- `settings.py`: 환경 변수와 실행 설정
- `economy.py`: SQLite/Supabase 잔액 저장과 포인트 트랜잭션
- `presentation.py`: 공통 Components V2 카드와 서버 컨텍스트 처리
- `cogs/`: 명령어별 모듈 (`잔액`, `일일`, `송금`, `공동계좌`, `공동입금`, `공동출금`, `지급`, `차감`, `잔액설정`, `상점`, `구매`, `판매`, `인벤토리`, `상품등록`, `상품수정`, `상품삭제`)

## 기능

- `/잔액`: 내 잔액 확인
- `/일일`: 설정된 시간대 기준 하루 한 번 보상 수령
- `/송금`: 다른 멤버에게 포인트 송금
- `/공동계좌`: 서버 공동 계좌 잔액 확인
- `/공동입금`, `/공동출금`: 개인 잔액과 서버 공동 계좌 사이에 포인트 이동
- 공동 계좌는 서버마다 하나씩 생성되며, 모든 서버 멤버가 입금하거나 출금할 수 있습니다.
- `/지급`, `/차감`, `/잔액설정`: 관리자 지급, 차감, 잔액 설정
- `/상점`: 서버 상점 상품과 가격, 재고 확인
- `/구매`: 포인트로 상품 구매
- `/판매`: 구매한 상품을 원가의 80%에 판매
- `/인벤토리`: 구매한 상품 확인
- `/상품등록`, `/상품수정`, `/상품삭제`: 관리자 상품 관리

상품은 관리자 명령어로 등록하고 수정할 수 있으며, 재고를 지정하거나 무제한으로 설정할 수 있습니다. `/상품등록` 또는 `/상품수정`에서 역할을 연결하면 구매 시 해당 역할을 자동으로 지급합니다. 역할 변경은 이후 구매부터 적용되고, 이미 받은 역할은 그대로 유지됩니다. 구매한 상품과 재고는 서버별로 데이터베이스에 저장됩니다. 구매 상품은 현재 인벤토리형 아이템으로 관리됩니다.

각 서버의 잔액은 독립적으로 관리됩니다. 송금, 일일 보상, 상품 구매와 판매는 SQLite 또는 PostgreSQL 트랜잭션으로 처리합니다. 마을 공동 계좌도 서버별로 하나씩 생성되며, 공동 입금·출금은 개인 잔액과 공동 잔액을 한 트랜잭션으로 변경합니다.

## Supabase 사용

기존 SQLite 데이터를 Supabase 프로젝트로 처음 옮길 때 다음 순서로 진행합니다.

1. requirements.txt 의존성을 설치합니다.
2. Supabase 대시보드의 Connect에서 Direct 또는 Session pooler 연결 문자열을 복사해 .env의 SUPABASE_ADMIN_DATABASE_URL에 설정합니다. 관리자 연결 문자열은 이 1회 이전에만 사용하며, Transaction pooler는 사용할 수 없습니다.
3. python migrate_to_supabase.py를 실행합니다.
4. 이전이 끝나면 스크립트가 잔액, 상점, 인벤토리 데이터를 확인하고 앱 전용 DB 계정의 DATABASE_URL을 .env에 저장합니다. 관리자 연결 문자열은 .env에서 제거됩니다.
5. python bot.py를 실행합니다. DATABASE_URL이 설정되어 있으면 Supabase를 사용하고, 비어 있으면 SQLite를 사용합니다.

이전 스크립트는 대상 테이블이 이미 있으면 기존 데이터를 덮어쓰지 않고 중단합니다. Supabase 테이블에는 RLS를 켜고 anon/authenticated/service_role 접근을 차단하며, 봇 전용 DB 역할만 접근하도록 설정합니다. 배포 환경에서는 .env 대신 해당 호스팅 서비스의 비밀 환경변수에 DATABASE_URL을 설정하세요.

기존 Supabase 프로젝트에서 공동 계좌를 사용하려면 `supabase/migrations/20260926072621_create_shared_accounts.sql` 내용을 SQL Editor에서 한 번 실행해야 합니다. 이 SQL은 공개 API 역할을 차단하고 봇 전용 DB 역할에 필요한 접근만 허용합니다.

## 실행

Python 3.10 이상이 필요합니다.

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

`.env`에서 `DISCORD_TOKEN`을 설정합니다. 개발 시에는 `SYNC_GUILD_ID`에 테스트 서버 ID를 입력하면 명령어가 해당 서버에 즉시 동기화됩니다. 비워 두면 전역 명령어로 동기화되며, Discord에 표시되기까지 시간이 걸릴 수 있습니다.

```sh
python bot.py
```

Discord Developer Portal에서 봇을 만든 뒤 초대할 때 `bot`과 `applications.commands` 스코프를 선택하세요. 봇에는 명령 응답을 위한 메시지 전송 및 임베드 링크 권한이 필요합니다. 관리자 명령은 서버 관리자 권한을 요구합니다.

## 설정값

| 환경 변수 | 기본값 | 설명 |
| --- | --- | --- |
| `DISCORD_TOKEN` | 없음 | Discord 봇 토큰 |
| `SYNC_GUILD_ID` | 전역 동기화 | 개발용 서버 ID |
| `DAILY_REWARD` | `100` | 일일 보상 포인트 |
| `TIMEZONE` | `Asia/Seoul` | 일일 보상 기준 시간대 |
| `DATABASE_PATH` | `data/economy.sqlite3` | SQLite 파일 경로 |
| `DATABASE_URL` | 비어 있음 | 설정하면 사용하는 Supabase PostgreSQL 연결 문자열 |
| `SUPABASE_ADMIN_DATABASE_URL` | 비어 있음 | 최초 데이터 이전에만 사용하는 관리자 연결 문자열 |
