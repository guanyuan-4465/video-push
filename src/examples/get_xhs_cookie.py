import asyncio
from pathlib import Path
import sys

# 添加项目根目录到 Python 路径
ROOT_DIR = Path(__file__).parent.parent
sys.path.append(str(ROOT_DIR))

from conf import BASE_DIR
from uploader.xhs_uploader.main import xhs_setup

if __name__ == '__main__':
    # 设置 cookie 文件路径
    account_file = Path(BASE_DIR / "cookies" / "xhs_uploader" / "account.json")
    
    # 确保目录存在
    account_file.parent.mkdir(parents=True, exist_ok=True)
    
    # 运行登录流程
    cookie_setup = asyncio.run(xhs_setup(str(account_file), handle=True)) 