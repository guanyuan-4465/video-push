from concurrent.futures import ProcessPoolExecutor
import multiprocessing
from typing import Optional
from src.utils.log import logger

class ProcessPoolManager:
    _instance = None
    _pool: Optional[ProcessPoolExecutor] = None
    
    def __init__(self):
        self._pool = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def initialize_pool(self, max_workers: Optional[int] = None):
        """初始化进程池"""
        if max_workers is None:
            max_workers = multiprocessing.cpu_count()
        
        if self._pool is None:
            self._pool = ProcessPoolExecutor(max_workers=max_workers)
            logger.info(f"进程池已初始化，包含 {max_workers} 个工作进程")
        return self._pool

    def get_pool(self) -> Optional[ProcessPoolExecutor]:
        """获取进程池"""
        if self._pool is None:
            self.initialize_pool()
        return self._pool

# 全局实例
_pool_manager = ProcessPoolManager()

def get_process_pool() -> Optional[ProcessPoolExecutor]:
    """获取进程池实例"""
    return _pool_manager.get_pool()

def initialize_process_pool(max_workers: Optional[int] = None) -> bool:
    """初始化进程池"""
    try:
        pool = _pool_manager.initialize_pool(max_workers)
        return pool is not None
    except Exception as e:
        logger.error(f"初始化进程池失败: {e}")
        return False

def shutdown_process_pool():
    """关闭进程池"""
    try:
        if _pool_manager._pool:
            _pool_manager._pool.shutdown(wait=True)
            _pool_manager._pool = None
            logger.info("进程池已关闭")
    except Exception as e:
        logger.error(f"关闭进程池失败: {e}")