import time
import json
import os
import re
import requests

from pathlib import Path
from urllib.parse import unquote
from datetime import datetime


# ============================================================
# 설정
# ============================================================

SERVICE_KEY = (
    "xGPyERgH59u72I%2B3hdSXSdLfrOUQjpjtvx3TiLgznNYvD6Cg%2FLHiRC0M4js3w%2FZF7EQG3bjYzn5HmggbT%2F8CDw%3D%3D"
)

# 현재 Python 파일이 실제로 존재하는 폴더
BASE_DIR = Path(__file__).resolve().parent

# 1순위:
# Python 파일과 같은 폴더에서 찾음
LOCATION_FILE = BASE_DIR / "역사별_승강기_통합(번호).json"


WANTED_FIELDS = [
    "address1",
    "address2",
    "buldNm",
    "elevatorNo",
    "dtlLoc",
    "elvtrDivNm",
    "elvtrKindNm",
    "elvtrStts",
    "shuttleSection",
    "shuttleFloorCnt",
    "pauseAblDe",
    "pauseAbleResn",
]


CLASSIFY_FIELDS = [
    "elvtrDivNm",
    "elvtrKindNm",
    "elvtrForm",
    "elvtrSeNm",
]


# API 전체 필드 확인
SHOW_ALL_KEYS = True

# 매칭 실패 elevatorNo 출력
SHOW_UNMATCHED = True


# ============================================================
# elevatorNo 정규화
# ============================================================

def normalize_no(value) -> str:
    """
    승강기 일련번호를 숫자 7자리 문자열로 정규화합니다.

    예:
    0153-203
    153203
    0153203

    모두
    0153203
    으로 변환됩니다.
    """

    if value is None:
        return ""

    digits = re.sub(
        r"\D",
        "",
        str(value),
    )

    if not digits:
        return ""

    return digits.zfill(7)


# ============================================================
# 위치 JSON 자동 탐색
# ============================================================

def find_location_file() -> Path | None:
    """
    역사별_승강기_통합(번호).json을 자동으로 찾습니다.

    탐색 순서:

    1. 현재 Python 파일과 같은 폴더
    2. 현재 Python 파일 기준 app/data
    3. 현재 Python 파일 기준 data
    4. 현재 작업 폴더
    5. 현재 작업 폴더의 app/data
    """

    filename = "역사별_승강기_통합(번호).json"

    candidates = [
        # Python 파일과 같은 폴더
        BASE_DIR / filename,

        # Python 파일 폴더 아래 app/data
        BASE_DIR / "app" / "data" / filename,

        # Python 파일 폴더 아래 data
        BASE_DIR / "data" / filename,

        # 현재 터미널 위치
        Path.cwd() / filename,

        # backend에서 실행하는 경우
        Path.cwd() / "app" / "data" / filename,
    ]

    # 부모 폴더도 몇 단계 확인
    current = BASE_DIR

    for _ in range(4):
        candidates.append(
            current / "app" / "data" / filename
        )

        candidates.append(
            current / "data" / filename
        )

        candidates.append(
            current / filename
        )

        current = current.parent

    checked = set()

    for path in candidates:

        resolved = path.resolve()

        if resolved in checked:
            continue

        checked.add(resolved)

        if resolved.exists():

            print(
                "[참조] 상세위치 파일 발견:"
            )

            print(
                f"       {resolved}"
            )

            return resolved

    print(
        "[경고] 역사별_승강기_통합(번호).json을 "
        "찾지 못했습니다."
    )

    print(
        "[확인한 위치]"
    )

    for path in checked:
        print(
            f" - {path}"
        )

    return None


# ============================================================
# 위치 데이터 로드
# ============================================================

