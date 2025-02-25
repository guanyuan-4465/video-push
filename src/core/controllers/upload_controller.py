from src.core.services.upload_service import UploadService
from src.core.services.cookie_service import CookieService
from src.core.services.task_queue import TaskQueue, UploadTask
from src.core.uploaders.douyin import DouyinUploader
from src.core.uploaders.xiaohongshu import XiaohongshuUploader
from src.utils.log import logger
from pathlib import Path
from src.config.base_config import ConfigManager
from datetime import datetime
from typing import Optional
import asyncio

class UploadController:
    def __init__(self):
        self.upload_service = UploadService()
        self.cookie_service = CookieService()
        self.config_manager = ConfigManager()
        self.task_queue = TaskQueue()
        self._register_uploaders()
        
    async def initialize(self):
        """初始化控制器"""
        await self.task_queue.start(self)
        
    async def shutdown(self):
        """关闭控制器"""
        await self.task_queue.stop()
    
    def schedule_upload(self, platform: str, content_dir: Path, schedule_time: datetime) -> bool:
        """调度上传任务"""
        try:
            # 创建新任务
            task = UploadTask.create(
                platform=platform,
                content_path=str(content_dir),
                schedule_time=schedule_time
            )
            
            # 添加到任务队列
            success = self.task_queue.add_task(task)
            if success:
                logger.info(f"已调度上传任务: {platform} - {schedule_time}")
            return success
            
        except Exception as e:
            logger.error(f"调度上传任务失败: {e}")
            return False
            
    def get_task_status(self, task_id: str) -> str:
        """获取任务状态"""
        return self.task_queue.get_task_status(task_id)
        
    def get_all_tasks(self):
        """获取所有任务"""
        return self.task_queue.get_all_tasks()
        
    def _register_uploaders(self):
        """注册所有上传器"""
        # 注册上传服务
        self.upload_service.register_uploader('douyin', DouyinUploader)
        self.upload_service.register_uploader('xiaohongshu', XiaohongshuUploader)
        
        # 注册cookie服务
        self.cookie_service.register_uploader('douyin', DouyinUploader)
        self.cookie_service.register_uploader('xiaohongshu', XiaohongshuUploader)
        
    async def validate_cookie(self, platform: str, cookie_path: str) -> bool:
        """验证cookie"""
        return await self.cookie_service.validate_cookie(platform, cookie_path)
        
    async def generate_cookie(self, platform: str, cookie_path: str) -> bool:
        """生成cookie"""
        return await self.cookie_service.generate_cookie(platform, cookie_path)
        
    async def upload_content(self, platform: str, content_dir: Path, schedule_time: Optional[datetime] = None) -> bool:
        """处理内容上传"""
        try:
            # 扫描内容
            content = self._scan_content(content_dir)
            if not content:
                return False

            # 创建任务（无论是否定时）
            task = UploadTask.create(
                platform=platform,
                content_path=str(content_dir),
                schedule_time=schedule_time or datetime.now()  # 如果不是定时，就立即执行
            )
            
            # 添加到任务队列
            return self.task_queue.add_task(task)
            
        except Exception as e:
            logger.error(f"创建上传任务失败: {e}")
            return False

    def _scan_content(self, content_dir: Path) -> dict:
        """扫描内容目录，返回内容信息"""
        try:
            # 检查目录是否存在
            if not content_dir.exists():
                raise ValueError(f"目录不存在: {content_dir}")
            
            # 查找视频文件
            video_files = list(content_dir.glob("*.mp4"))
            if not video_files:
                raise ValueError(f"未找到视频文件")
            
            # 查找封面图片
            cover_files = list(content_dir.glob("*.png"))
            
            # 查找描述文件
            desc_files = list(content_dir.glob("*.txt"))
            if not desc_files:
                raise ValueError(f"未找到描述文件")
            
            # 读取描述文件
            desc_content = desc_files[0].read_text(encoding='utf-8').strip()
            title, *tags = desc_content.split('\n')
            
            return {
                'video': str(video_files[0]),
                'cover': str(cover_files[0]) if cover_files else None,
                'title': title,
                'tags': [tag.strip('#') for tag in tags if tag.strip()]
            }
            
        except Exception as e:
            logger.error(f"扫描内容失败: {e}")
            return None

    async def pause_task(self, task_id: str) -> bool:
        """暂停任务"""
        task = self.task_queue.get_task(task_id)
        if task and task.status == 'pending':
            task.status = 'paused'
            return True
        return False
        
    async def resume_task(self, task_id: str) -> bool:
        """恢复任务"""
        task = self.task_queue.get_task(task_id)
        if task and task.status == 'paused':
            task.status = 'pending'
            return True
        return False
        
    async def retry_task(self, task_id: str) -> bool:
        """重试失败的任务"""
        task = self.task_queue.get_task(task_id)
        if task and task.can_retry():
            task.status = 'pending'
            task.retry_count += 1
            return True
        return False

    def upload_sync(self, platform: str, content_dir: Path) -> bool:
        """同步上传方法"""
        try:
            content = self._scan_content(content_dir)
            if not content:
                return False
            
            # 获取平台配置
            platform_config = self.config_manager.config.get_platform_config(platform)
            if not platform_config or not platform_config.get('cookie_path'):
                raise ValueError(f"未找到 {platform} 平台的配置或 cookie")
            
            # 使用 asyncio.run 执行异步上传
            return asyncio.run(self.upload_service.upload_content(
                platform=platform,
                content=content,
                cookie_path=platform_config['cookie_path']
            ))
            
        except Exception as e:
            logger.error(f"上传失败: {e}")
            return False
