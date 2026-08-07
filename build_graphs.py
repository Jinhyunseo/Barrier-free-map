import json
import os
import re

# 1. 층수 코드 정규화 함수
def format_floor_code(ground_type, floor_num):
    try:
        f_num = int(float(floor_num))
    except (ValueError, TypeError):
        f_num = 1
    return f"B{f_num}" if ground_type == "지하" else f"{f_num}F"

# 2. 노선 정보 매핑 함수
def extract_line_info(opr_cd, line_cd):
    if opr_cd == "DX":
        return "신분당선", "SB"
    elif opr_cd == "KR":
        if line_cd == "K1":
            return "수인분당선", "SU"
        elif line_cd == "K5":
            return "경강선", "KK"
        return "수인분당선", "SU"
    return "공통", "COMM"

FACILITY_TYPE_MAP = {
    "TOLT": "화장실",
    "ELEC": "전동휠체어충전기",
    "INFO": "고객안내센터",
    "FEED": "유아휴게실/수유실",
    "ATM": "현금수출입기"
}

# 3. 데이터 구조 완충 파싱 헬퍼
def extract_body_list(data_dict):
    body_list = []
    if not isinstance(data_dict, dict):
        return body_list
    
    if "body" in data_dict and isinstance(data_dict["body"], list):
        body_list.extend(data_dict["body"])
    else:
        for key, val in data_dict.items():
            if isinstance(val, dict) and "body" in val and isinstance(val["body"], list):
                body_list.extend(val["body"])
    return body_list

