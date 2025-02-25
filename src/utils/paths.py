from pathlib import Path
import sys
import os

class PathManager:
    """路径管理器"""
    
    @staticmethod
    def get_root_dir() -> Path:
        """获取项目根目录"""
        return Path(__file__).resolve().parent.parent.parent
    
    @staticmethod
    def get_src_dir() -> Path:
        """获取src目录"""
        return PathManager.get_root_dir() / "src"
    
    @staticmethod
    def get_core_dir() -> Path:
        """获取core目录"""
        return PathManager.get_src_dir() / "core"
        
    @staticmethod
    def get_uploaders_dir() -> Path:
        """获取uploaders目录"""
        return PathManager.get_core_dir() / "uploaders"
    
    @staticmethod
    def get_services_dir() -> Path:
        """获取services目录"""
        return PathManager.get_core_dir() / "services"
    
    @staticmethod
    def get_validators_dir() -> Path:
        """获取validators目录"""
        return PathManager.get_core_dir() / "validators"

    @staticmethod
    def get_data_dir() -> Path:
        """获取数据根目录"""
        data_dir = PathManager.get_root_dir() / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir

    @staticmethod
    def get_logs_dir() -> Path:
        """获取日志目录"""
        logs_dir = PathManager.get_data_dir() / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        return logs_dir

    @staticmethod
    def get_config_dir() -> Path:
        """获取配置文件目录"""
        config_dir = PathManager.get_data_dir() / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir
    
    @staticmethod
    def get_cookies_dir() -> Path:
        """获取 cookie 根目录"""
        cookies_dir = PathManager.get_data_dir() / "cookies"
        cookies_dir.mkdir(parents=True, exist_ok=True)
        return cookies_dir
        
    @staticmethod
    def get_platform_cookies_dir(platform: str) -> Path:
        """获取指定平台的 cookie 目录
        Args:
            platform: 平台名称(douyin/xiaohongshu)
        """
        platform_dir = PathManager.get_cookies_dir() / platform
        platform_dir.mkdir(parents=True, exist_ok=True)
        return platform_dir

    @staticmethod
    def get_cookie_path(platform: str, account_name: str) -> Path:
        """获取指定平台指定账号的 cookie 文件路径
        Args:
            platform: 平台名称(douyin/xiaohongshu)
            account_name: 账号名称
        """
        platform_dir = PathManager.get_platform_cookies_dir(platform)
        return platform_dir / f"{account_name}.json"

    @staticmethod
    def ensure_project_structure():
        """确保项目目录结构存在"""
        # 创建基本目录结构
        dirs = {
            'logs': "日志目录",
            'config': "配置目录",
            'cookies': "Cookie目录",
        }
        
        # 在 data 目录下创建子目录
        data_dir = PathManager.get_data_dir()
        for name, desc in dirs.items():
            dir_path = data_dir / name
            dir_path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def ensure_core_structure():
        """确保core目录结构存在"""
        dirs = {
            'uploaders': "上传器目录",
            'services': "服务目录",
            'validators': "验证器目录",
            'controllers': "控制器目录"
        }
        
        core_dir = PathManager.get_core_dir()
        for name, desc in dirs.items():
            dir_path = core_dir / name
            dir_path.mkdir(parents=True, exist_ok=True)
            
        # 确保__init__.py文件存在
        for dir_path in core_dir.glob("**/"):
            init_file = dir_path / "__init__.py"
            if not init_file.exists():
                init_file.touch()
