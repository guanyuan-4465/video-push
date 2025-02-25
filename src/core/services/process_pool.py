from multiprocessing import Pool, cpu_count
from src.utils.log import logger

# 全局进程池
_process_pool = None

def initialize_process_pool():
    """初始化进程池"""
    global _process_pool
    try:
        # 减少进程数，只使用CPU核心数的1/4，最少2个进程
        worker_count = max(cpu_count() // 4, 2)  
        _process_pool = Pool(processes=worker_count)
        logger.info(f"进程池已初始化，工作进程数: {worker_count}")
        return _process_pool
    except Exception as e:
        logger.error(f"初始化进程池失败: {e}")
        return None

def get_process_pool():
    """获取进程池实例"""
    global _process_pool
    try:
        if _process_pool is None:
            logger.info("初始化进程池...")
            _process_pool = initialize_process_pool()
        return _process_pool
    except Exception as e:
        logger.error(f"获取进程池失败: {e}")
        return None

def shutdown_process_pool():
    """关闭进程池"""
    global _process_pool
    if _process_pool:
        _process_pool.close()
        _process_pool.join()
        _process_pool = None