# 4. 역별 노드/간선 변환 메인 로직 (weight_sec 이동시간 제외)
def convert_raw_to_graph(station_code, station_name, raw_data):
    nodes_dict = {}
    edges_set = set()
    edges_list = []

    # [통합 허브 노드] 대합실
    main_conc_id = f"{station_code}_CONCOURSE"
    nodes_dict[main_conc_id] = {
        "id": main_conc_id,
        "station_code": station_code,
        "station_name": station_name,
        "type": "CONCOURSE",
        "floor": "B1/B2",
        "line": "공통",
        "description": f"{station_name} 통합 대합실/환승 구역"
    }

    # ==================== [A] 엘리베이터 (EV) 파싱 ====================
    el_raw = raw_data.get("elevator", raw_data)
    elevator_items = extract_body_list(el_raw)

    for idx, item in enumerate(elevator_items):
        opr_cd = item.get("railOprIsttCd")
        line_cd = item.get("lnCd")
        line_name, line_code = extract_line_info(opr_cd, line_cd)

        from_floor = format_floor_code(item.get("grndDvNmFr", "지하"), item.get("runStinFlorFr", 1))
        to_floor = format_floor_code(item.get("grndDvNmTo", "지하"), item.get("runStinFlorTo", 1))
        dtl_loc = item.get("dtlLoc", "").strip()

        exit_no = item.get("exitNo")
        if not exit_no:
            match = re.search(r'(\d+)번\s*출입구', dtl_loc)
            if match:
                exit_no = match.group(1)

        if exit_no or from_floor == "1F" or to_floor == "1F":
            exit_num_str = f"{int(exit_no):02d}" if exit_no and str(exit_no).isdigit() else "01"
            exit_node_id = f"{station_code}_1F_EXIT_{exit_num_str}"

            if exit_node_id not in nodes_dict:
                nodes_dict[exit_node_id] = {
                    "id": exit_node_id,
                    "station_code": station_code,
                    "station_name": station_name,
                    "type": "EXIT",
                    "floor": "1F",
                    "line": "공통",
                    "description": f"{station_name} {exit_num_str}번 출구 (지상)"
                }

            edge_key = tuple(sorted([exit_node_id, main_conc_id]) + ["EV"])
            if edge_key not in edges_set:
                edges_set.add(edge_key)
                edges_list.append({
                    "id": f"EDGE_EV_{station_code}_EXIT_{exit_num_str}",
                    "from_node": exit_node_id,
                    "to_node": main_conc_id,
                    "transport_type": "ELEVATOR",
                    "wheelchair_accessible": True,
                    "is_bidirectional": True,
                    "capacity_persons": item.get("rglnPsno", 15),
                    "capacity_weight_kg": item.get("rglnWgt", 1000),
                    "description": f"{exit_num_str}번 출구 ↔ 대합실 엘리베이터"
                })
        else:
            try:
                fr_num = int(float(item.get("runStinFlorFr", 1)))
                to_num = int(float(item.get("runStinFlorTo", 1)))
            except (ValueError, TypeError):
                fr_num, to_num = 1, 2

            deep_floor = f"B{max(fr_num, to_num)}"
            plat_node_id = f"{station_code}_{deep_floor}_{line_code}_PLAT_{idx+1:02d}"

            nodes_dict[plat_node_id] = {
                "id": plat_node_id,
                "station_code": station_code,
                "station_name": station_name,
                "type": "PLATFORM",
                "floor": deep_floor,
                "line": line_name,
                "description": f"{station_name} {line_name} {deep_floor} 승강장 ({dtl_loc})"
            }

            edge_key = tuple(sorted([plat_node_id, main_conc_id]) + ["EV"])
            if edge_key not in edges_set:
                edges_set.add(edge_key)
                edges_list.append({
                    "id": f"EDGE_EV_{station_code}_{line_code}_{idx+1:02d}",
                    "from_node": plat_node_id,
                    "to_node": main_conc_id,
                    "transport_type": "ELEVATOR",
                    "wheelchair_accessible": True,
                    "is_bidirectional": True,
                    "capacity_persons": item.get("rglnPsno", 15),
                    "capacity_weight_kg": item.get("rglnWgt", 1000),
                    "description": f"{line_name} {deep_floor} 승강장 ↔ 대합실 엘리베이터"
                })

    # ==================== [B] 에스컬레이터 (ESC) 파싱 ====================
    esc_raw = raw_data.get("escalator", {})
    escalator_items = extract_body_list(esc_raw)

    for idx, item in enumerate(escalator_items):
        opr_cd = item.get("railOprIsttCd")
        line_cd = item.get("lnCd")
        line_name, line_code = extract_line_info(opr_cd, line_cd)

        from_floor = format_floor_code(item.get("grndDvNmFr", "지하"), item.get("runStinFlorFr", 1))
        to_floor = format_floor_code(item.get("grndDvNmTo", "지하"), item.get("runStinFlorTo", 1))
        updn_dir = item.get("updnDvNm", "상행")
        dtl_loc = item.get("dtlLoc", "").strip()
        exit_no = item.get("exitNo")

        if exit_no or from_floor == "1F" or to_floor == "1F":
            exit_str = f"{int(exit_no):02d}" if exit_no and str(exit_no).isdigit() else "01"
            exit_node_id = f"{station_code}_1F_EXIT_{exit_str}"

            if exit_node_id not in nodes_dict:
                nodes_dict[exit_node_id] = {
                    "id": exit_node_id,
                    "station_code": station_code,
                    "station_name": station_name,
                    "type": "EXIT",
                    "floor": "1F",
                    "line": "공통",
                    "description": f"{station_name} {exit_str}번 출구 (지상)"
                }
            from_id = main_conc_id if from_floor != "1F" else exit_node_id
            to_id = exit_node_id if to_floor == "1F" else main_conc_id
        else:
            try:
                fr_num = int(float(item.get("runStinFlorFr", 1)))
                to_num = int(float(item.get("runStinFlorTo", 1)))
            except (ValueError, TypeError):
                fr_num, to_num = 1, 2

            deep_floor = f"B{max(fr_num, to_num)}"
            plat_node_id = f"{station_code}_{deep_floor}_{line_code}_ESC_PLAT_{idx+1:02d}"

            nodes_dict[plat_node_id] = {
                "id": plat_node_id,
                "station_code": station_code,
                "station_name": station_name,
                "type": "PLATFORM",
                "floor": deep_floor,
                "line": line_name,
                "description": f"{station_name} {line_name} {deep_floor} 승강장/통로 ({dtl_loc})"
            }

            from_id = main_conc_id if fr_num < to_num else plat_node_id
            to_id = plat_node_id if fr_num < to_num else main_conc_id

        edges_list.append({
            "id": f"EDGE_ESC_{station_code}_{idx+1:03d}",
            "from_node": from_id,
            "to_node": to_id,
            "transport_type": "ESCALATOR",
            "wheelchair_accessible": False,
            "direction": "UP" if updn_dir == "상행" else "DOWN",
            "is_bidirectional": False,
            "description": f"에스컬레이터 ({dtl_loc})"
        })

    # ==================== [C] 편의시설 (POI) 파싱 ====================
    conv_raw = raw_data.get("convenience", {})
    convenience_items = extract_body_list(conv_raw)

    for idx, item in enumerate(convenience_items):
        raw_gubun = item.get("gubun", "FACILITY")
        
        if raw_gubun == "EV":
            continue

        facility_name = FACILITY_TYPE_MAP.get(raw_gubun, "편의시설")
        dtl_loc = item.get("dtlLoc", "").strip()
        floor_num = item.get("stinFlor", "1")
        floor_code = f"B{floor_num}"

        is_handicapped = item.get("trfcWeakDvCd") == "1"
        if is_handicapped and raw_gubun == "TOLT":
            facility_name = "장애인화장실"

        poi_node_id = f"{station_code}_{floor_code}_POI_{raw_gubun}_{idx+1:02d}"

        nodes_dict[poi_node_id] = {
            "id": poi_node_id,
            "station_code": station_code,
            "station_name": station_name,
            "type": "FACILITY",
            "facility_type": facility_name,
            "floor": floor_code,
            "description": f"{station_name} {facility_name} ({dtl_loc})"
        }

        edges_list.append({
            "id": f"EDGE_WALK_{station_code}_POI_{idx+1:02d}",
            "from_node": main_conc_id,
            "to_node": poi_node_id,
            "transport_type": "WALK",
            "wheelchair_accessible": True,
            "is_bidirectional": True,
            "description": f"대합실 ↔ {facility_name} 보행 통로"
        })

    return {
        "station_id": station_code,
        "station_name": station_name,
        "total_nodes": len(nodes_dict),
        "total_edges": len(edges_list),
        "nodes": list(nodes_dict.values()),
        "edges": edges_list
    }

