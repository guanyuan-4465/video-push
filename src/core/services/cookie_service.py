from pathlib import Path
from typing import Optional
from src.utils.log import logger

class CookieService:
    def __init__(self):
        self._uploaders = {}  # 平台名称 -> 上传器类的映射
        
    def register_uploader(self, platform: str, uploader_class: type):
        """注册上传器"""
        self._uploaders[platform] = uploader_class
        
    async def validate_cookie(self, platform: str, cookie_path: str) -> bool:
        """验证指定平台的cookie是否有效"""
        try:
            uploader = self._uploaders[platform](
                title="",
                file_path="",
                tags=[],
                publish_date=None,
                account_file=cookie_path
            )
            return await uploader.validate_cookie()
        except Exception as e:
            logger.error(f"验证cookie失败: {str(e)}")
            return False
            
    async def generate_cookie(self, platform: str, cookie_path: str) -> bool:
        """生成新的cookie"""
        try:
            # 直接调用平台特定的cookie获取函数
            if platform == 'douyin':
                from src.core.uploaders.douyin import douyin_cookie_gen
                return await douyin_cookie_gen(cookie_path)
            elif platform == 'xiaohongshu':
                from src.core.uploaders.xiaohongshu import xhs_cookie_gen
                return await xhs_cookie_gen(cookie_path)
            else:
                raise ValueError(f"不支持的平台: {platform}")
            
        except Exception as e:
            logger.error(f"生成cookie失败: {str(e)}")
            return False 