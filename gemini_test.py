import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types

# 1. .env 파일에 저장된 GEMINI_API_KEY 불러오기
load_dotenv()

# 2. Gemini 클라이언트 생성
client = genai.Client()

def generate_route_reason(route_data):
    # 시스템 프롬프트 (AI의 역할 및 규칙)
    system_instruction = """
    너는 교통약자(휠체어, 유모차, 고령자)를 위한 배리어 프리 길안내 앱의 AI 도우미야.
    알고리즘이 탐색한 경로 데이터를 바탕으로, 사용자 유형에게 이 경로가 왜 최적이고 안전한지 자연스러운 문장으로 설명해야 해.

    [가이드라인]
    1. 정중하고 친절한 존댓말(~해요, ~합니다)을 사용한다.
    2. 전문 용어 대신 직관적이고 쉬운 표현을 사용한다. (예: 경사도 2% -> 완만한 길)
    3. 글자 수는 100자 내외(2~3문장)로 핵심만 간결하게 작성한다.
    4. 인삿말이나 부연 설명 없이 '추천 이유 문장'만 단독 출력한다.
    """

    # Few-Shot 예시 + 실제 요청 데이터
    prompt = f"""
[예시 1]
입력: {{"user_type": "휠체어", "features": ["계단 0개", "경사도 완만", "엘리베이터 동선"]}}
출력: 계단이 전혀 없고 모든 경사가 완만하여 휠체어로도 직접 안전하게 이동하실 수 있습니다. 지하철 출구부터 목적지까지 엘리베이터로 연속 연결되는 가장 수월한 경로입니다.

[예시 2]
입력: {{"user_type": "고령자", "features": ["오르막 최소화", "에스컬레이터 이용"]}}
출력: 무릎에 부담을 주는 오르막길을 피하고, 에스컬레이터를 이용해 힘들이지 않고 천천히 이동하기 좋습니다.

[실제 요청]
입력: {json.dumps(route_data, ensure_ascii=False)}
출력:
    """

    # 3. Gemini 3.5 Flash 모델 호출
    response = client.models.generate_content(
        model='gemini-3.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.3,
        )
    )

    return response.text.strip()

# -------------------------------------------------------------
# 테스트 실행
# -------------------------------------------------------------
if __name__ == "__main__":
    # 지도 알고리즘에서 전달받은 예시 데이터
    sample_route = {
        "user_type": "유모차 동반자",
        "features": [
            "보도 폭 2.5m 이상으로 넓음",
            "길턱 없음(0cm)",
            "지하철 3번 출구 엘리베이터 연계",
            "횡단보도 신호 시간 여유"
        ]
    }

    print("Gemini가 추천 이유를 생성 중입니다...")
    reason = generate_route_reason(sample_route)
    print("\n[생성된 추천 이유]:")
    print(reason)