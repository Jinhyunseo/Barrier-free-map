import json
import os
import re

def parse_section(section_str):
    """'B2-B1', '1-B1(DN)', 'B2~B1', 'B1-1' 등의 층 표현을 [출발층, 도착층]으로 정제"""
    if not section_str or section_str == "-":
        return "B1", "1F"
    
    # 괄호 속문구 (DN), (UP) 등 제거
    cleaned = re.sub(r'\(.*?\)', '', str(section_str)).strip()
    parts = re.split(r'[-~]', cleaned)
    if len(parts) >= 2:
        f1, f2 = parts[0].strip(), parts[1].strip()
        f1 = f"{f1}F" if f1.isdigit() else f1
        f2 = f"{f2}F" if f2.isdigit() else f2
        return f1, f2
    return "B1", "1F"

def extract_facilities(data):
    """팀원이 제공한 신규 'items' 구조에서 시설 및 dtlLoc 데이터 직접 추출"""
    facilities = []
    items_dict = data.get("items", {})

    for group_name, item_list in items_dict.items():
        for item in item_list:
            item_copy = item.copy()
            # 엘리베이터 / 에스컬레이터 구분
            if "에스컬레이터" in group_name or "에스컬레이터" in str(item.get("elvtrDivNm", "")):
                item_copy["_type"] = "ESCALATOR"
            else:
                item_copy["_type"] = "ELEVATOR"
            facilities.append(item_copy)

    return facilities

def build_station_graph(station_code, station_info):
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

    for idx, item in enumerate(facilities):
        status = item.get("elvtrStts", "운행중")
        fac_id = str(item.get("elevatorNo", f"{idx+1}"))
        dtl_loc = str(item.get("dtlLoc", "")).strip()

        is_elevator = (item.get("_type") == "ELEVATOR")
        transport_type = "ELEVATOR" if is_elevator else "ESCALATOR"
        wheelchair_accessible = is_elevator

        section = item.get("shuttleSection", "")
        from_floor, to_floor = parse_section(section)

        # 상세 지점 노드 ID 생성
        from_node_id = f"{station_code}_{from_floor}_FAC_{fac_id}_START"
        to_node_id = f"{station_code}_{to_floor}_FAC_{fac_id}_END"

        # dtlLoc 데이터 적용 (설명이 명확하게 노출됨)
        if dtl_loc and dtl_loc != "-":
            from_desc = f"{station_name} {from_floor} ({dtl_loc})"
            to_desc = f"{station_name} {to_floor} ({dtl_loc})"
        else:
            from_desc = f"{station_name} {from_floor} {transport_type} 구역 ({fac_id})"
            to_desc = f"{station_name} {to_floor} {transport_type} 구역 ({fac_id})"

        # 층별 보행 허브 노드
        from_floor_hub = f"{station_code}_{from_floor}_HUB"
        to_floor_hub = f"{station_code}_{to_floor}_HUB"

        for hub_id, floor_str in [(from_floor_hub, from_floor), (to_floor_hub, to_floor)]:
            if hub_id not in nodes_dict:
                nodes_dict[hub_id] = {
                    "id": hub_id,
                    "station_code": station_code,
                    "station_name": station_name,
                    "floor": floor_str,
                    "type": "FLOOR_HUB",
                    "description": f"{station_name} {floor_str} 대합실/통로 중앙"
                }

        # 시설 지점 노드 등록
        nodes_dict[from_node_id] = {
            "id": from_node_id,
            "station_code": station_code,
            "station_name": station_name,
            "floor": from_floor,
            "type": "FACILITY_POINT",
            "description": from_desc
        }
        nodes_dict[to_node_id] = {
            "id": to_node_id,
            "station_code": station_code,
            "station_name": station_name,
            "floor": to_floor,
            "type": "FACILITY_POINT",
            "description": to_desc
        }

        # 1) 수직 이동 간선 (ELEVATOR / ESCALATOR)
        edge_fac_id = f"EDGE_{station_code}_{fac_id}"
        edges.append({
            "id": f"{edge_fac_id}_UP",
            "from_node": from_node_id,
            "to_node": to_node_id,
            "transport_type": transport_type,
            "wheelchair_accessible": wheelchair_accessible,
            "status": status
        })
        edges.append({
            "id": f"{edge_fac_id}_DOWN",
            "from_node": to_node_id,
            "to_node": from_node_id,
            "transport_type": transport_type,
            "wheelchair_accessible": wheelchair_accessible,
            "status": status
        })

        # 2) 평지 보행 간선 (WALK)
        edges.append({
            "id": f"WALK_{from_node_id}_HUB",
            "from_node": from_node_id,
            "to_node": from_floor_hub,
            "transport_type": "WALK",
            "wheelchair_accessible": True,
            "status": "운행중"
        })
        edges.append({
            "id": f"WALK_HUB_{from_node_id}",
            "from_node": from_floor_hub,
            "to_node": from_node_id,
            "transport_type": "WALK",
            "wheelchair_accessible": True,
            "status": "운행중"
        })
        edges.append({
            "id": f"WALK_{to_node_id}_HUB",
            "from_node": to_node_id,
            "to_node": to_floor_hub,
            "transport_type": "WALK",
            "wheelchair_accessible": True,
            "status": "운행중"
        })
        edges.append({
            "id": f"WALK_HUB_{to_node_id}",
            "from_node": to_floor_hub,
            "to_node": to_node_id,
            "transport_type": "WALK",
            "wheelchair_accessible": True,
            "status": "운행중"
        })

    return {
        "station_code": station_code,
        "station_name": station_name,
        "nodes": list(nodes_dict.values()),
        "edges": edges
    }

