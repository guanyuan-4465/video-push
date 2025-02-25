from pathlib import Path
from typing import List

from conf import BASE_DIR

SOCIAL_MEDIA_DOUYIN = "douyin"
SOCIAL_MEDIA_XHS = "xiaohongshu"


def get_supported_social_media() -> List[str]:
    return [SOCIAL_MEDIA_DOUYIN, SOCIAL_MEDIA_XHS]


def get_cli_action() -> List[str]:
    return ["upload", "login", "watch"]


async def set_init_script(context):
    stealth_js_path = Path(BASE_DIR / "src" / "utils/stealth.min.js")
    await context.add_init_script(path=stealth_js_path)
    return context
