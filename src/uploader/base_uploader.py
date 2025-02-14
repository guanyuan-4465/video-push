class BaseUploader:
    def __init__(self, config: PlatformConfig):
        self.config = config
        
    def upload(self, content: MediaContent):
        """上传内容"""
        raise NotImplementedError

class XHSUploader(BaseUploader):
    def upload(self, content: MediaContent):
        """实现小红书上传逻辑"""
        # 1. 读取cookie
        # 2. 初始化会话
        # 3. 上传视频
        # 4. 发布内容
        pass

class DouyinUploader(BaseUploader):
    def upload(self, content: MediaContent):
        """实现抖音上传逻辑"""
        pass 