# Discord 포인트 봇

서버별 포인트 잔액을 SQLite 또는 Supabase PostgreSQL에 저장하는 슬래시 명령어 봇입니다. 모든 명령 응답은 Discord Components V2의 카드 레이아웃으로 표시합니다. 자동 응답 기능을 사용하므로 Discord Developer Portal에서 Message Content Intent를 켜야 합니다.

Components V2 메시지는 Discord의 기존 임베드와 함께 사용할 수 없습니다. 그래서 임베드처럼 보이도록 색상 테두리가 있는 `Container`와 `TextDisplay`를 사용합니다.

## 코드 구조

- `bot.py`: 봇 시작, Cog 로드, 슬래시 명령어 동기화 및 공통 오류 처리
- `settings.py`: 보상, 시간대, 데이터베이스 등 실행 설정
- `credentials.py`: `.env`에서 Discord 봇 토큰 읽기
- `permissions.py`: 관리자 전용 명령어 권한 검사
- `economy.py`: SQLite/Supabase 잔액 저장과 포인트 트랜잭션
- `presentation.py`: 공통 Components V2 카드와 서버 컨텍스트 처리
- `cogs/`: 명령어별 모듈 (`가방`, `일일`, `송금`, `공동계좌`, `공동입금`, `공동출금`, `지급`, `차감`, `잔액설정`, `상점`, `구매`, `판매`, `상품등록`, `상품수정`, `상품삭제`, `자동응답`)

## 기능

- `/가방`: 내 잔액과 보유 상품 확인
- `/일일`: 설정된 시간대 기준 하루 한 번 보상 수령
- 보이스 채널 리워드: 일반 계정(봇 제외)은 마이크가 켜져 있으면 시간당 100포인트, 본인 또는 서버가 음소거한 상태면 시간당 50포인트를 받습니다. Discord의 음소거 상태로 노마이크를 판별하며, 실제 마이크 장치 연결 여부는 감지하지 않습니다.
- `/송금`: 다른 멤버에게 포인트 송금
- `/공동계좌`: 서버 공동 계좌 잔액 확인
- `/공동입금`, `/공동출금`: 개인 잔액과 서버 공동 계좌 사이에 포인트 이동
- 공동 계좌는 서버마다 하나씩 생성됩니다. 모든 서버 멤버가 입금할 수 있고, 공동 자금 보호를 위해 출금은 서버 관리자만 할 수 있습니다.
- `/지급`, `/차감`, `/잔액설정`: 관리자 지급, 차감, 잔액 설정
- `/상점`: 서버 상점 상품과 가격, 재고 확인
- `/구매`: 포인트로 상품 구매
- `/판매`: 구매한 상품을 원가의 80%에 판매
- `/상품등록`, `/상품수정`, `/상품삭제`: 관리자 상품 관리
- `/자동응답 추가`, `/자동응답 임베드추가`, `/자동응답 목록`, `/자동응답 수정`, `/자동응답 임베드수정`, `/자동응답 방식`, `/자동응답 삭제`: 서버별 키워드 자동 응답 관리. 기본은 대소문자를 무시하는 완전 일치이며, 앞부분·뒷부분·문장 포함 방식도 선택할 수 있습니다. 일반 문구 또는 제목·설명·색상을 지정한 임베드로 답할 수 있습니다. `/임베드수정`은 기존 트리거를 임베드로 바꾸며, `/수정`은 텍스트 응답으로 바꿉니다. 응답에는 `{user}`, `{user_name}`, `{user_id}`, `{server}`, `{channel}`, `{channel_name}`, `{message_content}`, `{message_link}`, `{newline}` 치환자를 사용할 수 있습니다. 멘션은 표시되지만 알림은 보내지 않습니다. 서버마다 최대 100개까지 등록할 수 있습니다.

예를 들어 트리거 `안녕`, 응답 `반가워요, {user}!`를 추가하면 누군가 `안녕`이라고 보낼 때 봇이 같은 채널에 답합니다. 자동 응답 관리는 서버 관리자만 사용할 수 있습니다.

상품은 관리자 명령어로 등록하고 수정할 수 있으며, 재고를 지정하거나 무제한으로 설정할 수 있습니다. `/상품등록` 또는 `/상품수정`에서 역할을 연결하면 구매 시 해당 역할을 자동으로 지급하고, 연결된 상품을 판매하면 역할 회수를 시도합니다. 역할 변경은 이후 구매부터 적용되고, 이미 받은 역할은 그대로 유지됩니다. 구매한 상품과 재고는 서버별로 데이터베이스에 저장됩니다. 구매 상품은 현재 인벤토리형 아이템으로 관리됩니다.

각 서버의 잔액은 독립적으로 관리됩니다. 송금, 일일 보상, 상품 구매와 판매는 SQLite 또는 PostgreSQL 트랜잭션으로 처리합니다. 마을 공동 계좌도 서버별로 하나씩 생성되며, 공동 입금·출금은 개인 잔액과 공동 잔액을 한 트랜잭션으로 변경합니다.

## Supabase 사용

기존 SQLite 데이터를 Supabase 프로젝트로 처음 옮길 때 다음 순서로 진행합니다.

