import time
import json
import os
import re
import requests
from urllib.parse import unquote
from datetime import datetime

SERVICE_KEY = "xGPyERgH59u72I%2B3hdSXSdLfrOUQjpjtvx3TiLgznNYvD6Cg%2FLHiRC0M4js3w%2FZF7EQG3bjYzn5HmggbT%2F8CDw%3D%3D"

# 로컬 상세위치 참조 파일 (elevatorNo -> dtlLoc)
LOCATION_FILE = "역사별_승강기_통합(번호).json"

WANTED_FIELDS = [
    "address1",
    "address2",
    "buldNm",
    "elevatorNo",
    "dtlLoc",           # 로컬 JSON에서 붙여넣는 상세위치
    "elvtrDivNm",
    "elvtrKindNm",
    "elvtrStts",
    "shuttleSection",
    "shuttleFloorCnt",
    "pauseAblDe",
    "pauseAbleResn",
]

# 엘리베이터 / 에스컬레이터 분류에 사용할 필드 후보
CLASSIFY_FIELDS = ["elvtrDivNm", "elvtrKindNm", "elvtrForm", "elvtrSeNm"]

# 실제 API가 어떤 필드명을 주는지 확인하고 싶을 때 True
SHOW_ALL_KEYS = True

# 매칭 실패한 elevatorNo를 콘솔에 출력할지
SHOW_UNMATCHED = True
# ─────────────────────────────────────────────────────────────


def normalize_no(value) -> str:
    """승강기 일련번호를 숫자 7자리로 정규화.

    '0153-203', '153203', '0153203' 이 모두 '0153203' 이 되도록 맞춘다.
    """
    if value is None:
        return ""
    digits = re.sub(r"\D", "", str(value))
    if not digits:
        return ""
    return digits.zfill(7)


def load_location_map(path: str = LOCATION_FILE) -> dict:
    """로컬 JSON을 읽어 {정규화된 elevatorNo: 상세정보} 형태로 반환."""
    if not os.path.exists(path):
        print(f"[경고] 상세위치 파일을 찾을 수 없습니다: {path}")
        print("       dtlLoc 없이 계속 진행합니다.\n")
        return {}

    try:
        with open(path, encoding="utf-8") as f:
            stations = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[경고] 상세위치 파일을 읽지 못했습니다: {e}\n")
        return {}

    mapping = {}
    duplicates = []

    for station in stations:
        for kind, key in (("엘리베이터", "elevators"), ("에스컬레이터", "escalators")):
            for unit in station.get(key, []):
                no = normalize_no(unit.get("elevatorNo"))
                if not no:
                    continue
                if no in mapping:
                    duplicates.append(no)
                    continue
                mapping[no] = {
                    "dtlLoc": unit.get("dtlLoc"),
                    "kind": kind,
                    "lnCd": unit.get("lnCd"),
                    "stinCd": unit.get("stinCd"),
                    "updnDvNm": unit.get("updnDvNm"),
                    "exitNo": unit.get("exitNo"),
                }

    print(f"[참조] 상세위치 {len(mapping)}건 로드 ({path})")
    if duplicates:
        print(f"[경고] 중복된 elevatorNo {len(duplicates)}건은 첫 번째 값만 사용: {sorted(set(duplicates))}")
    return mapping


def fetch_and_filter_elevators(building_name: str, service_key: str) -> list:
    url = "https://apis.data.go.kr/B553664/ElevatorInformationService/getElevatorListM"

    params = {
        "serviceKey": unquote(service_key),
        "numOfRows": "200",
        "pageNo": "1",
        "_type": "json",
        "sido": "경기",
        "sigungu": "성남",
        "buld_nm": building_name,
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()

        # 공공데이터 API 공통 JSON 응답 구조 파싱
        items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])

        if isinstance(items, dict):
            items = [items]

        # buldPrpos 필드 내 "운수시설" 포함 여부 필터링
        filtered_items = []
        for item in items:
            buld_prpos = item.get("buldPrpos")
            if not buld_prpos:
                continue

            if isinstance(buld_prpos, str) and "운수시설" in buld_prpos:
                filtered_items.append(item)
            elif isinstance(buld_prpos, list) and any("운수시설" in str(p) for p in buld_prpos):
                filtered_items.append(item)

        return filtered_items

    except requests.exceptions.RequestException as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] API 요청 실패: {e}")
        return []
    except json.JSONDecodeError:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] JSON 파싱 실패 (서비스키 또는 API 상태 확인 필요)")
        return []