# 5. 메인 실행 로직 (6개 역 전체 일괄 처리)
if __name__ == "__main__":
    target_stations = {
        "PGY": {"name": "판교역", "raw_file": "data_raw/pangyo_raw.json"},
        "JGJ": {"name": "정자역", "raw_file": "data_raw/jeongja_raw.json"},
        "YTP": {"name": "야탑역", "raw_file": "data_raw/yatap_raw.json"},
        "SNE": {"name": "수내역", "raw_file": "data_raw/sunae_raw.json"},
        "SHY": {"name": "서현역", "raw_file": "data_raw/seohyeon_raw.json"},
        "IME": {"name": "이매역", "raw_file": "data_raw/imae_raw.json"}
    }

    all_graphs = {}

    for stn_cd, info in target_stations.items():
        file_path = info["raw_file"]

        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)

            graph = convert_raw_to_graph(stn_cd, info["name"], raw_data)

            out_path = f"data_output/{stn_cd}_graph.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(graph, f, ensure_ascii=False, indent=2)

            all_graphs[stn_cd] = graph
            print(f"✅ {info['name']}({stn_cd}) 그래프 변환 완료 ➔ {out_path} (노드: {graph['total_nodes']}개, 간선: {graph['total_edges']}개)")
        else:
            print(f"⚠️ {file_path} 파일이 존재하지 않아 건너뜁니다.")

    if all_graphs:
        integrated_path = "data_output/all_stations_graph.json"
        with open(integrated_path, "w", encoding="utf-8") as f:
            json.dump(all_graphs, f, ensure_ascii=False, indent=2)
        print(f"\n🎉 전체 {len(all_graphs)}개 역 통합 그래프 JSON 저장 완료! ➔ {integrated_path}")