def load_location_map(
    path: Path | None = None,
) -> dict:

    """
    로컬 JSON을 읽어서

    {
        elevatorNo: {
            dtlLoc,
            kind,
            lnCd,
            stinCd,
            ...
        }
    }

    구조로 반환합니다.
    """

    if path is None:
        path = find_location_file()

    if path is None:

        print(
            "[경고] 상세위치 데이터 없이 계속 진행합니다.\n"
        )

        return {}

    try:

        with open(
            path,
            "r",
            encoding="utf-8",
        ) as f:

            stations = json.load(f)

    except (
        OSError,
        json.JSONDecodeError,
    ) as e:

        print(
            f"[경고] 상세위치 파일을 읽지 못했습니다: {e}\n"
        )

        return {}

    if not isinstance(
        stations,
        list,
    ):

        print(
            "[경고] 상세위치 JSON의 최상위 구조가 "
            "list가 아닙니다."
        )

        return {}

    mapping = {}

    duplicates = []

    elevator_count = 0
    escalator_count = 0

    for station in stations:

        if not isinstance(
            station,
            dict,
        ):
            continue

        for kind, key in (
            (
                "엘리베이터",
                "elevators",
            ),
            (
                "에스컬레이터",
                "escalators",
            ),
        ):

            units = station.get(
                key,
                [],
            )

            if not isinstance(
                units,
                list,
            ):
                continue

            for unit in units:

                if not isinstance(
                    unit,
                    dict,
                ):
                    continue

                no = normalize_no(
                    unit.get(
                        "elevatorNo"
                    )
                )

                if not no:
                    continue

                if no in mapping:

                    duplicates.append(
                        no
                    )

                    continue

                mapping[no] = {
                    "dtlLoc": unit.get(
                        "dtlLoc"
                    ),

                    "kind": kind,

                    "lnCd": unit.get(
                        "lnCd"
                    ),

                    "stinCd": unit.get(
                        "stinCd"
                    ),

                    "updnDvNm": unit.get(
                        "updnDvNm"
                    ),

                    "exitNo": unit.get(
                        "exitNo"
                    ),

                    "grndDvNmFr": unit.get(
                        "grndDvNmFr"
                    ),

                    "runStinFlorFr": unit.get(
                        "runStinFlorFr"
                    ),

                    "grndDvNmTo": unit.get(
                        "grndDvNmTo"
                    ),

                    "runStinFlorTo": unit.get(
                        "runStinFlorTo"
                    ),
                }

                if kind == "엘리베이터":
                    elevator_count += 1

                elif kind == "에스컬레이터":
                    escalator_count += 1

    print()
    print(
        "=" * 60
    )

    print(
        "[상세위치 데이터 로드 완료]"
    )

    print(
        f"파일: {path}"
    )

    print(
        f"전체 장비번호: {len(mapping)}건"
    )

    print(
        f"엘리베이터: {elevator_count}건"
    )

    print(
        f"에스컬레이터: {escalator_count}건"
    )

    print(
        "=" * 60
    )

    if duplicates:

        unique_duplicates = sorted(
            set(
                duplicates
            )
        )

        print(
            f"[경고] 중복 elevatorNo: "
            f"{len(unique_duplicates)}건"
        )

        print(
            unique_duplicates
        )

    return mapping


# ============================================================
# 공공데이터 API
# ============================================================

def fetch_and_filter_elevators(
    building_name: str,
    service_key: str,
) -> list:

    url = (
        "https://apis.data.go.kr/"
        "B553664/"
        "ElevatorInformationService/"
        "getElevatorListM"
    )

    params = {
        "serviceKey": unquote(
            service_key
        ),

        "numOfRows": "200",

        "pageNo": "1",

        "_type": "json",

        "sido": "경기",

        "sigungu": "성남",

        "buld_nm": building_name,
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=10,
        )

        response.raise_for_status()

        data = response.json()

        items = (
            data
            .get(
                "response",
                {},
            )
            .get(
                "body",
                {},
            )
            .get(
                "items",
                {},
            )
            .get(
                "item",
                [],
            )
        )

        if isinstance(
            items,
            dict,
        ):

            items = [
                items
            ]

        if not isinstance(
            items,
            list,
        ):

            return []

        filtered_items = []

        for item in items:

            if not isinstance(
                item,
                dict,
            ):
                continue

            buld_prpos = item.get(
                "buldPrpos"
            )

            if not buld_prpos:
                continue

            if isinstance(
                buld_prpos,
                str,
            ):

                if (
                    "운수시설"
                    in buld_prpos
                ):

                    filtered_items.append(
                        item
                    )

            elif isinstance(
                buld_prpos,
                list,
            ):

                if any(
                    "운수시설"
                    in str(p)
                    for p
                    in buld_prpos
                ):

                    filtered_items.append(
                        item
                    )

        return filtered_items

    except (
        requests
        .exceptions
        .RequestException
    ) as e:

        print(
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
            f"API 요청 실패: {e}"
        )

        return []

    except json.JSONDecodeError:

        print(
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
            "JSON 파싱 실패 "
            "(서비스키 또는 API 상태 확인 필요)"
        )

        return []


# ============================================================
# 상세 위치 1:1 매칭
# ============================================================

