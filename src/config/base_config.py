from pathlib import Path
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict, field
from src.utils.log import logger
from src.utils.paths import PathManager
import os

@dataclass
class PlatformConfig:
    """简化后的平台配置"""
    enabled: bool = False
    cookie_path: str = ""
    location: str = ""  # 发布地点
    upload_interval: int = 30  # 上传间隔(分钟)
    schedule_enabled: bool = False  # 定时发布开关
    content_type: str = "video"  # 新增：内容类型 "video" 或 "image"

@dataclass
class GlobalConfig:
    """简化后的全局配置"""
    base_dir: Path = field(default_factory=lambda: Path.home() / "Documents" / "uploads")
    batch_enabled: bool = False
    content_type: str = "video"  # 新增：全局默认内容类型
    
    # 平台配置
    douyin: PlatformConfig = field(default_factory=PlatformConfig)
    xiaohongshu: PlatformConfig = field(default_factory=PlatformConfig)

    def get_platform_config(self, platform: str) -> Dict[str, Any]:
        """获取指定平台的配置"""
        if platform == 'douyin':
            return asdict(self.douyin)
        elif platform == 'xiaohongshu':
            return asdict(self.xiaohongshu)
        else:
            return {}


class ConfigManager:
    """配置管理器"""
    def __init__(self):
        self.config_path = PathManager.get_config_dir() / "config.json"
        self._config = None  # 不在初始化时加载配置
        
    @property
    def config(self) -> GlobalConfig:
        """每次访问配置时重新加载"""
        self._config = self._load_config()
        return self._config
        
    def _load_config(self) -> GlobalConfig:
        """加载配置文件"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    logger.info(f"读取到的原始配置: {config_data}")  # 添加日志
                
                config = GlobalConfig()
                
                # 设置全局配置属性
                if 'base_dir' in config_data:
                    config.base_dir = Path(config_data['base_dir'])
                if 'batch_enabled' in config_data:
                    config.batch_enabled = config_data['batch_enabled']
                if 'content_type' in config_data:
                    config.content_type = config_data['content_type']
                
                logger.info(f"全局配置设置完成: base_dir={config.base_dir}, batch_enabled={config.batch_enabled}")
                
                # 设置平台配置
                for platform in ['douyin', 'xiaohongshu']:
                    if platform in config_data:
                        platform_config = getattr(config, platform)
                        platform_data = config_data[platform]
                        logger.info(f"{platform} 平台配置数据: {platform_data}")
                        
                        for key, value in platform_data.items():
                            if hasattr(platform_config, key):
                                setattr(platform_config, key, value)
                                logger.info(f"设置 {platform}.{key} = {value}")
                
                # 验证配置加载结果
                logger.info(f"全局配置状态: batch_enabled={config.batch_enabled}")
                for platform in ['douyin', 'xiaohongshu']:
                    platform_config = getattr(config, platform)
                    logger.info(f"加载后的 {platform} 配置: {asdict(platform_config)}")
                    
                return config
            else:
                # 创建默认配置
                logger.info(f"配置文件不存在，创建默认配置: {self.config_path}")
                config = GlobalConfig()
                self.save_config(config)
                return config
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            return GlobalConfig()  # 返回默认配置
            
    def save_config(self, config: Optional[GlobalConfig] = None) -> bool:
        """保存配置到文件"""
        try:
            if config is None:
                config = self._config or GlobalConfig()
                
            # 确保配置目录存在
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 转换为字典
            config_dict = {
                'base_dir': str(config.base_dir),
                'batch_enabled': config.batch_enabled,  # 确保包含批量模式状态
                'douyin': asdict(config.douyin),
                'xiaohongshu': asdict(config.xiaohongshu)
            }
            
            logger.info(f"准备保存的配置: {config_dict}")
            
            # 直接写入文件
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, ensure_ascii=False, indent=2)
                f.flush()  # 确保写入磁盘
                os.fsync(f.fileno())
            
            # 验证保存结果
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    saved_data = json.load(f)
                    if 'batch_enabled' not in saved_data:
                        logger.error("批量模式配置未成功保存")
                        return False
                    logger.info(f"配置已验证: {saved_data}")
                    
            # 保存后清空缓存的配置
            self._config = None
            logger.info("配置已保存，并清除缓存")
            return True
            
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            return False
            
    def get_platform_config(self, platform: str) -> Dict[str, Any]:
        """获取平台配置"""
        return self.config.get_platform_config(platform)
    
    def update_platform_config(self, platform: str, new_config: Dict[str, Any]) -> bool:
        """更新平台配置"""
        try:
            if platform not in ['douyin', 'xiaohongshu']:
                logger.error(f"不支持的平台: {platform}")
                return False
                
            platform_config = getattr(self.config, platform)
            
            # 更新配置
            for key, value in new_config.items():
                if hasattr(platform_config, key):
                    setattr(platform_config, key, value)
            
            # 保存配置
            return self.save_config()
            
        except Exception as e:
            logger.error(f"更新平台配置失败: {e}")
            return False

    def _validate_config(self, config: GlobalConfig) -> dict:
        """验证配置的完整性"""
        errors = []
        
        # 验证基础目录
        base_dir = Path(config.base_dir)
        if not base_dir.exists():
            errors.append(f"内容目录不存在: {base_dir}")
            return {'valid': False, 'errors': errors}
        
        # 批量模式的特殊验证
        if config.batch_enabled:
            # 检查是否有子目录
            sub_dirs = [d for d in base_dir.iterdir() if d.is_dir()]
            if not sub_dirs:
                errors.append("批量模式已启用但内容目录下没有子目录")
            else:
                # 验证每个子目录的结构
                for sub_dir in sub_dirs:
                    sub_errors = self._validate_content_dir(sub_dir)
                    if sub_errors:
                        errors.append(f"子目录 {sub_dir.name} 验证失败: {', '.join(sub_errors)}")
        else:
            # 单个模式验证
            content_errors = self._validate_content_dir(base_dir)
            if content_errors:
                errors.extend(content_errors)
        
        # 验证平台配置
        for platform in ['douyin', 'xiaohongshu']:
            platform_config = getattr(config, platform)
            if platform_config.enabled:
                if not platform_config.cookie_path:
                    errors.append(f"{platform} 未设置Cookie路径")
                elif not Path(platform_config.cookie_path).exists():
                    errors.append(f"{platform} Cookie文件不存在: {platform_config.cookie_path}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }

    def _validate_content_dir(self, directory: Path) -> List[str]:
        """验证内容目录的结构"""
        errors = []
        
        # 检查必要文件
        video_files = list(directory.glob("*.mp4"))
        image_files = list(directory.glob("*.jpg")) + list(directory.glob("*.png"))
        desc_files = list(directory.glob("*.txt"))
        
        if not (video_files or image_files):
            errors.append("未找到媒体文件(视频或图片)")
        if not desc_files:
            errors.append("未找到描述文件(desc.txt)")
        
        return errors 