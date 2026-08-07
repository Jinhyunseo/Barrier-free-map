import heapq

# ==============================================================================
# 1. 가짜 지도 데이터 (sample_map)
#    - 노드(점): 'A_출발지', 'B_일반버스정류장' 등 각 장소
#    - 간선(선): 각 장소 사이를 연결하는 도로 및 대중교통 정보
# ==============================================================================
sample_map = {
    'A_출발지': [
        {
            'to': 'B_일반버스정류장',      # 목적지 노드 이름
            'type': 'walk',                # 이동 수단 ('walk', 'bus', 'subway')
            'travel_time_min': 5,          # 소요 시간 (분)
            'walk_distance_m': 300,        # 보행 거리 (m)
            'has_stairs': False,           # 계단 존재 여부 (True/False)
            'incline': 2.0,                # 경사도 (%)
            'curb_height': 1,              # 보도 턱 높이 (cm)
            'is_transfer': False,          # 환승 구간 여부
            'has_elevator': False,         # 엘리베이터 설치 여부
            'is_low_floor_bus': False      # 저상버스 여부
        },
        {
            'to': 'C_지하철역_입구',
            'type': 'walk',
            'travel_time_min': 8,
            'walk_distance_m': 450,
            'has_stairs': True,            # ⚠️ 계단 있음 (휠체어/유모차 회피 대상)
            'incline': 1.0,
            'curb_height': 0,
            'is_transfer': False,
            'has_elevator': False,
            'is_low_floor_bus': False
        },
        {
            'to': 'D_저상버스정류장',
            'type': 'walk',
            'travel_time_min': 10,
            'walk_distance_m': 600,        # 거리는 더 길지만 평탄하고 넓은 길
            'has_stairs': False,
            'incline': 1.5,
            'curb_height': 1,
            'is_transfer': False,
            'has_elevator': False,
            'is_low_floor_bus': False
        }
    ],
    'B_일반버스정류장': [
        {
            'to': 'E_환승센터',
            'type': 'bus',
            'travel_time_min': 15,
            'walk_distance_m': 0,
            'has_stairs': False,
            'incline': 0.0,
            'curb_height': 0,
            'is_transfer': False,
            'has_elevator': False,
            'is_low_floor_bus': False      # ⚠️ 일반버스 (수동 휠체어 탑승 불가)
        }
    ],
    'C_지하철역_입구': [
        {
            'to': 'E_환승센터',
            'type': 'subway',
            'travel_time_min': 10,
            'walk_distance_m': 50,
            'has_stairs': False,
            'incline': 0.0,
            'curb_height': 0,
            'is_transfer': False,
            'has_elevator': True,          # ⭕ 엘리베이터 지원 (편의성 높음)
            'is_low_floor_bus': False
        }
    ],
    'D_저상버스정류장': [
        {
            'to': 'E_환승센터',
            'type': 'bus',
            'travel_time_min': 12,
            'walk_distance_m': 0,
            'has_stairs': False,
            'incline': 0.0,
            'curb_height': 0,
            'is_transfer': False,
            'has_elevator': False,
            'is_low_floor_bus': True       # ⭕ 저상버스 지원
        }
    ],
    'E_환승센터': [
        {
            'to': 'F_도착지',
            'type': 'walk',
            'travel_time_min': 5,
            'walk_distance_m': 200,
            'has_stairs': False,
            'incline': 2.0,
            'curb_height': 1,
            'is_transfer': True,           # ⚠️ 환승 구간
            'has_elevator': True,
            'is_low_floor_bus': False
        }
    ],
    'F_도착지': [] # 목적지는 나가는 길 없음
}


