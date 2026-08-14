# 성남시 교통약자 길안내 - Backend v2

## 역할
FastAPI가 Flutter 앱과 외부 지도/교통 API 사이의 오케스트레이터 역할을 합니다.

- 주소/장소명 → 좌표: Kakao Local API
- 후보 대중교통 경로: Kakao Public Traffic API
- 역 내부 접근성: 기존 station graph + 시설 데이터
- 실시간 시설 상태: 기존 facility status 서비스
- 사용자 조건: 다중 선택 조건 + 단일 경로 선호도
- 현장 제보: 이미지 저장 → AI 검증(PENDING/APPROVED/REJECTED)
- MySQL: 사용자/조건/시설/실시간 상태/제보 등의 영속 데이터

## 권장 실행 순서

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

`.env`에 실제 API 키와 MySQL 접속 정보를 입력합니다.

DB 생성 후:

```powershell
python -m app.scripts.init_db
python -m app.scripts.seed_conditions
```

서버 실행:

```powershell
uvicorn app.main:app --reload
```

Swagger:

`http://127.0.0.1:8000/docs`

## v2 API

- `GET /health`
- `GET /api/v2/conditions`
- `POST /api/v2/users/register`
- `GET /api/v2/users/{user_id}/profile`
- `PUT /api/v2/users/{user_id}/profile`
- `GET /api/v2/geocode`
- `GET /api/v2/geocode/address`
- `GET /api/v2/geocode/keyword`
- `POST /api/v2/routes/search`
- `POST /api/v2/reports`

### 경로 검색 예시

```json
{
  "origin": "판교역",
  "destination": "성남종합버스터미널",
  "mobility_conditions": [
    "AVOID_STAIRS",
    "PREFER_ELEVATOR",
    "AVOID_STEEP_INCLINE"
  ],
  "preference": "BALANCED"
}
```

## 중요

`backend/.env`는 Git에 올리지 않습니다. 기존 압축본에 들어 있던 API 키는 노출된 것으로 간주하고 실제 키를 교체한 뒤 새 `.env`를 작성하는 것을 권장합니다.

현재 역 내부 경로 엔진은 1차 프로토타입의 `WHEELCHAIR/STROLLER/ELDERLY` 프로필을 내부적으로 사용합니다. 외부 API 계약은 2차 PRD에 맞춘 `mobility_conditions` 방식으로 바꾸었고, `condition_service.py`가 기존 엔진과 연결하는 호환 계층입니다. 다음 단계에서 `station_path_service.py` 자체를 condition-set 기반으로 바꾸면 이 호환 계층을 제거할 수 있습니다.
