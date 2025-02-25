from pathlib import Path
from sys import stdout
from loguru import logger
from src.utils.paths import PathManager
import logging


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


def setup_logger():
    """设置统一的日志系统"""
    # 移除所有现有处理器
    logger.remove()
    
    # 设置日志格式
    log_format = "{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
    
    # 设置日志文件
    log_file = PathManager.get_logs_dir() / "app.log"
    
    # 添加文件处理器
    logger.add(
        log_file,
        format=log_format,
        rotation="500 MB",
        retention="10 days",
        encoding="utf-8"
    )
    
    # 添加控制台处理器
    logger.add(stdout, colorize=True, format=log_format)
    
    # 使用 logging 模块配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    return logger


# 创建全局日志对象
logger = setup_logger()