# ==============================================================================
# 2. 사용자 유형별 기준 및 가중치 설정 (USER_CONFIGS)
#    - max_*: 절대 넘으면 안 되는 물리적 한계 (Hard Barrier)
#    - weights: 불편함 점수를 계산할 때 곱해줄 가중치 (Soft Scoring)
# ==============================================================================
USER_CONFIGS = {
    'manual_wheelchair': {
        'name': '👩‍🦼 수동 휠체어',
        # --- 안전 제한 조건 (하나라도 어기면 이 길은 통과 불가) ---
        'max_incline': 8.3,             # 경사도 8.3% 이상 진입 불가 (법적 기준)
        'max_curb': 2,                  # 턱 높이 2cm 초과 진입 불가
        'allow_stairs': False,          # 계단 절대 이용 불가
        'require_low_floor_bus': True,  # 버스 이용 시 저상버스 필수
        # --- 불편함 점수 가중치 (점수가 높을수록 원치 않는 길) ---
        'weights': {
            'time_per_min': 1.0,        # 1분당 +1.0점
            'walk_dist_per_m': 0.08,    # 수동 휠체어는 팔로 밀어야 하므로 거리 패널티가 큼
            'transfer_penalty': 20.0,   # 환승 시 큰 부담 패널티
            'elevator_bonus': -8.0,     # 엘리베이터가 있으면 점수 차감 (선호)
            'low_bus_bonus': -15.0      # 저상버스는 점수 큰 차감 (선호)
        }
    },
    'electric_wheelchair': {
        'name': '👨‍🦼 전동 휠체어',
        'max_incline': 10.0,            # 수동보다 경사 등판 능력이 높음 (10%)
        'max_curb': 3,                  # 수동보다 약간 높은 턱(3cm) 극복 가능
        'allow_stairs': False,          # 계단 절대 불가
        'require_low_floor_bus': True,  # 저상버스 필수 (경사판 이용 탑승)
        'weights': {
            'time_per_min': 1.0,
            'walk_dist_per_m': 0.02,    # 모터 동력이므로 거리 부담이 매우 적음
            'transfer_penalty': 25.0,   # 차체가 크고 무거워 승하차/환승 시 시간이 더 걸림
            'elevator_bonus': -10.0,    # 차체가 크므로 승강기 선호도 높음
            'low_bus_bonus': -15.0      # 저상버스 필수 선호
        }
    },
    'stroller': {
        'name': '👶 유모차',
        'max_incline': 10.0,            # 휠체어보다는 완만한 경사 감당 가능
        'max_curb': 5,                  # 턱 5cm까지는 밀어서 넘을 수 있음
        'allow_stairs': False,          # 계단 이용 불가
        'require_low_floor_bus': False, # 상황에 따라 일반버스도 접어서 탑승 가능
        'weights': {
            'time_per_min': 1.0,
            'walk_dist_per_m': 0.03,    # 바퀴가 있어 보행 거리 부담이 휠체어보다 적음
            'transfer_penalty': 15.0,
            'elevator_bonus': -10.0,    # 엘리베이터 매우 선호
            'low_bus_bonus': -5.0
        }
    },
    'elderly': {
        'name': '🧓 고령자 ',
        'max_incline': 8.3,             # 완만한 경사 선호
        'max_curb': 3,                  # 낮은 턱만 통과 가능
        'allow_stairs': False,          # 무릎 관절 보호를 위해 계단 회피
        'require_low_floor_bus': False, # 일반버스도 시간이 있으면 탑승 가능
        'weights': {
            'time_per_min': 1.2,        # 이동 시간에 대한 체력 부담이 큼
            'walk_dist_per_m': 0.05,    # 긴 보행 거리를 유모차보다 부담스러워함
            'transfer_penalty': 25.0,   # 환승할 때 이동하는 것을 매우 싫어함
            'elevator_bonus': -12.0,    # 계단 대신 엘리베이터 필수 선호
            'low_bus_bonus': -5.0
        }
    }
}


# ==============================================================================
# 3. 안전 검사 함수 (check_hard_barrier)
#    - 목적: 사용자가 지나갈 수 없는 위험한 길인지 확인하는 '문지기' 역할
#    - 반환: 위험 요소가 있으면 '이유(문자열)', 안전하면 'None' 반환
# ==============================================================================
def check_hard_barrier(edge, config):
    # 1. 계단 검사
    if not config['allow_stairs'] and edge['has_stairs']:
        return "계단 구간"
    
    # 2. 경사도 검사
    if edge['incline'] >= config['max_incline']:
        return f"기준 초과 경사({edge['incline']}% >= {config['max_incline']}%)"
    
    # 3. 보도 턱 높이 검사
    if edge['curb_height'] > config['max_curb']:
        return f"높은 보도 턱({edge['curb_height']}cm)"
    
    # 4. 저상버스 필수 여부 검사
    if config['require_low_floor_bus'] and edge['type'] == 'bus' and not edge['is_low_floor_bus']:
        return "휠체어 탑승 불가능한 일반버스"
    
    # 아무 문제도 없으면 통과
    return None


