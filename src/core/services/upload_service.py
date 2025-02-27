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
        location = kwargs.get('location', '')  # 添加地点参数
        
        return self._uploaders[platform](
            title=title,
            file_path=file_path,
            tags=tags,
            publish_date=publish_date,
            account_file=account_file,
            thumbnail_path=thumbnail_path,
            location=location  # 传递地点参数给上传器
        )
        
    async def upload_content(self, platform: str, content: Dict, cookie_path: str, platform_config: Dict = None, playwright=None) -> bool:
        """上传内容"""
        try:
            logger.info(f"接收到的参数: platform={platform}, platform_config={platform_config}")  # 添加日志

            # 判断内容类型
            content_type = "video" if content.get('video') else "image"
            logger.info(f"检测到内容类型: {content_type}")

            # 获取地点配置
            location = platform_config.get('location', '') if platform_config else ''
            logger.info(f"地点配置: {location if location else '未设置'}")

            if content_type == "video":
                # 视频上传
                if not content.get('video'):
                    raise ValueError("不支持的文件类型: 缺少视频文件")
                    
                uploader = self.get_uploader(
                    platform=platform,
                    title=content.get('title', ''),
                    file_path=content.get('video', ''),
                    tags=content.get('tags', []),
                    publish_date=None,  # 由任务队列控制定时
                    account_file=cookie_path,
                    thumbnail_path=content.get('cover'),
                    location=location  # 添加地点参数
                )
            else:
                # 图文上传
                if not content.get('images'):
                    raise ValueError("不支持的文件类型: 缺少图片文件")
                    
                uploader = self.get_uploader(
                    platform=platform,
                    title=content.get('title', ''),
                    file_path=content.get('images', [])[0],  # 使用第一张图片作为主图
                    tags=content.get('tags', []),
                    publish_date=None,
                    account_file=cookie_path,
                    image_paths=content.get('images', []),  # 传入所有图片路径
                    location=location  # 添加地点参数
                )
            
            # 执行上传
            if playwright:
                return await uploader.upload(playwright)
            else:
                async with async_playwright() as playwright:
                    return await uploader.upload(playwright)
                    
        except Exception as e:
            logger.error(f"上传失败: {str(e)}")
            raise 