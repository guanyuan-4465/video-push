from queue import Queue, Empty
from dataclasses import dataclass, field
from src.core.services.process_pool import get_process_pool
from datetime import datetime
from typing import Optional, Dict, List, Callable
import asyncio
import uuid
from src.utils.log import logger
import json
from pathlib import Path
import time
from concurrent.futures import TimeoutError
import threading

@dataclass
class UploadTask:
    """上传任务数据类"""
    id: str  # 任务唯一标识
    platform: str  # 平台
    content_path: str  # 内容路径
    schedule_time: datetime  # 计划执行时间
    created_at: datetime = field(default_factory=datetime.now)  # 创建时间
    status: str = 'pending'  # 任务状态: pending, ready, running, completed, failed
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    
    @classmethod
    def create(cls, platform: str, content_path: str, schedule_time: Optional[datetime] = None) -> 'UploadTask':
        """创建新任务"""
        # 如果没有指定计划时间，则立即执行
        if schedule_time is None:
            schedule_time = datetime.now()
            
        return cls(
            id=str(uuid.uuid4()),
            platform=platform,
            content_path=content_path,
            schedule_time=schedule_time,
            created_at=datetime.now()
        )

    def can_retry(self) -> bool:
        return self.status == 'failed' and self.retry_count < self.max_retries

@dataclass
class UploadTaskData:
    """可序列化的任务数据"""
    platform: str
    content_path: str
    cookie_path: str
    content: dict

