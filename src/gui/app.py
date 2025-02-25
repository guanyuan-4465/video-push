import sys
from PyQt6.QtWidgets import QApplication, QMessageBox
from src.gui.main_window import MainWindow
from src.utils.paths import PathManager
from src.utils.log import logger  # 改用新的 logger
import asyncio

def main():
    app = QApplication(sys.argv)
    
    try:
        # 确保项目目录结构存在
        PathManager.ensure_project_structure()
        
        window = MainWindow()
        window.show()
        
        return app.exec()
    except Exception as e:
        logger.error(f"程序启动失败：{str(e)}")
        QMessageBox.critical(None, "错误", f"程序启动失败：{str(e)}")
        return 1

if __name__ == "__main__":
    main()