def attach_locations(items: list, location_map: dict) -> tuple:
    """API 결과에 elevatorNo로 매칭한 dtlLoc을 붙인다.

    원본 item을 직접 수정하며, (매칭수, 미매칭 번호목록)을 반환한다.
    """
    matched = 0
    unmatched = []

    for item in items:
        no = normalize_no(item.get("elevatorNo"))
        info = location_map.get(no)
        if info:
            item["dtlLoc"] = info["dtlLoc"]
            item["_matchedKind"] = info["kind"]
            matched += 1
        else:
            item["dtlLoc"] = "-"
            unmatched.append(item.get("elevatorNo"))

    return matched, unmatched


def pick_fields(item: dict) -> dict:
    """WANTED_FIELDS에 적힌 필드만 골라서 반환 (필드명 그대로 사용)"""
    return {key: item.get(key, "-") for key in WANTED_FIELDS}


def classify(item: dict) -> str:
    """엘리베이터 / 에스컬레이터 / 휠체어리프트 / 기타 로 분류"""
    # 로컬 JSON에서 매칭된 경우 그쪽 분류를 우선 사용
    if item.get("_matchedKind"):
        return item["_matchedKind"]

    text = " ".join(str(item.get(f, "")) for f in CLASSIFY_FIELDS).strip()

    # 분류용 필드가 비어 있으면 전체 값에서 찾아봄
    if not text:
        text = " ".join(str(v) for v in item.values())

    if "에스컬레이터" in text or "무빙워크" in text:
        return "에스컬레이터"
    if "휠체어리프트" in text or "리프트" in text:
        return "휠체어리프트"
    if "엘리베이터" in text or "승강기" in text:
        return "엘리베이터"
    return "기타"


def group_items(data: list) -> dict:
    """분류별로 묶어서 반환"""
    groups = {"엘리베이터": [], "에스컬레이터": [], "휠체어리프트": [], "기타": []}
    for item in data:
        groups[classify(item)].append(item)
    # 비어 있는 분류는 제외
    return {k: v for k, v in groups.items() if v}


def print_items(data: list, building_name: str):
    print(f"\n=== '{building_name}' 승강기 목록 (총 {len(data)}건) ===")

    if not data:
        print("조회된 데이터가 없습니다.\n")
        return

    if SHOW_ALL_KEYS:
        print(f"[참고] API가 주는 전체 필드명: {list(data[0].keys())}")

    groups = group_items(data)

    for kind, items in groups.items():
        print(f"\n■ {kind} ({len(items)}건)")
        print("=" * 40)
        for idx, item in enumerate(items, start=1):
            print(f"[{idx}]")
            for key, value in pick_fields(item).items():
                print(f"  {key}: {value}")
            print("-" * 40)
    print()


def save_to_json(data: list, building_name: str, match_info: dict, filename: str = None):
    if filename is None:
        filename = f"{building_name} 승강기 현황.json"

    groups = group_items(data)

    payload = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_count": len(data),
        "count_by_type": {kind: len(items) for kind, items in groups.items()},
        "dtlLoc_matched": match_info.get("matched", 0),
        "dtlLoc_unmatched": match_info.get("unmatched", []),
        "items": {
            kind: [pick_fields(item) for item in items]
            for kind, items in groups.items()
        },
    }

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=4)

    summary = ", ".join(f"{k} {v}건" for k, v in payload["count_by_type"].items()) or "0건"
    print(f"[{payload['updated_at']}] 데이터 업데이트 완료 ({summary} -> {filename})")
    print(f"    상세위치 매칭: {payload['dtlLoc_matched']}/{len(data)}건")

    if SHOW_UNMATCHED and payload["dtlLoc_unmatched"]:
        print(f"    미매칭 elevatorNo: {payload['dtlLoc_unmatched']}")


def main():
    location_map = load_location_map()

    buld_nm = input("조회할 지하철 역을 입력하세요 (buld_nm): ").strip()

    if not buld_nm:
        print("건물명이 입력되지 않았습니다. 프로그램을 종료합니다.")
        return

    print(f"\n'{buld_nm}' 건물 정보 수집 시작 (1시간 간격 업데이트 / 종료: Ctrl+C)\n")

    while True:
        filtered_data = fetch_and_filter_elevators(buld_nm, SERVICE_KEY)

        matched, unmatched = attach_locations(filtered_data, location_map)

        save_to_json(
            filtered_data,
            building_name=buld_nm,
            match_info={"matched": matched, "unmatched": unmatched},
        )
        print_items(filtered_data, building_name=buld_nm)

        # 3,600초 (1시간) 대기
        time.sleep(3600)


if __name__ == "__main__":
    main()