def attach_locations(
    items: list,
    location_map: dict,
) -> tuple:

    """
    API 결과의 elevatorNo와
    위치 데이터의 elevatorNo를 1:1 비교합니다.

    성공하면 다음 정보를 API item에 추가합니다.

    dtlLoc
    lnCd
    stinCd
    updnDvNm
    exitNo
    """

    matched = 0

    unmatched = []

    print()
    print(
        "=" * 60
    )

    print(
        "[elevatorNo 1:1 매칭 시작]"
    )

    for item in items:

        raw_no = item.get(
            "elevatorNo"
        )

        no = normalize_no(
            raw_no
        )

        info = location_map.get(
            no
        )

        if info:

            item[
                "dtlLoc"
            ] = info.get(
                "dtlLoc"
            )

            item[
                "_matchedKind"
            ] = info.get(
                "kind"
            )

            item[
                "_locationLnCd"
            ] = info.get(
                "lnCd"
            )

            item[
                "_locationStinCd"
            ] = info.get(
                "stinCd"
            )

            item[
                "_locationUpdnDvNm"
            ] = info.get(
                "updnDvNm"
            )

            item[
                "_locationExitNo"
            ] = info.get(
                "exitNo"
            )

            matched += 1

            print(
                f"[MATCH] "
                f"{raw_no} → "
                f"{info.get('dtlLoc')}"
            )

        else:

            item[
                "dtlLoc"
            ] = "-"

            unmatched.append(
                raw_no
            )

            print(
                f"[NO MATCH] {raw_no}"
            )

    print(
        "=" * 60
    )

    print(
        f"매칭 성공: {matched}/{len(items)}"
    )

    print(
        f"매칭 실패: {len(unmatched)}/{len(items)}"
    )

    print(
        "=" * 60
    )

    return (
        matched,
        unmatched,
    )


# ============================================================
# 저장할 필드
# ============================================================

def pick_fields(
    item: dict,
) -> dict:

    result = {
        key: item.get(
            key,
            "-"
        )
        for key
        in WANTED_FIELDS
    }

    # 위치 JSON에서 가져온 추가 식별정보
    result[
        "locationLnCd"
    ] = item.get(
        "_locationLnCd",
        "-",
    )

    result[
        "locationStinCd"
    ] = item.get(
        "_locationStinCd",
        "-",
    )

    result[
        "locationUpdnDvNm"
    ] = item.get(
        "_locationUpdnDvNm",
        "-",
    )

    result[
        "locationExitNo"
    ] = item.get(
        "_locationExitNo",
        "-",
    )

    return result


# ============================================================
# 시설 종류 분류
# ============================================================

def classify(
    item: dict,
) -> str:

    # 1:1 위치 매칭에 성공한 경우
    # 위치 데이터의 분류를 우선 사용

    if item.get(
        "_matchedKind"
    ):

        return item[
            "_matchedKind"
        ]

    text = " ".join(
        str(
            item.get(
                field,
                "",
            )
        )
        for field
        in CLASSIFY_FIELDS
    ).strip()

    if not text:

        text = " ".join(
            str(value)
            for value
            in item.values()
        )

    if (
        "에스컬레이터"
        in text
        or
        "무빙워크"
        in text
    ):

        return "에스컬레이터"

    if (
        "휠체어리프트"
        in text
        or
        "리프트"
        in text
    ):

        return "휠체어리프트"

    if (
        "엘리베이터"
        in text
        or
        "승강기"
        in text
    ):

        return "엘리베이터"

    return "기타"


# ============================================================
# 시설별 그룹
# ============================================================

def group_items(
    data: list,
) -> dict:

    groups = {
        "엘리베이터": [],
        "에스컬레이터": [],
        "휠체어리프트": [],
        "기타": [],
    }

    for item in data:

        groups[
            classify(
                item
            )
        ].append(
            item
        )

    return {
        key: value
        for key, value
        in groups.items()
        if value
    }


# ============================================================
# 콘솔 출력
# ============================================================

def print_items(
    data: list,
    building_name: str,
):

    print(
        f"\n=== '{building_name}' "
        f"승강기 목록 "
        f"(총 {len(data)}건) ==="
    )

    if not data:

        print(
            "조회된 데이터가 없습니다.\n"
        )

        return

    if SHOW_ALL_KEYS:

        print(
            "[참고] API가 주는 전체 필드명:"
        )

        print(
            list(
                data[0].keys()
            )
        )

    groups = group_items(
        data
    )

    for kind, items in (
        groups.items()
    ):

        print(
            f"\n■ {kind} "
            f"({len(items)}건)"
        )

        print(
            "=" * 40
        )

        for idx, item in enumerate(
            items,
            start=1,
        ):

            print(
                f"[{idx}]"
            )

            for key, value in (
                pick_fields(
                    item
                ).items()
            ):

                print(
                    f"  {key}: {value}"
                )

            print(
                "-" * 40
            )

    print()


# ============================================================
# JSON 저장
# ============================================================

