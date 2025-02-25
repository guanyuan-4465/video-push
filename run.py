import os
import sys
from pathlib import Path
# 将项目根目录添加到 Python 路径
ROOT_DIR = Path(__file__).resolve().parent
sys.path.append(str(ROOT_DIR))

# 导入必要的模块
from src.utils.paths import PathManager
from src.gui.app import main

if __name__ == "__main__":
    try:
        # 设置工作目录为项目根目录
        ROOT_DIR = Path(__file__).resolve().parent
        os.chdir(str(ROOT_DIR))
        
        # 确保必要的目录结构存在
        PathManager.ensure_project_structure()
        
        # 启动应用
        sys.exit(main())
    except Exception as e:
        print(f"程序启动失败：{str(e)}")
        sys.exit(1) 