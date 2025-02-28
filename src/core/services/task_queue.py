from queue import Queue, Empty
from dataclasses import dataclass, field, asdict
from src.core.services.process_pool import get_process_pool
from datetime import datetime
from typing import Optional, Dict, List, Callable
import asyncio
import uuid
from src.utils.log import logger
import json
from pathlib import Path
import time
from concurrent.futures import TimeoutError, ProcessPoolExecutor
import threading
from PyQt6.QtCore import QMetaObject, Qt, Q_ARG, QVariant

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
    content: Optional[Dict] = None
    content_type: str = "video"  # 新增：内容类型标识
    
    @classmethod
    def create(cls, platform: str, content_path: str, schedule_time: Optional[datetime] = None) -> 'UploadTask':
        """创建新任务"""
        task = cls(
            id=str(uuid.uuid4()),
            platform=platform,
            content_path=content_path,
            schedule_time=schedule_time or datetime.now()
        )
        # 根据内容路径判断内容类型
        content_path = Path(content_path)
        if list(content_path.glob("*.mp4")):
            task.content_type = "video"
        elif list(content_path.glob("*.jpg")) or list(content_path.glob("*.png")):
            task.content_type = "image"
        return task

    def can_retry(self) -> bool:
        return self.status == 'failed' and self.retry_count < self.max_retries

@dataclass
class UploadTaskData:
    """上传任务数据"""
    platform: str
    content_path: str
    cookie_path: str
    content: Optional[Dict] = None
    title: str = ""
    thumbnail_path: Optional[str] = None
    image_paths: List[str] = field(default_factory=list)  # 新增：支持多图片路径
    tags: List[str] = field(default_factory=list)
    schedule_time: Optional[datetime] = None
    content_type: str = "video"  # 新增：内容类型标识
    platform_config: Optional[Dict] = None  # 添加平台配置字段
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'platform': self.platform,
            'content_path': self.content_path,
            'cookie_path': self.cookie_path,
            'content': self.content,
            'title': self.title,
            'thumbnail_path': self.thumbnail_path,
            'image_paths': self.image_paths,  # 新增
            'tags': self.tags,
            'schedule_time': self.schedule_time.isoformat() if self.schedule_time else None,
            'content_type': self.content_type,  # 新增
            'platform_config': self.platform_config  # 添加到字典转换中
        }
    
    @classmethod
    def from_dict(cls, data: Dict):
        """从字典创建实例"""
        if 'schedule_time' in data and data['schedule_time']:
            data['schedule_time'] = datetime.fromisoformat(data['schedule_time'])
        return cls(**data)

