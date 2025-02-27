from src.core.services.upload_service import UploadService
from src.core.services.cookie_service import CookieService
from src.core.services.task_queue import TaskQueue, UploadTask
from src.core.uploaders.douyin import DouyinUploader
from src.core.uploaders.xiaohongshu import XiaohongshuUploader
from src.utils.log import logger
from pathlib import Path
from src.config.base_config import ConfigManager
from datetime import datetime
from typing import Optional, List, Dict
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

    def _scan_content(self, content_dir: Path) -> List[Dict]:
        """扫描内容目录，返回内容信息列表"""
        try:
            if not content_dir.exists():
                raise ValueError(f"目录不存在: {content_dir}")
            
            # 重新获取最新的配置
            batch_enabled = self.config_manager.config.batch_enabled
            logger.info(f"当前批量模式状态: {batch_enabled}")
            
            # 检查是否为批量模式
            if batch_enabled:
                logger.info(f"批量模式：扫描子目录 {content_dir}")
                # 批量模式：扫描所有子目录
                contents = []
                sub_dirs = [d for d in content_dir.iterdir() if d.is_dir()]
                
                if not sub_dirs:
                    logger.error(f"批量模式下目录为空或没有子目录: {content_dir}")
                    raise ValueError(f"批量模式下目录为空或没有子目录: {content_dir}")
                    
                logger.info(f"找到 {len(sub_dirs)} 个子目录: {[d.name for d in sub_dirs]}")
                
                for sub_dir in sub_dirs:
                    try:
                        content = self._scan_single_dir(sub_dir)
                        if content:
                            contents.append(content)
                            logger.info(f"成功扫描子目录: {sub_dir.name}")
                    except Exception as e:
                        logger.warning(f"扫描子目录 {sub_dir} 失败: {e}")
                
                if not contents:
                    raise ValueError("没有找到有效的内容")
                    
                logger.info(f"批量模式共扫描到 {len(contents)} 个有效内容")
                return contents
            else:
                # 单个模式：直接扫描目录
                logger.info(f"单个模式：直接扫描目录 {content_dir}")
                content = self._scan_single_dir(content_dir)
                return [content] if content else []
            
        except Exception as e:
            logger.error(f"扫描内容失败: {e}")
            raise

    def _scan_single_dir(self, directory: Path) -> Dict:
        """扫描单个目录的内容"""
        logger.info(f"扫描目录: {directory}")
        
        # 查找媒体文件
        video_files = list(directory.glob("*.mp4"))
        image_files = list(directory.glob("*.jpg")) + list(directory.glob("*.png"))
        
        # 查找描述文件
        desc_files = list(directory.glob("*.txt"))
        if not desc_files:
            raise ValueError(f"未找到描述文件: {directory}")
        
        # 读取描述文件
        with open(desc_files[0], 'r', encoding='utf-8') as f:
            desc_lines = f.readlines()
        
        title = desc_lines[0].strip() if desc_lines else ""
        tags = []
        if len(desc_lines) > 1:
            tags = [tag.strip() for tag in desc_lines[1:] if tag.strip().startswith('#')]
        
        # 构建内容信息
        content = {
            'title': title,
            'tags': tags,
            'desc_file': str(desc_files[0])
        }
        
        if video_files:
            content['type'] = 'video'
            content['video'] = str(video_files[0])
            logger.info(f"找到视频文件: {video_files[0].name}")
        elif image_files:
            content['type'] = 'image'
            content['images'] = [str(img) for img in image_files]
            logger.info(f"找到图片文件: {[img.name for img in image_files]}")
        else:
            raise ValueError(f"未找到媒体文件: {directory}")
        
        logger.info(f"成功扫描目录 {directory.name}: {content['type']}, 标题: {title}")
        return content

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
