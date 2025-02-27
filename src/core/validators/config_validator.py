from pathlib import Path
from typing import List
from src.utils.log import logger
from src.utils.paths import PathManager
import json
from src.config.base_config import GlobalConfig

class ConfigValidator:
    @staticmethod
    def validate_base_dir(base_dir: Path) -> bool:
        if not base_dir or not base_dir.exists():
            logger.error("内容目录不存在")
            return False
        return True
        
    @staticmethod
    def validate_platform_config(platform: str, config: dict) -> bool:
        if not config.get('enabled'):
            return True  # 未启用的平台不需要验证
            
        cookie_path = config.get('cookie_path')
        if not cookie_path or not Path(cookie_path).exists():
            logger.error(f"{platform} 平台的Cookie文件不存在")
            return False
            
        return True 

    def validate_config(self, config: GlobalConfig) -> bool:
        """验证配置对象"""
        try:
            # 验证基础配置
            if not self.validate_base_dir(config.base_dir):
                logger.error("基础目录验证失败")
                return False
                
            # 验证批量模式配置
            if not isinstance(config.batch_enabled, bool):
                logger.error("批量模式配置类型错误")
                return False
            
            # 验证平台配置
            for platform in ['douyin', 'xiaohongshu']:
                platform_config = getattr(config, platform)
                if not self.validate_platform_config(platform, platform_config.__dict__):
                    logger.error(f"{platform}平台配置验证失败")
                    return False
            
            logger.info("配置验证通过")
            return True
            
        except Exception as e:
            logger.error(f"配置验证失败: {e}")
            return False 