class TaskQueue:
    """任务队列管理"""
    def __init__(self):
        self.task_queue = Queue()
        self.tasks = {}
        self._running = False
        self.status_callbacks = []
        self.platform_last_exec = {
            'douyin': None,
            'xiaohongshu': None
        }  # 记录每个平台最后执行时间
        self.platform_intervals = {
            'douyin': 60,  # 抖音发布间隔1分钟
            'xiaohongshu': 60  # 小红书发布间隔1分钟
        }  # 平台发布间隔（秒）
        self._load_tasks()
        
        self.process_pool = get_process_pool()
        if self.process_pool is None:
            logger.warning("任务队列无法获取进程池，将使用线程池替代")
        
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
        
        self._running = True
        logger.info("任务队列处理器启动中...")
        
        # 创建并启动任务处理线程
        def run_tasks():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._process_tasks())
        
        self.task_thread = threading.Thread(target=run_tasks)
        self.task_thread.daemon = True
        self.task_thread.start()
        
    def stop(self):
        """停止任务处理"""
        self._running = False
        logger.info("任务队列处理器已停止")
        
    async def _process_tasks(self):
        """处理任务队列"""
        while self._running:
            try:
                current_time = datetime.now()
                # 按平台分组获取就绪任务
                platform_tasks = {
                    'douyin': [],
                    'xiaohongshu': []
                }
                
                # 遍历所有任务并按平台分组
                for task_id, task in list(self.tasks.items()):
                    if task.status == 'pending' and current_time >= task.schedule_time:
                        platform_tasks[task.platform].append(task)
                        task.status = 'ready'
                        self._notify_status_change(task.id, task.status)
                    elif task.status == 'ready':
                        platform_tasks[task.platform].append(task)

                # 并行处理不同平台的任务
                futures = []
                
                # 对每个平台单独处理
                for platform, tasks in platform_tasks.items():
                    if not tasks:
                        continue
                        
                    # 检查该平台的上次执行时间
                    last_exec = self.platform_last_exec.get(platform)
                    if last_exec:
                        elapsed = (current_time - last_exec).total_seconds()
                        if elapsed < self.platform_intervals[platform]:
                            logger.info(f"{platform} 平台任务间隔未到 ({elapsed:.0f}/{self.platform_intervals[platform]}秒)")
                            continue
                    
                    # 获取该平台的第一个任务
                    task = tasks[0]
                    task.status = 'running'
                    self._notify_status_change(task.id, task.status)
                    logger.info(f"开始处理 {platform} 平台任务: {task.id}")
                    
                    # 提交任务到进程池
                    future = self._submit_task(task)
                    futures.append((task, future, platform))

                # 等待当前批次的任务完成
                if futures:
                    for task, future, platform in futures:
                        try:
                            success = await asyncio.get_event_loop().run_in_executor(
                                None, future.result, 300
                            )
                            task.status = 'completed' if success else 'failed'
                            if success:
                                # 仅更新成功完成任务的平台最后执行时间
                                self.platform_last_exec[platform] = datetime.now()
                                logger.info(f"{platform} 平台任务完成，更新最后执行时间")
                            else:
                                task.error = "上传失败"
                        except Exception as e:
                            task.status = 'failed'
                            task.error = str(e)
                            logger.error(f"任务执行失败: {e}")
                        finally:
                            self._notify_status_change(task.id, task.status)
                            self._save_tasks()

                # 短暂休眠避免CPU占用过高
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"任务处理循环出错: {e}")
                await asyncio.sleep(5)
                
    def _submit_task(self, task: UploadTask):
        """提交任务到进程池"""
        try:
            if not self.process_pool:
                raise RuntimeError("进程池未初始化")
                
            # 获取平台配置
            from src.config.base_config import ConfigManager
            config = ConfigManager().config
            if not config:
                raise ValueError("无法获取配置")
                
            platform_config = config.get_platform_config(task.platform)
            logger.info(f"任务提交时的平台配置: {platform_config}")  # 添加日志
            if not platform_config:
                raise ValueError(f"未找到平台配置: {task.platform}")
                
            cookie_path = platform_config.get('cookie_path')
            logger.info(f"获取到的 cookie_path: {cookie_path}")  # 添加日志
            if not cookie_path or not Path(cookie_path).exists():
                raise ValueError(f"Cookie文件不存在: {cookie_path}")
                
            # 如果任务已经包含内容信息，直接使用
            content = task.content if task.content else self._scan_content(Path(task.content_path))
            if not content:
                raise ValueError(f"无法获取内容: {task.content_path}")
            
            # 创建可序列化的任务数据
            task_data = UploadTaskData(
                platform=task.platform,
                content_path=str(task.content_path),  # 确保是字符串
                cookie_path=str(cookie_path),    # 确保是字符串
                content=content,
                platform_config=platform_config  # 添加平台配置
            )
            logger.info(f"创建的任务数据: {task_data.to_dict()}")  # 添加日志
            # 提交任务到进程池
            logger.info(f"提交任务到进程池: {task.id}")
            return self.process_pool.submit(self._execute_task_in_process, task_data.to_dict())
            
        except Exception as e:
            logger.error(f"提交任务失败: {e}")
            raise

    @staticmethod
    def _execute_task_in_process(task_data_dict):
        """在独立进程中执行任务"""
        try:
            # 从字典重建任务数据
            from src.core.services.task_queue import UploadTaskData
            task_data = UploadTaskData.from_dict(task_data_dict)
            
            # 验证任务数据
            if not task_data.platform or not task_data.content_path or not task_data.cookie_path:
                raise ValueError("任务数据不完整")
            
            if not Path(task_data.content_path).exists():
                raise ValueError(f"内容路径不存在: {task_data.content_path}")
            
            if not Path(task_data.cookie_path).exists():
                raise ValueError(f"Cookie文件不存在: {task_data.cookie_path}")
            
            # 导入必要的模块
            from src.core.services.upload_service import UploadService
            import asyncio
            from playwright.async_api import async_playwright
            
            # 创建上传服务
            upload_service = UploadService()
            
            # 注册对应平台的上传器
            if task_data.platform == 'douyin':
                from src.core.uploaders.douyin import DouyinUploader
                upload_service.register_uploader('douyin', DouyinUploader)
            elif task_data.platform == 'xiaohongshu':
                from src.core.uploaders.xiaohongshu import XiaohongshuUploader
                upload_service.register_uploader('xiaohongshu', XiaohongshuUploader)
            
            # 定义异步上传函数
            async def run_upload():
                try:
                    # 在进程内创建 playwright 对象
                    async with async_playwright() as playwright:
                        # 执行上传
                        result = await upload_service.upload_content(
                            platform=task_data.platform,
                            content=task_data.content,
                            cookie_path=task_data.cookie_path,
                            platform_config=task_data.platform_config,  # 添加这行
                            playwright=playwright  # 传递 playwright 对象
                        )
                        return result
                except Exception as e:
                    logger.error(f"上传过程中出错: {e}")
                    return False
            
            # 运行异步函数
            return asyncio.run(run_upload())
            
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
            task = self.tasks.get(task_id)
            if not task:
                logger.warning(f"未找到任务 {task_id}")
                return

            # 安全地获取内容类型
            content_type = "未知"
            if hasattr(task, 'content') and task.content:
                content_type = "视频" if task.content.get('video') else "图文"
            elif hasattr(task, 'content_type'):
                content_type = task.content_type

            status_desc = {
                'pending': '等待中',
                'ready': '准备上传',
                'running': f'正在上传{content_type}内容',
                'completed': f'{content_type}上传完成',
                'failed': f'{content_type}上传失败'
            }.get(new_status, new_status)

            logger.info(f"任务 {task_id} ({content_type}) 状态变更为: {status_desc}")
            
            # 如果是失败状态，记录错误信息
            if new_status == 'failed' and hasattr(task, 'error'):
                logger.error(f"任务失败原因: {task.error}")

            # 通知所有回调
            for callback in self.status_callbacks:
                try:
                    callback(task_id, new_status)
                except Exception as e:
                    logger.error(f"状态通知回调执行失败: {e}")
                
        except Exception as e:
            logger.error(f"通知状态变更失败: {e}")

    def _scan_content(self, content_path: Path) -> dict:
        """扫描内容目录，获取视频/图片和描述文件"""
        try:
            if not content_path.exists():
                raise ValueError(f"内容目录不存在: {content_path}")
            
            # 查找媒体文件
            video_files = list(content_path.glob("*.mp4"))
            image_files = list(content_path.glob("*.jpg")) + list(content_path.glob("*.png"))
            
            # 查找描述文件
            txt_files = list(content_path.glob("*.txt"))
            if not txt_files:
                raise ValueError(f"未找到描述文件: {content_path}")
            
            # 读取描述内容
            desc_file = txt_files[0]
            logger.info(f"使用描述文件: {desc_file}")
            
            try:
                with open(desc_file, "r", encoding="utf-8") as f:
                    desc_lines = f.readlines()
                    title = desc_lines[0].strip() if desc_lines else ""
                    tags = []
                    if len(desc_lines) > 1:
                        tags = [tag.strip() for tag in desc_lines[1].split("#") if tag.strip()]
            except UnicodeDecodeError:
                with open(desc_file, "r", encoding="gbk") as f:
                    desc_lines = f.readlines()
                    title = desc_lines[0].strip() if desc_lines else ""
                    tags = []
                    if len(desc_lines) > 1:
                        tags = [tag.strip() for tag in desc_lines[1].split("#") if tag.strip()]
            
            # 构建返回内容
            content = {
                "title": title,
                "tags": tags,
                "desc_file": str(desc_file)
            }
            
            # 根据文件类型构建不同的内容
            if video_files:
                # 视频模式
                content["video"] = str(video_files[0])
                # 查找对应的封面图片
                cover_files = [f for f in image_files if f.stem == video_files[0].stem]
                if cover_files:
                    content["cover"] = str(cover_files[0])
                logger.info(f"找到视频文件: 视频={video_files[0].name}, " + 
                           f"封面={cover_files[0].name if cover_files else '无'}")
            elif image_files:
                # 图文模式
                content["images"] = [str(f) for f in image_files]
                logger.info(f"找到图片文件: {[f.name for f in image_files]}")
            else:
                raise ValueError(f"未找到媒体文件(视频或图片): {content_path}")
            
            return content
            
        except Exception as e:
            logger.error(f"扫描内容失败: {e}")
            return None

    def _execute_task_in_main_thread(self, task_data):
        """在主线程中执行任务，避免Qt线程问题"""
        # 检查是否存在主窗口实例
        if hasattr(self, 'main_window') and self.main_window:
            # 使用Qt的跨线程调用机制
            QMetaObject.invokeMethod(
                self.main_window,
                "handle_task",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(QVariant, task_data)
            )
        else:
            # 如果没有主窗口，则直接在当前线程执行
            self._execute_task(task_data)