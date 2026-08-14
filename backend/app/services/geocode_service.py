import os
from typing import List, Tuple

import httpx
from dotenv import load_dotenv

from app.schemas.response import LocationPoint


load_dotenv()


class GeocodeService:
    """카카오 지도 API를 활용한 주소 및 장소명 → 좌표 변환 서비스"""

    def __init__(self):
        self.kakao_api_key = os.getenv("KAKAO_REST_API_KEY")
        self.keyword_url = (
            "https://dapi.kakao.com/v2/local/search/keyword.json"
        )
        self.address_url = (
            "https://dapi.kakao.com/v2/local/search/address.json"
        )

    async def search_address(self, address: str) -> List[LocationPoint]:
        """도로명/지번 주소를 입력받아 좌표로 변환"""

        if not self.kakao_api_key:
            raise RuntimeError(
                "KAKAO_REST_API_KEY가 없습니다. backend/.env 파일을 확인하세요."
            )

        headers = {
            "Authorization": f"KakaoAK {self.kakao_api_key}"
        }
        params = {
            "query": address
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                self.address_url,
                headers=headers,
                params=params,
            )

        if response.status_code != 200:
            print(
                f"[Kakao Address API 오류] "
                f"Status Code: {response.status_code}, "
                f"Body: {response.text}"
            )
            return []

        data = response.json()
        documents = data.get("documents", [])
        results = []

        for doc in documents:
            address_info = doc.get("address") or {}
            road_address_info = doc.get("road_address") or {}

            display_name = (
                road_address_info.get("building_name")
                or doc.get("address_name")
                or address
            )

            results.append(
                LocationPoint(
                    name=display_name,
                    longitude=float(doc.get("x", 0.0)),
                    latitude=float(doc.get("y", 0.0)),
                    address=address_info.get("address_name"),
                    road_address=road_address_info.get("address_name"),
                )
            )

        return results

    async def search_keyword(self, query: str) -> List[LocationPoint]:
        """장소명/키워드를 입력받아 좌표로 변환"""

        if not self.kakao_api_key:
            raise RuntimeError(
                "KAKAO_REST_API_KEY가 없습니다. backend/.env 파일을 확인하세요."
            )

        headers = {
            "Authorization": f"KakaoAK {self.kakao_api_key}"
        }
        params = {
            "query": query
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                self.keyword_url,
                headers=headers,
                params=params,
            )

        if response.status_code != 200:
            print(
                f"[Kakao Keyword API 오류] "
                f"Status Code: {response.status_code}, "
                f"Body: {response.text}"
            )
            return []

        data = response.json()
        documents = data.get("documents", [])
        results = []

        for doc in documents:
            results.append(
                LocationPoint(
                    name=doc.get("place_name", query),
                    latitude=float(doc.get("y", 0.0)),
                    longitude=float(doc.get("x", 0.0)),
                    address=doc.get("address_name"),
                    road_address=doc.get("road_address_name"),
                )
            )

        return results

    async def search_auto(
        self,
        query: str,
    ) -> Tuple[str, List[LocationPoint]]:
        """
        주소 검색을 우선 시도하고,
        결과가 없으면 장소명 검색으로 전환합니다.
        """

        address_results = await self.search_address(query)

        if address_results:
            return "ADDRESS", address_results

        keyword_results = await self.search_keyword(query)

        return "KEYWORD", keyword_results