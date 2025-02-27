from pathlib import Path
from sys import stdout
import sys
from loguru import logger
from src.utils.paths import PathManager


def log_formatter(record: dict) -> str:
    """
    Formatter for log records.
    :param dict record: Log object containing log metadata & message.
    :returns: str
    """
    colors = {
        "TRACE": "#cfe2f3",
        "INFO": "#9cbfdd",
        "DEBUG": "#8598ea",
        "WARNING": "#dcad5a",
        "SUCCESS": "#3dd08d",
        "ERROR": "#ae2c2c"
    }
    color = colors.get(record["level"].name, "#b3cfe7")
    return f"<fg #70acde>{{time:YYYY-MM-DD HH:mm:ss}}</fg #70acde> | <fg {color}>{{level}}</fg {color}>: <light-white>{{message}}</light-white>\n"


def create_logger(log_name: str, file_path: str):
    """
    Create custom logger for different business modules.
    :param str log_name: name of log
    :param str file_path: Optional path to log file
    :returns: Configured logger
    """
    def filter_record(record):
        return record["extra"].get("business_name") == log_name

    log_dir = PathManager.get_logs_dir()
    log_dir.mkdir(exist_ok=True)
    
    logger.add(
        log_dir / file_path,
        filter=filter_record,
        level="INFO",
        rotation="10 MB",
        retention="10 days",
        backtrace=True,
        diagnose=True
    )
    return logger.bind(business_name=log_name)


def setup_logging():
    """配置日志系统"""
    log_dir = Path(__file__).parent.parent.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / "app.log"
    
    # 配置 loguru
    logger.remove()  # 移除默认处理器
    logger.add(
        log_file,
        level="INFO",
        rotation="10 MB",
        retention="10 days",
        format="{time:YYYY-MM-DD HH:mm:ss} - {name} - {level} - {message}",
        encoding='utf-8'
    )
    logger.add(sys.stdout, level="INFO")  # 添加控制台输出


# 在应用启动时调用
setup_logging()

# 导出 logger
logger = logger.bind(name=__name__)

