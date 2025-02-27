from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Optional, List
from playwright.async_api import Playwright

class BaseUploader(ABC):
    def __init__(self, 
                 title: str,
                 file_path: str,
                 tags: List[str],
                 publish_date: Optional[str],
                 account_file: str,
                 thumbnail_path: Optional[str] = None,
                 location: Optional[str] = None):
        self.title = title
        self.file_path = file_path
        self.tags = tags or []
        self.publish_date = publish_date
        self.account_file = account_file
        self.thumbnail_path = thumbnail_path
        self.location = location

    @abstractmethod
    async def upload(self, playwright: Playwright) -> bool:
        """执行上传操作"""
        pass

    @abstractmethod
    async def validate_cookie(self) -> bool:
        """验证cookie是否有效"""
        pass

    @abstractmethod
    async def generate_cookie(self) -> bool:
        """生成新的cookie"""
        pass 