# ==============================================================================
# 4. 불편함 점수 계산 함수 (calculate_score)
#    - 목적: 안전검사를 통과한 길에 대해 얼마나 '불편한지' 점수로 환산
#    - 점수가 낮을수록 쾌적하고 좋은 길!
# ==============================================================================
def calculate_score(edge, weights):
    cost = 0.0
    
    # 기본 소요 시간 및 보행 거리 비용 계산
    cost += edge['travel_time_min'] * weights['time_per_min']
    cost += edge['walk_distance_m'] * weights['walk_dist_per_m']
    
    # 특수 조건에 따른 패널티(+) 및 보너스(-) 적용
    if edge['is_transfer']:
        cost += weights['transfer_penalty']  # 환승 부담 패널티 추가
    if edge['has_elevator']:
        cost += weights['elevator_bonus']    # 엘리베이터가 있으면 점수 할인
    if edge['is_low_floor_bus']:
        cost += weights['low_bus_bonus']     # 저상버스이면 점수 할인
        
    # 점수가 0 이하로 떨어지는 것을 방지 (최소 0.1점 보장)
    return max(cost, 0.1)


# ==============================================================================
# 5. 최적 경로 탐색 함수 (find_optimal_route)
#    - 다익스트라(Dijkstra) 알고리즘을 사용해 가장 점수가 낮은 경로를 탐색
# ==============================================================================
def find_optimal_route(graph, start, end, user_type):
    config = USER_CONFIGS[user_type]
    weights = config['weights']
    
    # 우선순위 큐(Priority Queue) 초기화
    # 튜플 구조: (현재 누적 점수, 현재 노드 위치, 지나온 경로 리스트, 누적 시간, 누적 보행거리)
    pq = [(0.0, start, [start], 0, 0)]
    
    # 각 노드까지 가는 데 걸리는 최소 점수 기록용 딕셔너리 (초기값은 무한대 float('inf'))
    best_scores = {node: float('inf') for node in graph}
    best_scores[start] = 0.0
    
    # 회피한 위험 요소들의 이유를 담아둘 세트(중복 제거용)
    avoided_reasons = set()

    while pq:
        # 힙(heap)에서 지금까지 점수가 가장 낮은 길을 우선적으로 꺼냄
        current_score, current, path, total_time, total_walk = heapq.heappop(pq)

        # 이미 계산된 더 좋은(점수가 낮은) 경로가 기록되어 있다면 이 탐색은 건너뜀
        if current_score > best_scores[current]:
            continue

        # 목적지(end)에 도착했다면 탐색 종료 및 최종 결과 반환
        if current == end:
            return {
                'score': round(current_score, 2),
                'path': path,
                'total_time_min': total_time,
                'total_walk_m': total_walk,
                'avoided_reasons': list(avoided_reasons)
            }

        # 현재 노드에서 갈 수 있는 모든 다음 길(edge)을 확인
        for edge in graph[current]:
            next_node = edge['to']
            
            # [1단계] 안전 검사 (Hard Barrier Check)
            barrier = check_hard_barrier(edge, config)
            if barrier:
                avoided_reasons.add(barrier) # 탈락한 이유를 기록에 남김
                continue                     # 위험한 길이면 탐색 중단하고 다음 길로 넘어가기

            # [2단계] 점수 계산 (Soft Scoring)
            edge_score = calculate_score(edge, weights)
            new_score = current_score + edge_score
            
            new_time = total_time + edge['travel_time_min']
            new_walk = total_walk + edge['walk_distance_m']

            # [3단계] 더 좋은 경로 발견 시 최적 점수 갱신 및 큐에 등록
            if new_score < best_scores[next_node]:
                best_scores[next_node] = new_score
                heapq.heappush(pq, (new_score, next_node, path + [next_node], new_time, new_walk))

    # 출발지에서 목적지까지 도달 가능한 경로가 없을 때
    return None


# ==============================================================================
# 6. 코드 직접 실행부
#    - python test_route.py 로 실행했을 때 동작하는 코드
# ==============================================================================
if __name__ == "__main__":
    start_node = 'A_출발지'
    end_node = 'F_도착지'

    print("\n==========================================================")
    print(" ♿ 배리어 프리 길찾기 알고리즘 결과 출력")
    print("==========================================================\n")

    # 4가지 사용자 유형에 대해 각각 경로 계산 실행
    for user_key, config in USER_CONFIGS.items():
        result = find_optimal_route(sample_map, start_node, end_node, user_key)
        
        print(f"[{config['name']}]")
        if result:
            route_str = " ➔ ".join(result['path'])
            avoided_str = ", ".join(result['avoided_reasons']) if result['avoided_reasons'] else "없음"
            print(f"  • 추천 경로: {route_str}")
            print(f"  • 소요 시간: {result['total_time_min']}분 | 보행 거리: {result['total_walk_m']}m")
            print(f"  • 회피 요소: [{avoided_str}]")
            print()
        else:
            print("  • 안전하게 이동 가능한 경로가 없습니다.\n")