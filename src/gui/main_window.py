from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QLineEdit, QCheckBox,
    QTabWidget, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt
from pathlib import Path
from src.config.base_config import ConfigManager, PlatformConfig, GlobalConfig
from src.utils.log import logger
from src.utils.paths import PathManager

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        # 初始化平台相关的控件
        self.platform_widgets = {
            'douyin': {},
            'xiaohongshu': {}
        }
        self.init_ui()
        
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
        
        # Cookie设置
        cookie_group = QWidget()
        cookie_layout = QHBoxLayout(cookie_group)
        cookie_layout.addWidget(QLabel("Cookie文件:"))
        cookie_edit = QLineEdit()
        cookie_layout.addWidget(cookie_edit)
        cookie_button = QPushButton("选择...")
        cookie_layout.addWidget(cookie_button)
        
        # 定时发布设置
        schedule_group = QWidget()
        schedule_layout = QHBoxLayout(schedule_group)
        schedule_checkbox = QCheckBox("启用定时发布")
        schedule_layout.addWidget(schedule_checkbox)
        
        # 保存控件引用到字典中 - 移到这里，确保所有控件都已创建
        self.platform_widgets[platform.lower()] = {
            'enabled_checkbox': enabled_checkbox,
            'cookie_edit': cookie_edit,
            'cookie_button': cookie_button,
            'schedule': schedule_checkbox
        }
        
        # 设置按钮点击事件
        platform_name = platform
        cookie_button.clicked.connect(
            lambda checked, name=platform_name: self.browse_file(f"{name} Cookie文件", "*.json", name.lower())
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
        """浏览选择文件
        Args:
            title: 文件选择对话框标题
            filter: 文件过滤器（如 "*.json"）
            platform: 平台标识（'douyin' 或 'xiaohongshu'）
        """
        file, _ = QFileDialog.getOpenFileName(
            self, 
            title,
            "",  # 不设置默认路径，让用户自由选择
            filter
        )
        
        if file:
            try:
                # 直接使用用户选择的文件路径
                self.platform_widgets[platform]['cookie_edit'].setText(file)
                logger.info(f"已选择 {platform} 的 cookie 文件：{file}")
                
                # 可以在这里进行简单的文件格式验证
                with open(file, 'r', encoding='utf-8') as f:
                    import json
                    json.load(f)  # 验证是否为有效的 JSON 文件
                    
            except json.JSONDecodeError:
                logger.error(f"选择的文件不是有效的 JSON 文件：{file}")
                QMessageBox.critical(self, "错误", "请选择有效的 JSON 格式的 cookie 文件")
                self.platform_widgets[platform]['cookie_edit'].clear()
            except Exception as e:
                logger.error(f"读取文件失败：{str(e)}")
                QMessageBox.critical(self, "错误", f"读取文件失败：{str(e)}")
                self.platform_widgets[platform]['cookie_edit'].clear()
    
    def save_config(self):
        """保存配置"""
        try:
            # 基础配置
            config = GlobalConfig(
                base_dir=Path(self.dir_edit.text()) if self.dir_edit.text() else None,
                batch_enabled=self.batch_checkbox.isChecked()
            )
            
            # 平台配置
            for platform in ['douyin', 'xiaohongshu']:
                widgets = self.platform_widgets.get(platform, {})
                if widgets.get('enabled_checkbox') and widgets['enabled_checkbox'].isChecked():
                    platform_config = PlatformConfig(
                        enabled=True,
                        cookie_path=Path(widgets['cookie_edit'].text()) if widgets['cookie_edit'].text() else None,
                        schedule_enabled=widgets.get('schedule', QCheckBox()).isChecked()
                    )
                    setattr(config, platform, platform_config)
            
            self.config_manager.config = config
            self.config_manager.save_config()
            logger.info("配置已保存")
            QMessageBox.information(self, "成功", "配置保存成功！")
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            QMessageBox.critical(self, "错误", f"保存配置失败：{str(e)}")
    
    def start_upload(self):
        """开始上传"""
        try:
            self.save_config()
            self.config_manager.validate_config()
            
            contents = self.config_manager.scan_content_dirs()
            enabled_platforms = self.config_manager.config.get_enabled_platforms()
            
            for platform in enabled_platforms:
                # 获取对应的上传器
                uploader = self.get_uploader(platform)
                
                # 执行上传
                for content in contents:
                    uploader.upload(content)
                
            QMessageBox.information(self, "成功", f"已开始上传 {len(contents)} 个内容到 {len(enabled_platforms)} 个平台！")
        except Exception as e:
            logger.error(f"上传失败：{str(e)}")
            QMessageBox.critical(self, "错误", f"上传失败：{str(e)}")