from pathlib import Path
import sys
import os
from src.utils.log import logger

class PathManager:
    """路径管理器"""
    
    @staticmethod
    def get_root_dir() -> Path:
        """获取项目根目录"""
        return Path(__file__).resolve().parent.parent.parent
    
    @staticmethod
    def get_project_dir(name: str) -> Path:
        """获取项目目录"""
        dir_path = PathManager.get_root_dir() / name
        dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path
    
    @staticmethod
    def get_logs_dir() -> Path:
        """获取日志目录"""
        logs_dir = PathManager.get_root_dir() / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        return logs_dir
    
    @staticmethod
    def get_config_dir() -> Path:
        """获取配置文件目录"""
        config_dir = PathManager.get_root_dir() / "config"  # 改回根目录下的 config
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir
    
    @staticmethod
    def get_cookies_dir() -> Path:
        """获取 cookie 目录"""
        cookies_dir = PathManager.get_root_dir() / "cookies"
        cookies_dir.mkdir(parents=True, exist_ok=True)
        return cookies_dir
    
    @staticmethod
    def get_cookie_path(platform: str) -> Path:
        """获取指定平台的 cookie 文件路径"""
        cookies_dir = PathManager.get_cookies_dir()
        return cookies_dir / f"{platform}_account.json"
    
    @staticmethod
    def ensure_project_structure():
        """确保项目目录结构"""
        dirs = {
            'logs': "日志目录",      # 系统日志必需
            'config': "配置目录"     # 配置文件必需
        }
        
        for name, desc in dirs.items():
            dir_path = PathManager.get_project_dir(name)
            logger.info(f"确保{desc}存在: {dir_path}")