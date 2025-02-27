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
from PyQt6.QtCore import QTimer, QThread, pyqtSignal, pyqtSlot
from typing import Optional
from src.core.services.process_pool import get_process_pool
import os

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("社交媒体自动发布工具")  # 设置窗口标题
        
        # 延迟初始化控制器
        self.upload_controller = None
        self.config_manager = None
        self.config_validator = None
        
        # 初始化UI
        self.platform_widgets = {
            'douyin': {},
            'xiaohongshu': {}
        }
        
        # 延迟加载
        QTimer.singleShot(0, self._delayed_init)
        
        # 注册窗口关闭事件
        self.closeEvent = self.handle_close
        
        # 添加定时刷新任务状态
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_tasks)
        self.refresh_timer.start(5000)  # 每5秒刷新一次
        
        # 在MainWindow的__init__方法中添加:
        pool = get_process_pool()
        if pool:
            logger.info("进程池已初始化")
        else:
            logger.warning("进程池未初始化，部分功能可能不可用")
        
    def _delayed_init(self):
        """延迟初始化"""
        try:
            self.config_manager = ConfigManager()
            self.config_validator = ConfigValidator()
            self.upload_controller = UploadController()
            
            self.init_ui()
            self.load_config_to_ui()
        except Exception as e:
            logger.error(f"延迟初始化失败: {e}")
        
    def init_ui(self):
        """初始化UI"""
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
        cookie_layout = QVBoxLayout(cookie_group)
        
        # Cookie文件选择
        cookie_file_layout = QHBoxLayout()
        cookie_file_layout.addWidget(QLabel("Cookie文件:"))
        cookie_edit = QLineEdit()
        cookie_file_layout.addWidget(cookie_edit)
        cookie_button = QPushButton("选择...")
        cookie_file_layout.addWidget(cookie_button)
        
        # 添加到Cookie管理组
        cookie_layout.addLayout(cookie_file_layout)
        
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
        
        cookie_layout.addLayout(cookie_actions_layout)
        
        # 发布地点设置
        location_group = QWidget()
        location_layout = QHBoxLayout(location_group)
        location_layout.addWidget(QLabel("发布地点:"))
        location_edit = QLineEdit()
        location_layout.addWidget(location_edit)
        
        # 定时发布设置
        schedule_group = QWidget()
        schedule_layout = QHBoxLayout(schedule_group)
        schedule_checkbox = QCheckBox("启用定时发布")
        schedule_layout.addWidget(schedule_checkbox)
        
        # 添加时间选择器
        schedule_time = QDateTimeEdit()
        schedule_time.setDateTime(datetime.now() + timedelta(minutes=5))
        schedule_time.setEnabled(False)  # 初始禁用
        schedule_layout.addWidget(schedule_time)

        # 连接复选框状态变化
        schedule_checkbox.stateChanged.connect(lambda state: schedule_time.setEnabled(state == 2))
        
        # 保存控件引用
        platform_key = "douyin" if platform == "抖音" else "xiaohongshu"
        self.platform_widgets[platform_key] = {
            'enabled_checkbox': enabled_checkbox,
            'cookie_edit': cookie_edit,
            'cookie_button': cookie_button,
            'get_cookie_button': get_cookie_button,
            'update_cookie_button': update_cookie_button,
            'location_edit': location_edit,
            'schedule': schedule_checkbox,
            'time_picker': schedule_time
        }
        
        # 设置按钮点击事件
        cookie_button.clicked.connect(
            lambda: self.browse_file(f"{platform} Cookie文件", "*.json", platform_key)
        )
        
        # 添加所有组件到布局
        layout.addWidget(enable_group)
        layout.addWidget(cookie_group)
        layout.addWidget(location_group)
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
                    content_dirs = [d for d in dir_path.iterdir() if d.is_dir()]
                    if not content_dirs:
                        reply = QMessageBox.question(
                            self,
                            "创建目录结构",
                            "当前为批量发布模式，但未找到子目录。\n是否创建示例目录结构？",
                            QMessageBox.Yes | QMessageBox.No
                        )
                        
                        if reply == QMessageBox.Yes:
                            # 创建示例批量目录结构
                            # 视频示例
                            video_dir = dir_path / "video_example"
                            video_dir.mkdir(exist_ok=True)
                            logger.info(f"创建视频示例目录：{video_dir}")
                            
                            # 图文示例
                            image_dir = dir_path / "image_example"
                            image_dir.mkdir(exist_ok=True)
                            logger.info(f"创建图文示例目录：{image_dir}")
                                
                            QMessageBox.information(
                                self,
                                "提示",
                                "已创建示例目录结构：\n\n"
                                "1. 视频内容目录结构：\n"
                                "video_example/\n"
                                "  - 视频文件 (video.mp4)\n"
                                "  - 封面图片 (cover.jpg/png)\n"
                                "  - 描述文件 (desc.txt)\n\n"
                                "2. 图文内容目录结构：\n"
                                "image_example/\n"
                                "  - 图片文件 (*.jpg/*.png)\n"
                                "  - 描述文件 (desc.txt)"
                            )
                else:
                    # 单个发布模式：检查文件
                    video_files = list(dir_path.glob("*.mp4"))
                    image_files = list(dir_path.glob("*.jpg")) + list(dir_path.glob("*.png"))
                    desc_files = list(dir_path.glob("*.txt"))
                    
                    # 只有当目录非空但缺少必要文件时才提示
                    if any(dir_path.iterdir()) and not (video_files or image_files):
                        QMessageBox.information(
                            self,
                            "提示",
                            "请确保目录中包含以下文件：\n\n"
                            "1. 视频发布需要：\n"
                            "  - 视频文件 (*.mp4)\n"
                            "  - 封面图片 (*.jpg/*.png，可选)\n"
                            "  - 描述文件 (desc.txt)\n\n"
                            "2. 图文发布需要：\n"
                            "  - 图片文件 (*.jpg/*.png)\n"
                            "  - 描述文件 (desc.txt)"
                        )
                    elif (video_files or image_files) and not desc_files:
                        # 只有当有媒体文件但缺少描述文件时才提示
                        QMessageBox.warning(
                            self,
                            "提示",
                            "缺少描述文件 (desc.txt)，请添加。\n"
                            "描述文件格式：\n"
                            "第一行：标题\n"
                            "后续行：标签（每行一个，以#开头）"
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
            # 1. 检查配置管理器初始化状态
            if not self.config_manager or not hasattr(self.config_manager, 'config'):
                logger.error("配置管理器未正确初始化")
                QMessageBox.critical(self, "错误", "配置管理器未初始化，请重启应用")
                return False

            # 2. 从UI获取配置并更新到 GlobalConfig 对象
            config = self.config_manager.config
            config.base_dir = Path(self.dir_edit.text())
            config.batch_enabled = self.batch_checkbox.isChecked()
            logger.info(f"批量发布状态: {config.batch_enabled}")  # 添加日志
            
            # 更新平台配置
            for platform in ['douyin', 'xiaohongshu']:
                widgets = self.platform_widgets.get(platform)
                if widgets:
                    platform_config = getattr(config, platform)
                    platform_config.enabled = widgets['enabled_checkbox'].isChecked()
                    platform_config.cookie_path = widgets['cookie_edit'].text() or ""
                    platform_config.location = widgets['location_edit'].text() or ""
                    platform_config.schedule_enabled = widgets['schedule'].isChecked()

            # 3. 验证配置对象
            if not self.config_validator.validate_config(config):
                QMessageBox.warning(self, "警告", "配置验证失败")
                return False

            # 4. 保存配置并验证保存结果
            if not self.config_manager.save_config():
                QMessageBox.warning(self, "警告", "配置保存失败")
                return False

            logger.info("配置已成功保存")
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
                schedule_time = None
                
                if widgets['schedule'].isChecked():
                    schedule_time = widgets['time_picker'].dateTime().toPyDateTime()
                
                # 统一使用 upload_content 方法，根据 schedule_time 决定是否创建任务
                success = asyncio.run(self.upload_controller.upload_content(
                    platform=platform,
                    content_dir=content_dir,
                    schedule_time=schedule_time
                ))
                
                if success:
                    if schedule_time:
                        logger.info(f"已添加定时任务: {platform} - {schedule_time}")
                    else:
                        logger.info(f"{platform}平台上传成功")
                else:
                    QMessageBox.warning(self, "警告", f"操作失败：{platform}")
            
            # 刷新任务列表
            self.refresh_tasks()
                    
        except Exception as e:
            logger.error(f"上传失败: {e}")
            QMessageBox.critical(self, "错误", f"上传失败：{str(e)}")
            
    async def get_platform_cookie(self, platform_name):
        """获取平台cookie"""
        try:
            # 正确地将UI显示的平台名称转换为内部使用的平台键
            platform_key = "douyin" if platform_name == "抖音" else "xiaohongshu"
            
            # 获取平台配置
            widgets = self.platform_widgets.get(platform_key)
            if not widgets:
                QMessageBox.critical(self, "错误", f"未找到{platform_name}平台配置")
                return
            
            # 先询问用户输入账号名称
            account_name, ok = QInputDialog.getText(
                self, 
                f"输入{platform_name}账号", 
                "请输入账号名称（用于保存Cookie文件）:"
            )
            
            if not ok or not account_name:
                logger.info("用户取消了Cookie获取操作")
                return
            
            # 使用 PathManager 获取 cookie 路径
            cookie_path = PathManager.get_cookie_path(platform_key, account_name)
            
            # 更新UI显示
            widgets['cookie_edit'].setText(str(cookie_path))
            
            # 创建并启动工作线程
            self.cookie_worker = CookieWorker(platform_key, str(cookie_path))
            
            # 连接信号
            self.cookie_worker.progress.connect(lambda msg: logger.info(msg))
            self.cookie_worker.finished.connect(
                lambda success: self.on_cookie_generation_complete(success, platform_key)
            )
            
            # 禁用按钮防止重复点击
            widgets['get_cookie_button'].setEnabled(False)
            widgets['get_cookie_button'].setText("获取中...")
            
            # 启动线程
            self.cookie_worker.start()
            
        except Exception as e:
            logger.error(f"启动获取{platform_name} Cookie失败: {e}")
            QMessageBox.critical(self, "错误", f"启动获取Cookie失败: {str(e)}")

    @pyqtSlot(bool, str)
    def on_cookie_generation_complete(self, success, platform_key):
        """Cookie获取完成后的处理"""
        widgets = self.platform_widgets.get(platform_key)
        if not widgets:
            return
        
        # 恢复按钮状态
        widgets['get_cookie_button'].setEnabled(True)
        widgets['get_cookie_button'].setText("获取Cookie")
        
        if success:
            QMessageBox.information(self, "成功", f"成功获取{platform_key.capitalize()} Cookie")
        else:
            QMessageBox.warning(self, "警告", f"获取{platform_key.capitalize()} Cookie失败或被取消")

    def _get_platform_key(self, platform: str) -> str:
        """获取平台标识"""
        platform_map = {
            "抖音": "douyin",
            "小红书": "xiaohongshu"
        }
        return platform_map.get(platform, platform.lower())

    async def _get_account_name(self) -> Optional[str]:
        """异步获取账号名称"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, 
            lambda: QInputDialog.getText(
                self, 
                "输入账号", 
                "请输入账号名称（用于保存Cookie）:"
            )[0]
        )

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
        try:
            # 获取任务队列
            task_queue = self.upload_controller.task_queue
            if not task_queue:
                logger.error("任务队列未初始化")
                return
            
            # 清理任务
            task_queue.clear_completed_tasks()
            
            # 刷新任务列表
            self.refresh_tasks()
            
            QMessageBox.information(self, "成功", "已清理完成的任务")
            
        except Exception as e:
            logger.error(f"清理任务失败: {e}")
            QMessageBox.critical(self, "错误", f"清理任务失败: {str(e)}")
        
    def handle_close(self, event):
        """处理窗口关闭事件"""
        try:
            # 停止任务处理进程
            self.upload_controller.task_queue.stop()
            event.accept()
        except Exception as e:
            logger.error(f"关闭窗口时出错: {e}")
            event.accept()

    def start_task_processing(self):
        """启动任务处理"""
        try:
            # 确保控制器已初始化
            if self.upload_controller is None:
                logger.warning("等待控制器初始化...")
                QTimer.singleShot(100, self.start_task_processing)  # 延迟重试
                return
            
            if not hasattr(self.upload_controller, 'task_queue'):
                logger.error("任务队列未正确初始化")
                return
            
            # 启动任务队列处理
            self.upload_controller.task_queue.start()
            logger.info("任务处理已启动")
            
        except Exception as e:
            logger.error(f"启动任务处理失败: {e}")

    def get_cookie(self, platform: str):
        """获取平台Cookie的非异步入口方法"""
        try:
            # 确保从正确的位置导入PathManager
            from src.utils.paths import PathManager
            
            # 获取账号名称
            account_name, ok = QInputDialog.getText(
                self, 
                "输入账号", 
                "请输入账号名称（用于保存Cookie）:"
            )
            
            if not ok or not account_name:
                return False
            
            # 获取平台标识
            platform_key = self._get_platform_key(platform)
            
            # 生成cookie文件路径
            cookie_file = PathManager.get_cookie_path(platform_key, account_name)
            
            # 确保目录存在
            cookie_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 创建一个新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # 直接调用cookie生成函数
                if platform_key == "douyin":
                    from src.core.uploaders.douyin import douyin_cookie_gen
                    success = loop.run_until_complete(douyin_cookie_gen(str(cookie_file)))
                else:
                    from src.core.uploaders.xiaohongshu import xhs_cookie_gen
                    success = loop.run_until_complete(xhs_cookie_gen(str(cookie_file)))
                    
                if success:
                    # 更新UI
                    self._update_cookie_ui(platform_key, cookie_file)
                    QMessageBox.information(self, "成功", f"已成功获取{platform}账号 {account_name} 的Cookie")
                else:
                    QMessageBox.warning(self, "警告", f"获取{platform} Cookie失败")
                    
                return success
            finally:
                # 关闭事件循环
                loop.close()
                
        except Exception as e:
            logger.error(f"获取{platform} Cookie失败: {e}")
            QMessageBox.critical(self, "错误", f"获取Cookie失败: {str(e)}")
            return False

# 修改CookieWorker类，改进异常处理和监控逻辑
class CookieWorker(QThread):
    # 定义信号
    finished = pyqtSignal(bool)
    progress = pyqtSignal(str)
    
    def __init__(self, platform, cookie_path):
        super().__init__()
        self.platform = platform
        self.cookie_path = cookie_path
        
    def run(self):
        """在单独的线程中运行"""
        try:
            # 创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # 确保目录存在
            cookie_dir = os.path.dirname(self.cookie_path)
            os.makedirs(cookie_dir, exist_ok=True)
            
            self.progress.emit(f"开始获取{self.platform} Cookie，请在弹出的浏览器中登录")
            
            # 定义一个包装函数来处理超时和取消
            async def run_with_timeout(coro, timeout=360):
                try:
                    return await asyncio.wait_for(coro, timeout=timeout)
                except asyncio.TimeoutError:
                    self.progress.emit("操作超时")
                    return False
                except asyncio.CancelledError:
                    self.progress.emit("操作被取消")
                    return False
                except Exception as e:
                    if "has been closed" in str(e):
                        self.progress.emit("浏览器已被关闭")
                    else:
                        self.progress.emit(f"发生错误: {str(e)}")
                    return False
            
            # 根据平台选择不同的cookie生成器
            if self.platform == 'douyin':
                from src.core.uploaders.douyin import douyin_cookie_gen
                result = loop.run_until_complete(
                    run_with_timeout(douyin_cookie_gen(self.cookie_path))
                )
            elif self.platform == 'xiaohongshu':
                from src.core.uploaders.xiaohongshu import xhs_cookie_gen
                result = loop.run_until_complete(
                    run_with_timeout(xhs_cookie_gen(self.cookie_path))
                )
            else:
                self.progress.emit(f"不支持的平台: {self.platform}")
                result = False
                
            # 发送结果信号
            self.finished.emit(result)
            
        except Exception as e:
            import traceback
            logger.error(f"获取{self.platform} Cookie失败: {e}\n{traceback.format_exc()}")
            self.progress.emit(f"获取Cookie时发生错误: {e}")
            self.finished.emit(False)
        finally:
            try:
                # 确保事件循环被安全关闭
                pending_tasks = asyncio.all_tasks(loop)
                for task in pending_tasks:
                    task.cancel()
                
                if not loop.is_closed():
                    # 尝试运行一次loop以处理取消的任务
                    loop.run_until_complete(asyncio.sleep(0))
                    loop.close()
            except Exception as e:
                logger.error(f"清理事件循环时出错: {e}")