def save_to_json(
    data: list,
    building_name: str,
    match_info: dict,
    filename: str = None,
):

    if filename is None:

        filename = (
            f"{building_name} "
            f"승강기 현황.json"
        )

    # 결과 파일 역시
    # Python 파일과 같은 폴더에 저장
    output_path = (
        BASE_DIR
        / filename
    )

    groups = group_items(
        data
    )

    payload = {

        "updated_at": (
            datetime.now()
            .strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        ),

        "total_count": len(
            data
        ),

        "count_by_type": {
            kind: len(items)
            for kind, items
            in groups.items()
        },

        "dtlLoc_matched": (
            match_info.get(
                "matched",
                0,
            )
        ),

        "dtlLoc_unmatched": (
            match_info.get(
                "unmatched",
                [],
            )
        ),

        "items": {

            kind: [
                pick_fields(
                    item
                )
                for item
                in items
            ]

            for kind, items
            in groups.items()
        },
    }

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            payload,
            f,
            ensure_ascii=False,
            indent=4,
        )

    summary = ", ".join(
        f"{kind} {len(items)}건"
        for kind, items
        in groups.items()
    ) or "0건"

    print()
    print(
        "=" * 60
    )

    print(
        f"[{payload['updated_at']}] "
        "데이터 업데이트 완료"
    )

    print(
        f"시설: {summary}"
    )

    print(
        f"저장 위치: {output_path}"
    )

    print(
        f"상세위치 1:1 매칭: "
        f"{payload['dtlLoc_matched']}/"
        f"{len(data)}건"
    )

    if (
        SHOW_UNMATCHED
        and
        payload[
            "dtlLoc_unmatched"
        ]
    ):

        print(
            "미매칭 elevatorNo:"
        )

        print(
            payload[
                "dtlLoc_unmatched"
            ]
        )

    print(
        "=" * 60
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print(
        "=" * 60
    )

    print(
        "승강기 실시간 운행정보 수집 프로그램"
    )

    print(
        "=" * 60
    )

    print(
        f"Python 파일 위치: {BASE_DIR}"
    )

    print(
        f"현재 작업 위치: {Path.cwd()}"
    )

    # --------------------------------------------------------
    # 상세 위치 데이터 로드
    # --------------------------------------------------------

    location_file = (
        find_location_file()
    )

    location_map = (
        load_location_map(
            location_file
        )
    )

    if not location_map:

        print()
        print(
            "⚠ 상세위치 데이터가 로드되지 않았습니다."
        )

        print(
            "elevatorNo 1:1 매칭이 불가능합니다."
        )

        print(
            "역사별_승강기_통합(번호).json의 "
            "위치를 확인해주세요."
        )

        print()

    else:

        print()
        print(
            "✓ 상세위치 데이터 준비 완료"
        )

        print(
            "elevatorNo 기준 1:1 매칭을 수행합니다."
        )

        print()

    # --------------------------------------------------------
    # 역 입력
    # --------------------------------------------------------

    buld_nm = input(
        "조회할 지하철 역을 입력하세요 "
        "(buld_nm): "
    ).strip()

    if not buld_nm:

        print(
            "건물명이 입력되지 않았습니다. "
            "프로그램을 종료합니다."
        )

        return

    print()

    print(
        f"'{buld_nm}' 건물 정보 수집 시작"
    )

    print(
        "1시간 간격 업데이트 / 종료: Ctrl+C"
    )

    print()

    # --------------------------------------------------------
    # 1시간 반복
    # --------------------------------------------------------

    while True:

        print()
        print(
            "=" * 60
        )

        print(
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
            f"{buld_nm} 조회 시작"
        )

        # API 조회
        filtered_data = (
            fetch_and_filter_elevators(
                buld_nm,
                SERVICE_KEY,
            )
        )

        print(
            f"API 조회 결과: "
            f"{len(filtered_data)}건"
        )

        # elevatorNo 1:1 위치 매칭
        matched, unmatched = (
            attach_locations(
                filtered_data,
                location_map,
            )
        )

        # JSON 저장
        save_to_json(
            filtered_data,

            building_name=(
                buld_nm
            ),

            match_info={
                "matched": matched,
                "unmatched": unmatched,
            },
        )

        # 콘솔 출력
        print_items(
            filtered_data,
            building_name=(
                buld_nm
            ),
        )

        print()
        print(
            "다음 업데이트까지 1시간 대기합니다."
        )

        print(
            "지금 종료하려면 Ctrl+C"
        )

        # 1시간
        time.sleep(
            3600
        )


if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        print()
        print(
            "프로그램을 종료합니다."
        )