class TaskQueue:
    """任务队列管理"""
    def __init__(self):
        self.task_queue = Queue()  # 普通队列即可
        self.tasks = {}
        self._running = False
        self.status_callbacks = []
        self._load_tasks()  # 加载持久化的任务
        
    def _save_tasks(self):
        """保存任务到文件"""
        try:
            tasks_data = [
                {
                    'id': task.id,
                    'platform': task.platform,
                    'content_path': task.content_path,
                    'schedule_time': task.schedule_time.isoformat(),
                    'status': task.status,
                    'created_at': task.created_at.isoformat(),
                    'error': task.error
                }
                for task in self.tasks.values()
            ]
            
            with open('tasks.json', 'w', encoding='utf-8') as f:
                json.dump(tasks_data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"保存任务失败: {e}")
        
    def add_task(self, task: UploadTask) -> bool:
        try:
            # 检查是否为过期任务
            if datetime.now() >= task.schedule_time:
                task.status = 'ready'  # 直接标记为就绪
            
            # 根据计划时间和创建时间排序
            task_priority = (task.schedule_time, task.created_at)
            self.task_queue.put((task_priority, task))
            self.tasks[task.id] = task
            self._save_tasks()
            self._notify_status_change(task.id, task.status)
            return True
        except Exception as e:
            logger.error(f"添加任务失败: {e}")
            return False
            
    def get_task_status(self, task_id: str) -> Optional[str]:
        """获取任务状态"""
        task = self.tasks.get(task_id)
        return task.status if task else None
        
    def get_all_tasks(self) -> List[UploadTask]:
        """获取所有任务"""
        return list(self.tasks.values())
        
    def get_pending_tasks(self) -> List[UploadTask]:
        """获取待执行的任务"""
        return [task for task in self.tasks.values() if task.status == 'pending']
        
    def start(self):
        """启动任务处理"""
        if self._running:
            return
        
        try:
            self._running = True
            logger.info("任务队列处理器启动中...")
            
            # 使用新线程处理任务
            self._process_thread = threading.Thread(target=self._process_tasks)
            self._process_thread.daemon = True  # 设为守护线程
            self._process_thread.start()
            
        except Exception as e:
            self._running = False
            logger.error(f"任务队列启动失败: {e}")
        
    def stop(self):
        """停止任务处理"""
        self._running = False
        logger.info("任务队列处理器已停止")
        
    def _process_tasks(self):
        """处理任务队列"""
        while self._running:
            try:
                # 检查所有任务的状态
                current_time = datetime.now()
                ready_tasks = []
                
                # 遍历所有任务检查状态
                for task_id, task in list(self.tasks.items()):
                    if task.status == 'pending' and current_time >= task.schedule_time:
                        task.status = 'ready'
                        ready_tasks.append(task)
                        self._notify_status_change(task.id, task.status)
                    elif task.status == 'ready':
                        ready_tasks.append(task)

                # 处理就绪的任务
                if ready_tasks:
                    logger.info(f"发现 {len(ready_tasks)} 个待处理任务")
                    process_pool = get_process_pool()
                    if not process_pool:
                        logger.error("进程池未初始化")
                        time.sleep(5)
                        continue

                    for task in ready_tasks[:3]:  # 每次最多处理3个任务
                        try:
                            task.status = 'running'
                            self._notify_status_change(task.id, task.status)
                            logger.info(f"开始处理任务: {task.id} - {task.platform}")
                            
                            # 提交任务到进程池
                            future = self._submit_task(task)
                            
                            # 等待任务完成
                            try:
                                success = future.get(timeout=300)  # 5分钟超时
                                task.status = 'completed' if success else 'failed'
                                if not success:
                                    task.error = "上传失败"
                            except Exception as e:
                                task.status = 'failed'
                                task.error = str(e)
                                logger.error(f"任务执行失败: {e}")
                                
                            self._notify_status_change(task.id, task.status)
                            self._save_tasks()
                            
                        except Exception as e:
                            logger.error(f"处理任务 {task.id} 时出错: {e}")
                            task.status = 'failed'
                            task.error = str(e)
                            self._notify_status_change(task.id, task.status)
                            self._save_tasks()

                time.sleep(5)  # 每5秒检查一次任务状态
                
            except Exception as e:
                logger.error(f"任务处理循环出错: {e}")
                time.sleep(5)
                
    def _submit_task(self, task: UploadTask):
        """提交任务到进程池"""
        try:
            process_pool = get_process_pool()
            if not process_pool:
                raise RuntimeError("进程池未初始化")
                
            # 获取平台配置
            from src.config.base_config import ConfigManager
            config = ConfigManager().config
            if not config:
                raise ValueError("无法获取配置")
                
            platform_config = config.get_platform_config(task.platform)
            if not platform_config:
                raise ValueError(f"未找到平台配置: {task.platform}")
                
            cookie_path = platform_config.get('cookie_path')
            if not cookie_path or not Path(cookie_path).exists():
                raise ValueError(f"Cookie文件不存在: {cookie_path}")
                
            # 扫描内容目录
            content_path = Path(task.content_path)
            logger.info(f"开始扫描内容目录: {content_path}")
            
            # 检查目录是否存在
            if not content_path.exists():
                raise ValueError(f"内容目录不存在: {content_path}")
                
            # 列出目录内容
            logger.info(f"目录内容: {[f.name for f in content_path.iterdir()]}")
            
            # 扫描内容
            content = self._scan_content(content_path)
            if not content:
                raise ValueError(f"无法扫描内容: {content_path}")
                
            # 创建可序列化的任务数据
            task_data = UploadTaskData(
                platform=task.platform,
                content_path=task.content_path,
                cookie_path=cookie_path,
                content=content
            )
            
            # 提交任务到进程池
            return process_pool.apply_async(
                self._execute_task_in_process,
                (task_data,)
            )
            
        except Exception as e:
            logger.error(f"提交任务失败: {e}")
            raise

    def _execute_task_in_process(self, task_data: UploadTaskData) -> bool:
        """在独立进程中执行任务"""
        try:
            # 验证任务数据
            if not task_data.platform or not task_data.content_path or not task_data.cookie_path:
                raise ValueError("任务数据不完整")
            
            if not Path(task_data.content_path).exists():
                raise ValueError(f"内容路径不存在: {task_data.content_path}")
            
            if not Path(task_data.cookie_path).exists():
                raise ValueError(f"Cookie文件不存在: {task_data.cookie_path}")
            
            from src.core.services.upload_service import UploadService
            
            # 创建上传服务
            upload_service = UploadService()
            
            # 注册对应平台的上传器
            if task_data.platform == 'douyin':
                from src.core.uploaders.douyin import DouyinUploader
                upload_service.register_uploader('douyin', DouyinUploader)
            elif task_data.platform == 'xiaohongshu':
                from src.core.uploaders.xiaohongshu import XiaohongshuUploader
                upload_service.register_uploader('xiaohongshu', XiaohongshuUploader)
            
            # 执行上传
            return asyncio.run(upload_service.upload_content(
                platform=task_data.platform,
                content=task_data.content,
                cookie_path=task_data.cookie_path
            ))
            
        except Exception as e:
            logger.error(f"任务执行失败: {e}")
            return False

    def _load_tasks(self):
        """从文件加载任务"""
        try:
            if not Path('tasks.json').exists():
                logger.info("任务文件不存在，跳过加载")
                return
            
            with open('tasks.json', 'r', encoding='utf-8') as f:
                tasks_data = json.load(f)
            
            for task_data in tasks_data:
                task = UploadTask(
                    id=task_data['id'],
                    platform=task_data['platform'],
                    content_path=task_data['content_path'],
                    schedule_time=datetime.fromisoformat(task_data['schedule_time']),
                    status=task_data['status'],
                    created_at=datetime.fromisoformat(task_data['created_at']),
                    error=task_data['error']
                )
                self.tasks[task.id] = task
                if task.status == 'pending':
                    self.task_queue.put((task.schedule_time, task))
                
            logger.info(f"已加载 {len(tasks_data)} 个任务")
            
        except Exception as e:
            logger.error(f"加载任务失败: {e}")

    def clear_completed_tasks(self):
        """清理已完成的任务"""
        completed_tasks = [
            task_id for task_id, task in self.tasks.items()
            if task.status in ['completed', 'failed']
        ]
        
        for task_id in completed_tasks:
            del self.tasks[task_id]
        
        self._save_tasks()
        logger.info(f"已清理 {len(completed_tasks)} 个已完成任务")

    def add_status_callback(self, callback: Callable[[str, str], None]):
        """添加状态变更回调"""
        self.status_callbacks.append(callback)
        
    def _notify_status_change(self, task_id: str, new_status: str):
        """通知状态变更"""
        try:
            logger.info(f"任务 {task_id} 状态变更为: {new_status}")
            for callback in self.status_callbacks:
                try:
                    callback(task_id, new_status)
                except Exception as e:
                    logger.error(f"状态通知回调执行失败: {e}")
        except Exception as e:
            logger.error(f"通知状态变更失败: {e}")

    def _scan_content(self, content_path: Path) -> dict:
        """扫描内容目录，获取视频、封面和描述文件"""
        try:
            if not content_path.exists():
                raise ValueError(f"内容目录不存在: {content_path}")
            
            # 查找视频文件
            video_files = list(content_path.glob("*.mp4"))
            if not video_files:
                raise ValueError(f"未找到视频文件: {content_path}")
            
            # 查找封面图片
            cover_files = list(content_path.glob("*.jpg")) + list(content_path.glob("*.png"))
            if not cover_files:
                raise ValueError(f"未找到封面图片: {content_path}")
            
            # 查找描述文件 - 更灵活地查找 .txt 文件
            txt_files = list(content_path.glob("*.txt"))
            if not txt_files:
                raise ValueError(f"未找到描述文件: {content_path}")
            
            # 读取描述内容
            desc_file = txt_files[0]  # 使用找到的第一个 .txt 文件
            logger.info(f"使用描述文件: {desc_file}")
            
            try:
                with open(desc_file, "r", encoding="utf-8") as f:
                    desc_lines = f.readlines()
                    title = desc_lines[0].strip() if desc_lines else ""
                    tags = []
                    if len(desc_lines) > 1:
                        tags = [tag.strip() for tag in desc_lines[1].split("#") if tag.strip()]
            except UnicodeDecodeError:
                # 如果 UTF-8 解码失败，尝试其他编码
                with open(desc_file, "r", encoding="gbk") as f:
                    desc_lines = f.readlines()
                    title = desc_lines[0].strip() if desc_lines else ""
                    tags = []
                    if len(desc_lines) > 1:
                        tags = [tag.strip() for tag in desc_lines[1].split("#") if tag.strip()]
            
            # 记录找到的文件信息
            video_file = video_files[0]
            cover_file = cover_files[0]
            logger.info(f"找到文件: 视频={video_file.name}, 封面={cover_file.name}, 描述={desc_file.name}")
            
            return {
                "video": str(video_file),
                "cover": str(cover_file),
                "title": title,
                "tags": tags,
                "desc_file": str(desc_file)  # 添加描述文件路径
            }
            
        except Exception as e:
            logger.error(f"扫描内容失败: {e}")
            return None