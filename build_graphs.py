import json
import os
import re

def parse_section(section_str):
    """'B2-B1', '1-B1(DN)', 'B2~B1', 'B1-1' 등의 층 표현을 [출발층, 도착층]으로 정제"""
    if not section_str or section_str == "-":
        return "B1", "1F"
    
    cleaned = re.sub(r'\(.*?\)', '', str(section_str)).strip()
    parts = re.split(r'[-~]', cleaned)
    if len(parts) >= 2:
        f1, f2 = parts[0].strip(), parts[1].strip()
        f1 = f"{f1}F" if f1.isdigit() else f1
        f2 = f"{f2}F" if f2.isdigit() else f2
        return f1, f2
    return "B1", "1F"

def extract_facilities(data):
    """신규 RAW JSON의 'items' 구조에서 시설 추출"""
    facilities = []
    items_dict = data.get("items", {})

    for group_name, item_list in items_dict.items():
        for item in item_list:
            item_copy = item.copy()
            if "에스컬레이터" in group_name or "에스컬레이터" in str(item.get("elvtrDivNm", "")):
                item_copy["_type"] = "ESCALATOR"
            else:
                item_copy["_type"] = "ELEVATOR"
            facilities.append(item_copy)

    return facilities

def build_station_graph_new_spec(station_code, station_info):
    raw_file = station_info["raw_file"]
    station_name = station_info["name"]

    if not os.path.exists(raw_file):
        print(f"⚠️ {raw_file} 파일이 존재하지 않아 건너뜁니다.")
        return None

    with open(raw_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    facilities = extract_facilities(data)

    nodes_dict = {}
    edges = []

    ev_count = 0
    es_count = 0

    for idx, item in enumerate(facilities):
        is_elevator = (item.get("_type") == "ELEVATOR")
        transport_type = "ELEVATOR" if is_elevator else "ESCALATOR"
        wheelchair_accessible = is_elevator

        from_floor, to_floor = parse_section(item.get("shuttleSection", ""))
        dtl_loc = str(item.get("dtlLoc", "")).strip()
        exit_no = item.get("exitNo") or item.get("installationPlace")
        
        # 출구 번호 정제 (예: "2번출구" -> "2")
        if exit_no and isinstance(exit_no, str):
            exit_no_match = re.search(r'\d+', exit_no)
            exit_no_clean = exit_no_match.group() if exit_no_match else None
        else:
            exit_no_clean = str(exit_no) if exit_no else None

        line_name = station_info.get("line_name", "공통")

        # 1) 대합실 (CONCOURSE) 노드 생성을 위한 층 등록
        for fl in [from_floor, to_floor]:
            conc_id = f"{station_code}_{fl}_CONCOURSE"
            if conc_id not in nodes_dict:
                nodes_dict[conc_id] = {
                    "id": conc_id,
                    "station_code": station_code,
                    "station_name": station_name,
                    "type": "CONCOURSE",
                    "floor": fl,
                    "line_name": "공통",
                    "description": f"{station_name} {fl} 대합실/환승 구역"
                }

        # 2) 출구(EXIT) 노드 또는 승강장(PLATFORM) 상세 노드 생성
        if "1F" in [from_floor, to_floor] and exit_no_clean:
            # 출구 노드 생성
            exit_node_id = f"{station_code}_1F_EXIT_{exit_no_clean}"
            if exit_node_id not in nodes_dict:
                nodes_dict[exit_node_id] = {
                    "id": exit_node_id,
                    "station_code": station_code,
                    "station_name": station_name,
                    "type": "EXIT",
                    "floor": "1F",
                    "line_name": "공통",
                    "exit_no": exit_no_clean,
                    "description": f"{station_name} {exit_no_clean}번 출구"
                }
            target_platform_id = exit_node_id
        else:
            # PLATFORM 상세 지점 노드 생성
            type_code = "EV" if is_elevator else "ES"
            plat_node_id = f"{station_code}_LINE_01_{from_floor}_{type_code}_PLATFORM_{idx+1:03d}"
            
            nodes_dict[plat_node_id] = {
                "id": plat_node_id,
                "station_code": station_code,
                "station_name": station_name,
                "type": "PLATFORM",
                "floor": from_floor,
                "line_name": line_name,
                "detail_location": dtl_loc,
                "description": f"{station_name} {line_name} {from_floor} 승강장/인접 통로 ({dtl_loc})"
            }
            target_platform_id = plat_node_id

        # 3) 간선 (Edge) 데이터 구축
        from_conc = f"{station_code}_{from_floor}_CONCOURSE"
        to_conc = f"{station_code}_{to_floor}_CONCOURSE"
        
        # 시작/끝 연결 노드 결정
        from_node = target_platform_id if target_platform_id in nodes_dict else from_conc
        to_node = to_conc

        if is_elevator:
            ev_count += 1
            edge_id = f"{station_code}_01_EV_{ev_count:03d}"
        else:
            es_count += 1
            edge_id = f"{station_code}_01_ES_{es_count:03d}"

        edge_obj = {
            "id": edge_id,
            "station_name": station_name,
            "line_name": line_name,
            "from_node": from_node,
            "to_node": to_node,
            "transport_type": transport_type,
            "wheelchair_accessible": wheelchair_accessible,
            "is_bidirectional": True if is_elevator else False,
            "from_floor": from_floor,
            "to_floor": to_floor,
            "exit_no": exit_no_clean,
            "detail_location": dtl_loc,
            "operator_code": station_info.get("operator_code", "KR"),
            "line_code": station_info.get("line_code", "K1"),
            "kric_station_code": station_info.get("kric_code", ""),
            "description": f"{line_name} {transport_type.lower()} ({dtl_loc})"
        }

        if is_elevator:
            edge_obj["capacity_persons"] = item.get("rglnPsno") or 15
            edge_obj["capacity_weight_kg"] = item.get("rglnWgt") or 1000
        else:
            edge_obj["direction"] = "UP" if "UP" in str(exit_no).upper() or "상행" in dtl_loc else "DOWN"
            edge_obj["direction_name"] = "상행" if edge_obj["direction"] == "UP" else "하행"

        edges.append(edge_obj)

    nodes_list = list(nodes_dict.values())

    return {
        "station_id": station_code,
        "station_name": station_name,
        "source_files": [os.path.basename(raw_file)],
        "total_nodes": len(nodes_list),
        "total_edges": len(edges),
        "nodes": nodes_list,
        "edges": edges
    }

def main():
    os.makedirs("data_output", exist_ok=True)

    # 역별 정보 및 파일명 후보 지정 (한글/영문 모두 지원)
    target_stations = {
        "PGY": {"name": "판교역", "raw_files": ["data_raw/판교역 승강기 현황.json", "data_raw/pangyo_raw.json"], "line_name": "신분당선/경강선", "operator_code": "DX/KR", "line_code": "D1/K5"},
        "JGJ": {"name": "정자역", "raw_files": ["data_raw/정자역 승강기 현황.json", "data_raw/jeongja_raw.json"], "line_name": "수인분당선/신분당선", "operator_code": "KR/DX", "line_code": "K1/D1"},
        "YTP": {"name": "야탑역", "raw_files": ["data_raw/야탑역 승강기 현황.json", "data_raw/yatap_raw.json"], "line_name": "수인분당선", "operator_code": "KR", "line_code": "K1"},
        "SNE": {"name": "수내역", "raw_files": ["data_raw/수내역 승강기 현황.json", "data_raw/sunae_raw.json"], "line_name": "수인분당선", "operator_code": "KR", "line_code": "K1"},
        "SHY": {"name": "서현역", "raw_files": ["data_raw/서현역 승강기 현황.json", "data_raw/seohyeon_raw.json"], "line_name": "수인분당선", "operator_code": "KR", "line_code": "K1"},
        "IME": {"name": "이매역", "raw_files": ["data_raw/이매역 승강기 현황.json", "data_raw/imae_raw.json"], "line_name": "수인분당선/경강선", "operator_code": "KR", "line_code": "K1/K5"},
        "GCH": {"name": "가천대역", "raw_files": ["data_raw/가천대역 승강기 현황.json", "data_raw/gachon_raw.json"], "line_name": "수인분당선", "operator_code": "KR", "line_code": "K1"},
        "TPG": {"name": "태평역", "raw_files": ["data_raw/태평역 승강기 현황.json", "data_raw/taepyeong_raw.json"], "line_name": "수인분당선", "operator_code": "KR", "line_code": "K1"},
        "MRN": {"name": "모란역", "raw_files": ["data_raw/모란역 승강기 현황.json", "data_raw/moran_raw.json"], "line_name": "수인분당선/8호선", "operator_code": "KR/S8", "line_code": "K1/8"},
        "MGM": {"name": "미금역", "raw_files": ["data_raw/미금역 승강기 현황.json", "data_raw/migeum_raw.json"], "line_name": "수인분당선/신분당선", "operator_code": "KR/DX", "line_code": "K1/D1"},
        "ORI": {"name": "오리역", "raw_files": ["data_raw/오리역 승강기 현황.json", "data_raw/ori_raw.json"], "line_name": "수인분당선", "operator_code": "KR", "line_code": "K1"},
        "NWR": {"name": "남위례역", "raw_files": ["data_raw/남위례역 승강기 현황.json", "data_raw/namworye_raw.json"], "line_name": "8호선", "operator_code": "S8", "line_code": "8"},
        "SSG": {"name": "산성역", "raw_files": ["data_raw/산성역 승강기 현황.json", "data_raw/sanseong_raw.json"], "line_name": "8호선", "operator_code": "S8", "line_code": "8"},
        "NHS": {"name": "남한산성입구역", "raw_files": ["data_raw/남한산성입구역 승강기 현황.json", "data_raw/namhan_raw.json"], "line_name": "8호선", "operator_code": "S8", "line_code": "8"},
        "DDE": {"name": "단대오거리역", "raw_files": ["data_raw/단대오거리역 승강기 현황.json", "data_raw/dandae_raw.json"], "line_name": "8호선", "operator_code": "S8", "line_code": "8"},
        "SHN": {"name": "신흥역", "raw_files": ["data_raw/신흥역 승강기 현황.json", "data_raw/sinheung_raw.json"], "line_name": "8호선", "operator_code": "S8", "line_code": "8"},
        "SJN": {"name": "수진역", "raw_files": ["data_raw/수진역 승강기 현황.json", "data_raw/sujin_raw.json"], "line_name": "8호선", "operator_code": "S8", "line_code": "8"},
        "SNM": {"name": "성남역", "raw_files": ["data_raw/성남역 승강기 현황.json", "data_raw/seongnam_raw.json"], "line_name": "경강선/GTX-A", "operator_code": "KR", "line_code": "K5/GX"}
    }

    formatted_all_stations = {}
    success_count = 0

    for code, info in target_stations.items():
        # 존재하는 파일 탐색
        actual_raw_file = None
        for candidate in info["raw_files"]:
            if os.path.exists(candidate):
                actual_raw_file = candidate
                break

        if not actual_raw_file:
            print(f"⚠️ {info['name']}({code}) 파일이 존재하지 않아 건너뜁니다.")
            continue

        info["raw_file"] = actual_raw_file
        graph_data = build_station_graph_new_spec(code, info)
        if graph_data:
            station_name = info["name"]
            formatted_all_stations[station_name] = graph_data
            success_count += 1
            print(f"✅ {station_name}({code}) 새 규격 변환 완료 (노드: {graph_data['total_nodes']}개, 간선: {graph_data['total_edges']}개)")

    with open("data_output/all_stations_graph.json", "w", encoding="utf-8") as f:
        json.dump(formatted_all_stations, f, ensure_ascii=False, indent=2)

    print(f"\n🎉 전체 {success_count}개 역 신규 규격 통합 JSON 저장 완료! ➔ data_output/all_stations_graph.json")

if __name__ == "__main__":
    main()