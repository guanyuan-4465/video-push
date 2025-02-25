from typing import Dict
from playwright.async_api import async_playwright
from src.utils.log import logger
from src.core.uploaders.base import BaseUploader

class UploadService:
    def __init__(self):
        self._uploaders = {}  # 平台名称 -> 上传器类的映射
        
    def register_uploader(self, platform: str, uploader_class: type):
        """注册上传器"""
        self._uploaders[platform] = uploader_class
        
    def get_uploader(self, platform: str, **kwargs) -> BaseUploader:
        """获取上传器实例"""
        if platform not in self._uploaders:
            raise ValueError(f"不支持的平台: {platform}")
            
        # 从 kwargs 中提取必要参数
        title = kwargs.get('title', '')
        file_path = kwargs.get('file_path', '')
        tags = kwargs.get('tags', [])
        publish_date = kwargs.get('publish_date')
        account_file = kwargs.get('account_file', '')
        thumbnail_path = kwargs.get('thumbnail_path')
        
        return self._uploaders[platform](
            title=title,
            file_path=file_path,
            tags=tags,
            publish_date=publish_date,
            account_file=account_file,
            thumbnail_path=thumbnail_path
        )
        
    async def upload_content(self, platform: str, content: Dict, cookie_path: str) -> bool:
        """上传内容"""
        try:
            # 从 content 中获取必要信息
            uploader = self.get_uploader(
                platform=platform,
                title=content.get('title', ''),
                file_path=content.get('video', ''),
                tags=content.get('tags', []),
                publish_date=None,  # 暂不支持定时发布
                account_file=cookie_path,
                thumbnail_path=content.get('cover')
            )
            
            async with async_playwright() as playwright:
                return await uploader.upload(playwright)
                
        except Exception as e:
            logger.error(f"上传失败: {str(e)}")
            raise 