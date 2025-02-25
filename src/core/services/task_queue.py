from queue import Queue
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, List, Callable
import asyncio
import uuid
from src.utils.log import logger
import json
from pathlib import Path

@dataclass
class UploadTask:
    """上传任务数据类"""
    id: str  # 任务唯一标识
    platform: str  # 平台
    content_path: str  # 内容路径
    schedule_time: datetime  # 计划执行时间
    status: str = 'pending'  # 任务状态: pending, running, completed, failed
    created_at: datetime = datetime.now()
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    
    @classmethod
    def create(cls, platform: str, content_path: str, schedule_time: datetime) -> 'UploadTask':
        """创建新任务"""
        return cls(
            id=str(uuid.uuid4()),
            platform=platform,
            content_path=content_path,
            schedule_time=schedule_time
        )

    def can_retry(self) -> bool:
        return self.status == 'failed' and self.retry_count < self.max_retries

class TaskQueue:
    """任务队列管理"""
    def __init__(self):
        self.task_queue = Queue()
        self.tasks = {}  # 任务字典,用于状态跟踪
        self._running = False
        self._worker = None
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
        """添加任务到队列"""
        try:
            self.task_queue.put(task)
            self.tasks[task.id] = task
            logger.info(f"任务已添加到队列: {task.id}")
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
        
    async def start(self, upload_controller):
        """启动任务队列处理"""
        if self._running:
            return
            
        self._running = True
        self._worker = asyncio.create_task(self._process_tasks(upload_controller))
        logger.info("任务队列处理器已启动")
        
    async def stop(self):
        """停止任务队列处理"""
        if not self._running:
            return
            
        self._running = False
        if self._worker:
            self._worker.cancel()
            try:
                await self._worker
            except asyncio.CancelledError:
                pass
        logger.info("任务队列处理器已停止")
        
    async def _process_tasks(self, upload_controller):
        """处理任务队列"""
        while self._running:
            try:
                # 检查是否有到期的任务
                now = datetime.now()
                pending_tasks = self.get_pending_tasks()
                
                for task in pending_tasks:
                    if task.schedule_time <= now:
                        await self._execute_task(task, upload_controller)
                        
                await asyncio.sleep(1)  # 避免过度消耗CPU
                
            except Exception as e:
                logger.error(f"处理任务队列时出错: {e}")
                await asyncio.sleep(5)  # 出错后等待更长时间
                
    async def _execute_task(self, task: UploadTask, upload_controller):
        """执行单个任务"""
        try:
            task.status = 'running'
            logger.info(f"开始执行任务 {task.id} (重试次数: {task.retry_count})")
            
            success = await upload_controller.upload_content(
                platform=task.platform,
                content_dir=task.content_path
            )
            
            if success:
                task.status = 'completed'
            else:
                if task.can_retry():
                    task.status = 'pending'
                    task.retry_count += 1
                    logger.info(f"任务 {task.id} 将在稍后重试 (第 {task.retry_count} 次)")
                else:
                    task.status = 'failed'
                    task.error = "上传失败，已达到最大重试次数"
            
            # 保存任务状态
            self._save_tasks()
            
            self._notify_status_change(task.id, task.status)
            
        except Exception as e:
            task.status = 'failed'
            task.error = str(e)
            logger.error(f"执行任务 {task.id} 失败: {e}")

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
                    self.task_queue.put(task)
                
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
        for callback in self.status_callbacks:
            try:
                callback(task_id, new_status)
            except Exception as e:
                logger.error(f"状态通知回调执行失败: {e}")