def main():
    os.makedirs("data_output", exist_ok=True)

    target_stations = {
        "PGY": {"name": "판교역", "raw_file": "data_raw/pangyo_raw.json"},
        "JGJ": {"name": "정자역", "raw_file": "data_raw/jeongja_raw.json"},
        "YTP": {"name": "야탑역", "raw_file": "data_raw/yatap_raw.json"},
        "SNE": {"name": "수내역", "raw_file": "data_raw/sunae_raw.json"},
        "SHY": {"name": "서현역", "raw_file": "data_raw/seohyeon_raw.json"},
        "IME": {"name": "이매역", "raw_file": "data_raw/imae_raw.json"},
        "GCH": {"name": "가천대역", "raw_file": "data_raw/gachon_raw.json"},
        "TPG": {"name": "태평역", "raw_file": "data_raw/taepyeong_raw.json"},
        "MRN": {"name": "모란역", "raw_file": "data_raw/moran_raw.json"},
        "MGM": {"name": "미금역", "raw_file": "data_raw/migeum_raw.json"},
        "ORI": {"name": "오리역", "raw_file": "data_raw/ori_raw.json"},
        "NWR": {"name": "남위례역", "raw_file": "data_raw/namworye_raw.json"},
        "SSG": {"name": "산성역", "raw_file": "data_raw/sanseong_raw.json"},
        "NHS": {"name": "남한산성입구역", "raw_file": "data_raw/namhan_raw.json"},
        "DDE": {"name": "단대오거리역", "raw_file": "data_raw/dandae_raw.json"},
        "SHN": {"name": "신흥역", "raw_file": "data_raw/sinheung_raw.json"},
        "SJN": {"name": "수진역", "raw_file": "data_raw/sujin_raw.json"},
        "SNM": {"name": "성남역", "raw_file": "data_raw/seongnam_raw.json"}
    }

    all_stations_data = {}
    success_count = 0

    for code, info in target_stations.items():
        graph_data = build_station_graph(code, info)
        if graph_data:
            output_file = f"data_output/{code}_graph.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(graph_data, f, ensure_ascii=False, indent=2)

            node_cnt = len(graph_data["nodes"])
            edge_cnt = len(graph_data["edges"])
            print(f"✅ {info['name']}({code}) 그래프 생성 완료 ➔ {output_file} (노드: {node_cnt}개, 간선: {edge_cnt}개)")

            all_stations_data[code] = graph_data
            success_count += 1

    with open("data_output/all_stations_graph.json", "w", encoding="utf-8") as f:
        json.dump(all_stations_data, f, ensure_ascii=False, indent=2)

    print(f"\n🎉 전체 {success_count}개 역 dtlLoc 반영 정밀 그래프 저장 완료! ➔ data_output/all_stations_graph.json")

if __name__ == "__main__":
    main()