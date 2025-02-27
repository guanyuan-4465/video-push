from PyQt6.QtWidgets import QApplication, QMessageBox
from src.gui.main_window import MainWindow
from src.core.services.process_pool import initialize_process_pool, shutdown_process_pool
from src.utils.log import logger
from src.core.services.task_queue import TaskQueue
import sys

def main():
    """应用入口"""
    app = None
    try:
        # 1. 先创建Qt应用
        app = QApplication(sys.argv)
        
        # 2. 初始化进程池
        logger.info("正在初始化进程池...")
        if not initialize_process_pool():
            logger.error("进程池初始化失败")
            raise RuntimeError("进程池初始化失败")
        else:
            logger.info("进程池初始化成功")
            
        # 3. 创建并显示主窗口
        window = MainWindow()
        window.show()
            
        # 4. 启动任务队列处理
        task_queue = TaskQueue()
        task_queue.clear_completed_tasks()
        window.start_task_processing()
        
        # 5. 运行应用事件循环
        exit_code = app.exec()
        
        return exit_code
        
    except Exception as e:
        # 错误处理
        error_msg = f"程序启动失败：{str(e)}"
        logger.error(error_msg)
        
        # 显示错误对话框
        if app:
            QMessageBox.critical(None, "错误", error_msg)
            app.quit()
            
        return 1
        
    finally:
        # 确保进程池在应用退出时被关闭
        shutdown_process_pool()