1. requirements.txt 의존성을 설치합니다.
2. Supabase 대시보드의 Connect에서 Direct 또는 Session pooler 연결 문자열을 복사해 .env의 SUPABASE_ADMIN_DATABASE_URL에 설정합니다. 관리자 연결 문자열은 이 1회 이전에만 사용하며, Transaction pooler는 사용할 수 없습니다.
3. python migrate_to_supabase.py를 실행합니다.
4. 이전이 끝나면 스크립트가 잔액, 상점, 인벤토리 데이터를 확인하고 앱 전용 DB 계정의 DATABASE_URL을 .env에 저장합니다. 관리자 연결 문자열은 .env에서 제거됩니다.
5. `supabase/migrations/20260927120000_create_voice_activity.sql`을 SQL Editor에서 실행합니다. `GUILD_IDS` 서버별 테이블을 쓰는 경우에는 먼저 서버별 테이블 분리 마이그레이션을 적용하세요.
6. `supabase/migrations/20261003120000_create_autoresponders.sql`을 SQL Editor에서 실행합니다.
7. `supabase/migrations/20261003130000_add_autoresponder_embeds.sql`을 SQL Editor에서 실행합니다.
8. `python bot.py`를 실행합니다. `DATABASE_URL`이 설정되어 있으면 Supabase를 사용하고, 비어 있으면 SQLite를 사용합니다.

이전 스크립트는 대상 테이블이 이미 있으면 기존 데이터를 덮어쓰지 않고 중단합니다. Supabase 테이블에는 RLS를 켜고 anon/authenticated/service_role 접근을 차단하며, 봇 전용 DB 역할만 접근하도록 설정합니다. 배포 환경에서는 .env 대신 해당 호스팅 서비스의 비밀 환경변수에 DATABASE_URL을 설정하세요.

기존 Supabase 프로젝트에서 공동 계좌를 사용하려면 `supabase/migrations/20260926072621_create_shared_accounts.sql` 내용을 SQL Editor에서 한 번 실행해야 합니다. 이 SQL은 공개 API 역할을 차단하고 봇 전용 DB 역할에 필요한 접근만 허용합니다.

보이스 채널 보상을 Supabase에서 사용하려면 `supabase/migrations/20260927120000_create_voice_activity.sql`도 SQL Editor에서 실행해야 합니다. 이 SQL은 남은 보이스 시간을 보관하는 테이블을 만들고 봇 전용 DB 역할만 접근하도록 설정합니다.

### Discord 서버별 테이블 분리

`GUILD_IDS`에 설정한 서버마다 잔액, 상점, 인벤토리, 공동 계좌 테이블을 따로 사용합니다. 현재 설정 대상은 `1352691962817548360`과 `1358747276754817074`입니다.

1. `supabase/migrations/20260926101702_split_economy_tables_by_guild.sql` 전체 내용을 Supabase 대시보드의 SQL Editor에서 실행합니다.
2. 봇을 실행하는 `.env` 또는 호스팅 서비스 환경변수에 `GUILD_IDS=1352691962817548360,1358747276754817074`를 설정합니다.
3. `supabase/migrations/20260927120000_create_voice_activity.sql`도 SQL Editor에서 실행합니다. 기존 서버별 테이블에 보이스 시간 저장용 테이블을 추가합니다.
4. 봇을 재시작합니다. 시작 시 필요한 서버별 테이블을 확인하고, 각 Discord 서버에서는 해당 ID가 붙은 테이블만 사용합니다.

예를 들어 `accounts_1352691962817548360`과 `accounts_1358747276754817074`는 서로 분리됩니다. 다른 Discord 서버를 추가할 때는 해당 ID의 경제 테이블을 만들고 보이스 활동 마이그레이션도 적용한 다음 `GUILD_IDS`에 ID를 추가해야 합니다. 서버별 테이블을 설정하지 않은 기존 설치는 기존 테이블 이름을 계속 사용합니다.

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

Discord Developer Portal에서 봇을 만든 뒤 초대할 때 `bot`과 `applications.commands` 스코프를 선택하세요. Bot 설정의 Privileged Gateway Intents에서 **Message Content Intent**를 켜야 자동 응답이 동작합니다. 봇에는 명령 응답과 자동 응답을 위한 메시지 전송 및 임베드 링크 권한이 필요합니다. 관리자 명령은 서버 관리자 권한을 요구합니다.

## 설정값

| 환경 변수 | 기본값 | 설명 |
| --- | --- | --- |
| `DISCORD_TOKEN` | 없음 | Discord 봇 토큰 |
| `SYNC_GUILD_ID` | 전역 동기화 | 개발용 서버 ID |
| `GUILD_IDS` | 비어 있음 | 서버별 테이블을 사용할 Discord 서버 ID 목록(쉼표 구분) |
| `DAILY_REWARD` | `100` | 일일 보상 포인트 |
| `VOICE_REWARD` | `100` | 보이스 채널 연결 1시간당 포인트 |
| `VOICE_NO_MIC_REWARD` | `50` | 음소거 상태로 보이스 채널에 연결된 1시간당 포인트 |
| `TIMEZONE` | `Asia/Seoul` | 일일 보상 기준 시간대 |
| `DATABASE_PATH` | `data/economy.sqlite3` | SQLite 파일 경로 |
| `DATABASE_URL` | 비어 있음 | 설정하면 사용하는 Supabase PostgreSQL 연결 문자열 |
| `SUPABASE_ADMIN_DATABASE_URL` | 비어 있음 | 최초 데이터 이전에만 사용하는 관리자 연결 문자열 |
