import json
import os
import re

def parse_section(section_str):
    """'B2-B1', '1-B1(DN)', 'B2~B1' 등의 층 표현을 [출발층, 도착층]으로 정제"""
    if not section_str or section_str == "-":
        return None, None
    
    cleaned = re.sub(r'\(.*?\)', '', str(section_str)).strip()
    parts = re.split(r'[-~]', cleaned)
    if len(parts) >= 2:
        f1, f2 = parts[0].strip(), parts[1].strip()
        f1 = f"{f1}F" if f1.isdigit() else f1
        f2 = f"{f2}F" if f2.isdigit() else f2
        return f1, f2
    return None, None

def extract_facilities(data):
    """모든 JSON 구조(기존 6개 역 + 신규 12개 역)에서 승강기 시설 데이터 완전 추출"""
    facilities = []

    def search(obj, current_type=None):
        if isinstance(obj, dict):
            if any(k in obj for k in ["railOprIsttCd", "runStinFlorFr", "elevatorNo", "shuttleSection", "elvtrDivNm"]):
                item_copy = obj.copy()
                div_nm = str(obj.get("elvtrDivNm", "")) or str(obj.get("elvtrKindNm", ""))
                
                if "엘리베이터" in div_nm or "장애인" in div_nm or current_type == "ELEVATOR":
                    item_copy["_type"] = "ELEVATOR"
                elif "에스컬레이터" in div_nm or current_type == "ESCALATOR":
                    item_copy["_type"] = "ESCALATOR"
                else:
                    item_copy["_type"] = "ELEVATOR"
                facilities.append(item_copy)
            else:
                for key, val in obj.items():
                    next_type = current_type
                    key_lower = str(key).lower()
                    if "elevator" in key_lower or "엘리베이터" in key_lower:
                        next_type = "ELEVATOR"
                    elif "escalator" in key_lower or "에스컬레이터" in key_lower:
                        next_type = "ESCALATOR"
                    search(val, next_type)
        elif isinstance(obj, list):
            for elem in obj:
                search(elem, current_type)

    search(data)
    return facilities

def get_floors_from_item(item):
    """시설 항목에서 출발층과 도착층 추출"""
    section = item.get("shuttleSection") or item.get("section") or ""
    from_floor, to_floor = parse_section(section)
    if from_floor and to_floor:
        return from_floor, to_floor

    if "runStinFlorFr" in item and "runStinFlorTo" in item:
        fr_num = item.get("runStinFlorFr")
        to_num = item.get("runStinFlorTo")
        if fr_num is not None and to_num is not None:
            fr_is_underground = (item.get("grndDvNmFr") == "지하")
            to_is_underground = (item.get("grndDvNmTo") == "지하")
            
            from_floor = f"B{fr_num}" if fr_is_underground else f"{fr_num}F"
            to_floor = f"B{to_num}" if to_is_underground else f"{to_num}F"
            return from_floor, to_floor

    return "B1", "1F"

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

    # 시설 정보를 기반으로 상세 지점 노드 및 간선 생성
    for idx, item in enumerate(facilities):
        div_nm = str(item.get("elvtrDivNm", "")) or str(item.get("elvtrKindNm", ""))
        status = item.get("elvtrStts") or "운행중"
        fac_id = item.get("elevatorNo") or item.get("elvtrMgtNo1") or f"{idx+1}"
        dtl_loc = str(item.get("dtlLoc", "")).strip()

        is_elevator = (item.get("_type") == "ELEVATOR")
        transport_type = "ELEVATOR" if is_elevator else "ESCALATOR"
        wheelchair_accessible = True if is_elevator else False

        from_floor, to_floor = get_floors_from_item(item)

        # 상세 지점 노드 ID 생성 (승강기 탑승/내리는 개별 지점)
        from_node_id = f"{station_code}_{from_floor}_FAC_{fac_id}_START"
        to_node_id = f"{station_code}_{to_floor}_FAC_{fac_id}_END"

        # 상세 설명 생성
        if dtl_loc and dtl_loc != "-":
            from_desc = f"{station_name} {from_floor} ({dtl_loc})"
            to_desc = f"{station_name} {to_floor} ({dtl_loc})"
        else:
            from_desc = f"{station_name} {from_floor} {transport_type} 구역 ({fac_id})"
            to_desc = f"{station_name} {to_floor} {transport_type} 구역 ({fac_id})"

        # 층별 공용 보행 허브 노드 (해당 층 내부 보행 전용)
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

        # 출발지/도착지 상세 노드 등록
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

        # 1) 층간 수직 이동 간선 (ELEVATOR / ESCALATOR) - 층과 층 사이 이동
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

        # 2) 동일 층 내부 보행 간선 (WALK) - 같은 층 노드끼리만 평지 연결
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

    nodes = list(nodes_dict.values())
    return {
        "station_code": station_code,
        "station_name": station_name,
        "nodes": nodes,
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
            print(f"✅ {info['name']}({code}) 그래프 재구축 완료 ➔ {output_file} (노드: {node_cnt}개, 간선: {edge_cnt}개)")

            all_stations_data[code] = graph_data
            success_count += 1

    with open("data_output/all_stations_graph.json", "w", encoding="utf-8") as f:
        json.dump(all_stations_data, f, ensure_ascii=False, indent=2)

    print(f"\n🎉 전체 {success_count}개 역 물리 기반 그래프 저장 완료! ➔ data_output/all_stations_graph.json")

if __name__ == "__main__":
    main()