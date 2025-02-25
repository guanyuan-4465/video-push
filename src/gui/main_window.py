from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QLineEdit, QCheckBox,
    QTabWidget, QFileDialog, QMessageBox, QInputDialog,
    QDateTimeEdit, QTableWidget, QTableWidgetItem, QHeaderView
)
from pathlib import Path
from src.config.base_config import ConfigManager
from src.utils.log import logger
from src.utils.paths import PathManager
import asyncio
from playwright.async_api import async_playwright
from src.core.controllers.upload_controller import UploadController
from src.core.validators.config_validator import ConfigValidator
from datetime import datetime, timedelta

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.config_validator = ConfigValidator()
        self.upload_controller = UploadController()
        # 初始化平台相关的控件
        self.platform_widgets = {
            'douyin': {},
            'xiaohongshu': {}
        }
        self.init_ui()
        # 加载配置到UI
        self.load_config_to_ui()
        
        # 初始化任务管理器
        asyncio.run(self.upload_controller.initialize())
        
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle('社交媒体自动发布工具')
        self.setGeometry(100, 100, 800, 600)
        
        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        layout = QVBoxLayout(central_widget)
        
        # 创建标签页
        tabs = QTabWidget()
        tabs.addTab(self.create_global_tab(), "全局设置")
        tabs.addTab(self.create_xhs_tab(), "小红书")
        tabs.addTab(self.create_douyin_tab(), "抖音")
        
        layout.addWidget(tabs)
        
        # 添加底部按钮
        button_layout = QHBoxLayout()
        save_button = QPushButton("保存配置")
        save_button.clicked.connect(self.save_config)
        button_layout.addWidget(save_button)
        
        start_button = QPushButton("开始发布")
        start_button.clicked.connect(self.start_upload)
        button_layout.addWidget(start_button)
        
        layout.addLayout(button_layout)
        
        # 添加任务管理标签页
        tabs.addTab(self.create_tasks_tab(), "任务管理")
        
    def create_global_tab(self) -> QWidget:
        """创建全局设置标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 批量发布设置
        batch_group = QWidget()
        batch_layout = QHBoxLayout(batch_group)
        self.batch_checkbox = QCheckBox("启用批量发布")
        batch_layout.addWidget(self.batch_checkbox)
        
        # 内容目录选择
        dir_group = QWidget()
        dir_layout = QHBoxLayout(dir_group)
        dir_layout.addWidget(QLabel("内容目录:"))
        self.dir_edit = QLineEdit()
        dir_layout.addWidget(self.dir_edit)
        browse_button = QPushButton("浏览...")
        browse_button.clicked.connect(self.browse_directory)
        dir_layout.addWidget(browse_button)
        
        layout.addWidget(batch_group)
        layout.addWidget(dir_group)
        layout.addStretch()
        
        return tab
    
    def create_platform_tab(self, platform: str) -> QWidget:
        """创建平台特定的标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 启用平台
        enable_group = QWidget()
        enable_layout = QHBoxLayout(enable_group)
        enabled_checkbox = QCheckBox(f"启用{platform}")
        enable_layout.addWidget(enabled_checkbox)
        
        # Cookie管理组
        cookie_group = QWidget()
        cookie_layout = QVBoxLayout(cookie_group)  # 改为垂直布局
        
        # Cookie文件选择
        cookie_file_layout = QHBoxLayout()
        cookie_file_layout.addWidget(QLabel("Cookie文件:"))
        cookie_edit = QLineEdit()
        cookie_file_layout.addWidget(cookie_edit)
        cookie_button = QPushButton("选择...")
        cookie_file_layout.addWidget(cookie_button)
        
        # Cookie操作按钮
        cookie_actions_layout = QHBoxLayout()
        get_cookie_button = QPushButton("获取Cookie")
        get_cookie_button.clicked.connect(
            lambda: asyncio.run(self.get_platform_cookie(platform))
        )
        cookie_actions_layout.addWidget(get_cookie_button)
        
        update_cookie_button = QPushButton("更新Cookie")
        update_cookie_button.clicked.connect(lambda: self.update_platform_cookie(platform))
        cookie_actions_layout.addWidget(update_cookie_button)
        
        # 添加到Cookie管理组
        cookie_layout.addLayout(cookie_file_layout)
        cookie_layout.addLayout(cookie_actions_layout)
        
        # 定时发布设置
        schedule_group = QWidget()
        schedule_layout = QHBoxLayout(schedule_group)
        schedule_checkbox = QCheckBox("启用定时发布")
        schedule_layout.addWidget(schedule_checkbox)
        
        # 保存控件引用
        platform_key = "douyin" if platform == "抖音" else "xiaohongshu"
        self.platform_widgets[platform_key] = {
            'enabled_checkbox': enabled_checkbox,
            'cookie_edit': cookie_edit,
            'cookie_button': cookie_button,
            'get_cookie_button': get_cookie_button,
            'update_cookie_button': update_cookie_button,
            'schedule': schedule_checkbox
        }
        
        # 设置按钮点击事件
        cookie_button.clicked.connect(
            lambda: self.browse_file(f"{platform} Cookie文件", "*.json", platform_key)
        )
        
        # 添加所有组件到布局
        layout.addWidget(enable_group)
        layout.addWidget(cookie_group)
        layout.addWidget(schedule_group)
        layout.addStretch()
        
        return tab
    
    def create_xhs_tab(self) -> QWidget:
        """创建小红书标签页"""
        return self.create_platform_tab("小红书")
    
    def create_douyin_tab(self) -> QWidget:
        """创建抖音标签页"""
        return self.create_platform_tab("抖音")
    
    def browse_directory(self):
        """浏览选择目录"""
        directory = QFileDialog.getExistingDirectory(self, "选择内容目录")
        if directory:
            dir_path = Path(directory)
            try:
                # 检查目录是否存在
                if not dir_path.exists():
                    dir_path.mkdir(parents=True)
                    logger.info(f"创建目录：{dir_path}")
                
                # 检查目录结构
                if self.batch_checkbox.isChecked():
                    # 批量模式：检查是否有子目录
                    video_dirs = [d for d in dir_path.iterdir() if d.is_dir()]
                    if not video_dirs:
                        reply = QMessageBox.question(
                            self,
                            "创建目录结构",
                            "当前为批量发布模式，但未找到子目录。\n是否创建示例目录结构？",
                            QMessageBox.Yes | QMessageBox.No
                        )
                        
                        if reply == QMessageBox.Yes:
                            # 创建示例批量目录结构
                            for i in range(1, 3):  # 创建两个示例目录
                                example_dir = dir_path / f"video{i}"
                                example_dir.mkdir(exist_ok=True)
                                logger.info(f"创建示例目录：{example_dir}")
                            
                            QMessageBox.information(
                                self,
                                "提示",
                                "已创建示例目录结构：\n"
                                "video1/\n"
                                "  - 视频文件 (video.mp4)\n"
                                "  - 封面图片 (cover.png)\n"
                                "  - 描述文件 (desc.txt)\n"
                                "video2/\n"
                                "  ..."
                            )
                else:
                    # 单个发布模式：直接检查文件
                    video_files = list(dir_path.glob("*.mp4"))
                    if not video_files:
                        QMessageBox.information(
                            self,
                            "提示",
                            "请在选择的目录中放置：\n"
                            "- 视频文件 (video.mp4)\n"
                            "- 封面图片 (cover.png)\n"
                            "- 描述文件 (desc.txt)"
                        )
                
                self.dir_edit.setText(str(dir_path))
                logger.info(f"已选择内容目录：{dir_path}")
                
            except Exception as e:
                logger.error(f"设置目录失败：{str(e)}")
                QMessageBox.critical(self, "错误", f"设置目录失败：{str(e)}")
    
    def browse_file(self, title: str, filter: str, platform: str):
        """浏览选择文件"""
        try:
            # 打开平台对应的cookie目录
            initial_dir = str(PathManager.get_platform_cookies_dir(platform))
            
            file, _ = QFileDialog.getOpenFileName(
                self, 
                title,
                initial_dir,
                filter
            )
            
            if file:
                try:
                    # 验证JSON文件
                    with open(file, 'r', encoding='utf-8') as f:
                        import json
                        json.load(f)
                    
                    self.platform_widgets[platform]['cookie_edit'].setText(file)
                    logger.info(f"已选择 {platform} 的 cookie 文件：{file}")
                        
                except json.JSONDecodeError:
                    logger.error(f"选择的文件不是有效的 JSON 文件：{file}")
                    QMessageBox.critical(self, "错误", "请选择有效的 JSON 格式的 cookie 文件")
                    self.platform_widgets[platform]['cookie_edit'].clear()
                except Exception as e:
                    logger.error(f"读取文件失败：{str(e)}")
                    QMessageBox.critical(self, "错误", f"读取文件失败：{str(e)}")
                    self.platform_widgets[platform]['cookie_edit'].clear()
                
        except Exception as e:
            logger.error(f"选择文件失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"选择文件失败：{str(e)}")
    
    def save_config(self):
        """保存配置"""
        try:
            # 1. 从UI获取配置并更新到 GlobalConfig 对象
            config = self.config_manager.config
            config.base_dir = Path(self.dir_edit.text())
            config.batch_enabled = self.batch_checkbox.isChecked()
            
            # 更新平台配置
            for platform in ['douyin', 'xiaohongshu']:
                widgets = self.platform_widgets.get(platform)
                if widgets:
                    platform_config = getattr(config, platform)
                    platform_config.enabled = widgets['enabled_checkbox'].isChecked()
                    platform_config.cookie_path = Path(widgets['cookie_edit'].text()) if widgets['cookie_edit'].text() else None
                    platform_config.schedule_enabled = widgets['schedule'].isChecked()

            # 2. 使用 ConfigValidator 验证配置对象
            if not self.config_validator.validate_config(config):
                QMessageBox.warning(self, "警告", "配置验证失败")
                return False

            # 3. 验证通过后，使用 ConfigManager 保存配置
            self.config_manager.save_config()
            logger.info("配置已保存")
            QMessageBox.information(self, "成功", "配置保存成功！")
            return True
            
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            QMessageBox.critical(self, "错误", f"保存配置失败：{str(e)}")
            return False

    def get_uploader(self, platform: str):
        """获取平台对应的上传器
        Args:
            platform: 平台名称(douyin/xiaohongshu)
        Returns:
            对应平台的上传器实例
        """
        try:
            if platform == 'douyin':
                from src.core.uploaders.douyin import DouYinUploader
                config = self.config_manager.config.douyin
                return DouYinUploader(
                    title="",  # 从内容目录的desc.txt中读取
                    file_path="",  # 从内容目录中读取
                    tags=[],  # 从desc.txt中解析
                    publish_date=None,  # 暂不支持定时发布
                    account_file=str(config.cookie_path),
                    thumbnail_path=""  # 从内容目录中读取
                )
            elif platform == 'xiaohongshu':
                from src.core.uploaders.xiaohongshu import XHSUploader
                config = self.config_manager.config.xiaohongshu
                return XHSUploader(
                    title="",
                    file_path="",
                    tags=[],
                    publish_date=None,
                    account_file=str(config.cookie_path),
                    thumbnail_path=""
                )
            else:
                raise ValueError(f"不支持的平台: {platform}")
            
        except Exception as e:
            logger.error(f"获取上传器失败: {e}")
            raise

    async def start_single_upload(self, uploader, content):
        """执行单个内容的上传"""
        # 读取内容信息
        desc_file = content['desc']
        with open(desc_file, 'r', encoding='utf-8') as f:
            desc_text = f.read().strip()
        
        # 更新上传器参数
        uploader.title = desc_text.split('\n')[0]  # 第一行作为标题
        uploader.file_path = str(content['video'])
        uploader.thumbnail_path = str(content['cover'])
        uploader.tags = []  # TODO: 从desc.txt中解析标签
        
        # 开始上传
        async with async_playwright() as playwright:
            await uploader.upload(playwright)

    def start_upload(self):
        """开始上传"""
        try:
            # 检查是否选择了目录
            if not self.config_manager.config.base_dir:
                QMessageBox.warning(self, "警告", "请先选择内容目录！")
                return
            
            # 获取启用的平台
            enabled_platforms = []
            for platform in ['douyin', 'xiaohongshu']:
                platform_config = getattr(self.config_manager.config, platform)
                if platform_config.enabled:
                    enabled_platforms.append(platform)
                
            if not enabled_platforms:
                QMessageBox.warning(self, "警告", "请至少启用一个平台！")
                return
            
            content_dir = Path(self.config_manager.config.base_dir)
            
            # 处理每个启用的平台
            for platform in enabled_platforms:
                widgets = self.platform_widgets[platform]
                
                if widgets['schedule'].isChecked():
                    # 定时发布
                    schedule_time = widgets['time_picker'].dateTime().toPyDateTime()
                    success = self.upload_controller.schedule_upload(
                        platform=platform,
                        content_dir=content_dir,
                        schedule_time=schedule_time
                    )
                    if success:
                        logger.info(f"已添加定时任务: {platform} - {schedule_time}")
                    else:
                        QMessageBox.warning(self, "警告", f"添加定时任务失败：{platform}")
                else:
                    # 立即执行
                    asyncio.run(self.upload_controller.upload_content(
                        platform=platform,
                        content_dir=content_dir
                    ))
            
            # 刷新任务列表
            self.refresh_tasks()
                    
        except Exception as e:
            logger.error(f"上传失败: {e}")
            QMessageBox.critical(self, "错误", f"上传失败：{str(e)}")
            
    async def get_platform_cookie(self, platform: str):
        """获取平台Cookie"""
        try:
            # 获取账号名称（这里需要实现）
            account_name = await self._get_account_name()
            if not account_name:
                return
            
            platform_key = self._get_platform_key(platform)
            cookie_file = PathManager.get_cookie_path(platform_key, account_name)
            
            # 确保cookie目录存在
            cookie_file.parent.mkdir(parents=True, exist_ok=True)
            
            success = await self.upload_controller.generate_cookie(
                platform_key, 
                str(cookie_file)
            )
            
            if success:
                self._update_cookie_ui(platform_key, cookie_file)
                self._show_success_message(f"已成功获取{platform}账号 {account_name} 的Cookie")
            else:
                self._show_error_message("获取Cookie失败")
            
        except Exception as e:
            self._handle_error(f"获取{platform} Cookie失败", e)

    def _get_platform_key(self, platform: str) -> str:
        """获取平台标识"""
        platform_map = {
            "抖音": "douyin",
            "小红书": "xiaohongshu"
        }
        return platform_map.get(platform, platform.lower())

    async def _get_account_name(self) -> str:
        """获取账号名称"""
        try:
            # 使用 QInputDialog 获取用户输入
            account_name, ok = QInputDialog.getText(
                self,
                "输入账号名称",
                "请输入要保存的账号名称:",
                QLineEdit.EchoMode.Normal
            )
            
            if not ok or not account_name:
                logger.info("用户取消输入账号名称")
                return ""
            
            # 验证账号名称（可以添加更多验证规则）
            if len(account_name) < 2:
                self._show_error_message("账号名称太短")
                return ""
            
            logger.info(f"用户输入账号名称: {account_name}")
            return account_name
            
        except Exception as e:
            self._handle_error("获取账号名称失败", e)
            return ""

    def update_platform_cookie(self, platform: str):
        """更新平台Cookie"""
        try:
            # 平台名称映射
            platform_map = {
                "抖音": "douyin",
                "小红书": "xiaohongshu"
            }
            platform_key = platform_map.get(platform, platform.lower())
            
            # 打开平台对应的cookie目录让用户选择文件
            platform_dir = PathManager.get_platform_cookies_dir(platform_key)
            file, _ = QFileDialog.getOpenFileName(
                self,
                f"选择要更新的{platform} Cookie文件",
                str(platform_dir),
                "JSON文件 (*.json)"
            )
            
            if not file:  # 用户取消选择
                return
            
            try:
                # 验证JSON文件
                with open(file, 'r', encoding='utf-8') as f:
                    import json
                    json.load(f)
            except json.JSONDecodeError:
                QMessageBox.critical(self, "错误", "请选择有效的JSON格式的cookie文件")
                return
            except Exception as e:
                QMessageBox.critical(self, "错误", f"读取文件失败：{str(e)}")
                return
            
            # 显示确认对话框
            reply = QMessageBox.question(
                self,
                "确认更新",
                f"确定要更新选中的Cookie文件吗？\n{file}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.No:
                return
            
            # 显示提示消息
            QMessageBox.information(self, "提示", "即将打开浏览器，请扫码登录")
            
            # 根据平台调用对应的cookie获取函数
            if platform_key == "douyin":  # 修改这里，使用映射后的key来判断
                from src.core.uploaders.douyin import douyin_cookie_gen
                success = asyncio.run(douyin_cookie_gen(file))
            else:
                from src.core.uploaders.xiaohongshu import xhs_cookie_gen
                success = asyncio.run(xhs_cookie_gen(file))
            
            if success:
                # 更新UI显示
                self.platform_widgets[platform_key]['cookie_edit'].setText(file)  # 使用映射后的平台名称
                QMessageBox.information(self, "成功", f"{platform} Cookie已更新")
            else:
                QMessageBox.warning(self, "警告", f"{platform} Cookie更新失败")
            
        except Exception as e:
            logger.error(f"更新{platform} Cookie失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"更新Cookie失败：{str(e)}")

    def load_config_to_ui(self):
        """将配置加载到UI控件"""
        try:
            config = self.config_manager.config
            
            # 加载全局配置
            if config.base_dir:
                self.dir_edit.setText(str(config.base_dir))
            self.batch_checkbox.setChecked(config.batch_enabled)
            
            # 加载平台配置
            for platform in ['douyin', 'xiaohongshu']:
                platform_config = getattr(config, platform)
                widgets = self.platform_widgets.get(platform)
                if widgets:
                    widgets['enabled_checkbox'].setChecked(platform_config.enabled)
                    if platform_config.cookie_path:
                        widgets['cookie_edit'].setText(str(platform_config.cookie_path))
                    widgets['schedule'].setChecked(platform_config.schedule_enabled)
            
            logger.info("配置已加载到UI")
        except Exception as e:
            logger.error(f"加载配置到UI失败: {e}")

    def run_async(self, coro):
        """运行异步函数的辅助方法"""
        try:
            return asyncio.run(coro)
        except Exception as e:
            logger.error(f"异步操作失败: {e}")
            QMessageBox.critical(self, "错误", f"操作失败：{str(e)}")

    def _show_error_message(self, message: str):
        """显示错误消息"""
        QMessageBox.critical(self, "错误", message)

    def _show_success_message(self, message: str):
        """显示成功消息"""
        QMessageBox.information(self, "成功", message)

    def _handle_error(self, message: str, error: Exception):
        """处理错误"""
        error_message = f"{message}: {str(error)}"
        logger.error(error_message)
        self._show_error_message(error_message)

    def _update_cookie_ui(self, platform_key: str, cookie_file: Path):
        """更新Cookie相关的UI"""
        widgets = self.platform_widgets.get(platform_key)
        if widgets:
            widgets['cookie_edit'].setText(str(cookie_file))

    def create_tasks_tab(self) -> QWidget:
        """创建任务管理标签页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 任务列表
        self.task_table = QTableWidget()
        self.task_table.setColumnCount(6)
        self.task_table.setHorizontalHeaderLabels([
            "ID", "平台", "内容路径", "计划时间", "状态", "错误信息"
        ])
        self.task_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.task_table)
        
        # 任务操作按钮
        button_layout = QHBoxLayout()
        refresh_button = QPushButton("刷新任务列表")
        refresh_button.clicked.connect(self.refresh_tasks)
        button_layout.addWidget(refresh_button)
        
        clear_button = QPushButton("清理已完成任务")
        clear_button.clicked.connect(self.clear_completed_tasks)
        button_layout.addWidget(clear_button)
        
        layout.addLayout(button_layout)
        
        # 初始刷新任务列表
        self.refresh_tasks()
        
        return tab
        
    def refresh_tasks(self):
        """刷新任务列表"""
        tasks = self.upload_controller.get_all_tasks()
        self.task_table.setRowCount(len(tasks))
        
        for row, task in enumerate(tasks):
            self.task_table.setItem(row, 0, QTableWidgetItem(task.id))
            self.task_table.setItem(row, 1, QTableWidgetItem(task.platform))
            self.task_table.setItem(row, 2, QTableWidgetItem(task.content_path))
            self.task_table.setItem(row, 3, QTableWidgetItem(
                task.schedule_time.strftime("%Y-%m-%d %H:%M:%S")
            ))
            self.task_table.setItem(row, 4, QTableWidgetItem(task.status))
            self.task_table.setItem(row, 5, QTableWidgetItem(task.error or ""))
            
    def clear_completed_tasks(self):
        """清理已完成的任务"""
        # TODO: 实现任务清理功能
        pass
        
    def closeEvent(self, event):
        """窗口关闭事件"""
        try:
            # 停止任务管理器
            asyncio.run(self.upload_controller.shutdown())
            event.accept()
        except Exception as e:
            logger.error(f"关闭任务管理器失败: {e}")
            event.accept()