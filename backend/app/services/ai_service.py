"""Legacy compatibility module.

2차 프로토타입 F-09는 app.services.gemini_service와
app.api.reports에서 처리합니다. 이 파일은 과거 import가 남아 있을 때
ImportError가 나지 않도록 유지합니다.
"""

import logging

logger = logging.getLogger(__name__)


async def verify_report_image_with_ai(*args, **kwargs):
    logger.warning(
        "verify_report_image_with_ai()는 더 이상 사용하지 않습니다. "
        "Gemini 검증은 POST /api/v2/reports에서 처리됩니다."
    )
    return None
