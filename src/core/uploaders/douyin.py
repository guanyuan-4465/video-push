# -*- coding: utf-8 -*-
from datetime import datetime
from pathlib import Path
import random
import os
import asyncio

from playwright.async_api import Playwright, async_playwright, Page
from src.utils.log import logger
from src.utils.constant import FileTypes
from src.core.uploaders.base import BaseUploader

# 将函数移到类外部，作为独立函数
async def douyin_cookie_gen(cookie_path: str) -> bool:
    """使用 playwright 获取抖音 cookie"""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            
            # 访问登录页面
            await page.goto("https://creator.douyin.com/")
            logger.info("请使用抖音APP扫码登录...")
            
            # 等待登录成功后跳转
            try:
                # 使用显式等待而不是循环，简化代码
                await page.wait_for_url(
                    "https://creator.douyin.com/creator-micro/home",
                    timeout=300000  # 5分钟超时
                )
                logger.info("检测到登录成功")
                
                # 保存 cookies
                await context.storage_state(path=cookie_path)
                logger.info(f"Cookie 已保存到: {cookie_path}")
                
                # 验证 cookie
                await page.goto("https://creator.douyin.com/creator-micro/content/upload")
                if "login" in page.url:
                    raise Exception("Cookie 验证失败")
                    
                logger.info("Cookie 获取并验证成功！")
                return True
                
            except Exception as e:
                # 专门处理页面关闭/超时错误
                if "Target page, context or browser has been closed" in str(e):
                    logger.warning("浏览器已关闭，Cookie获取已取消")
                elif "Timeout" in str(e):
                    logger.warning("登录超时，请重试")
                else:
                    logger.error(f"登录过程中出错: {str(e)}")
                return False
                
    except Exception as e:
        logger.error(f"获取 Cookie 失败: {str(e)}")
        if os.path.exists(cookie_path):
            try:
                os.remove(cookie_path)
            except Exception:
                pass
        return False

class DouyinUploader(BaseUploader):
    def __init__(self, title, file_path, tags, publish_date, account_file, thumbnail_path=None, location=None):
        super().__init__(title, file_path, tags, publish_date, account_file, thumbnail_path, location)
        self.file_type = self._get_file_type()  # 使用方法而不是直接判断

    def _get_file_type(self):
        """判断文件类型"""
        suffix = Path(self.file_path).suffix.lower()
        if suffix in FileTypes.VIDEO_EXTENSIONS:
            return "video"
        elif suffix in FileTypes.IMAGE_EXTENSIONS:
            return "image"
        else:
            raise ValueError(f"不支持的文件类型: {suffix}")

    async def validate_cookie(self) -> bool:
        """验证cookie是否有效"""
        try:
            if not os.path.exists(self.account_file):
                logger.warning(f"Cookie文件不存在: {self.account_file}")
                return False
                
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                context = await browser.new_context(storage_state=self.account_file)
                page = await context.new_page()
                
                try:
                    await page.goto("https://creator.douyin.com/creator-micro/content/upload")
                    await page.wait_for_url("https://creator.douyin.com/creator-micro/content/upload", timeout=5000)
                    
                    if await page.get_by_text('手机号登录').count():
                        return False
                        
                    return True
                    
                finally:
                    await context.close()
                    await browser.close()
                    
        except Exception as e:
            logger.error(f"验证Cookie时发生错误: {str(e)}")
            return False

    async def generate_cookie(self) -> bool:
        """生成新的cookie"""
        try:
            cookie_dir = Path(self.account_file).parent
            cookie_dir.mkdir(parents=True, exist_ok=True)
            
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=False)
                context = await browser.new_context(viewport=None, no_viewport=True)
                page = await context.new_page()
                
                await page.set_viewport_size({'width': 1920, 'height': 1080})
                
                # 访问登录页面
                await page.goto("https://creator.douyin.com/")
                logger.info("请使用抖音APP扫码登录...")
                
                # 等待用户扫码登录
                await page.wait_for_url(
                    "https://creator.douyin.com/creator-micro/home", 
                    timeout=60000  # 1分钟超时
                )
                
                # 保存cookie
                await context.storage_state(path=self.account_file)
                logger.debug("登录成功，正在保存Cookie...")
                
                # 验证cookie
                await page.goto("https://creator.douyin.com/creator-micro/content/upload")
                try:
                    await page.wait_for_url("https://creator.douyin.com/creator-micro/content/upload", timeout=5000)
                    if await page.get_by_text('手机号登录').count():
                        raise Exception("Cookie验证失败")
                    logger.info("Cookie获取并验证成功！")
                    return True
                except Exception as e:
                    raise Exception(f"Cookie验证失败: {str(e)}")
                    
        except Exception as e:
            logger.error(f"获取Cookie失败: {str(e)}")
            if os.path.exists(self.account_file):
                os.remove(self.account_file)
            return False

    async def upload(self, playwright: Playwright) -> bool:
        """执行上传操作"""
        browser = None
        context = None
        try:
            browser = await playwright.chromium.launch(headless=False)
            context = await browser.new_context(storage_state=self.account_file)
            page = await context.new_page()
            
            # 访问抖音创作者页面
            await page.goto("https://creator.douyin.com/creator-micro/content/upload")
            await asyncio.sleep(random.uniform(0.5, 1.0))
            logger.info(f'[+]正在上传-------{self.title}')
            
            # 等待页面加载完成
            await page.wait_for_load_state("load")
            await asyncio.sleep(random.uniform(0.1, 0.5))
            logger.info('[+]页面加载完成')
            
            # 根据文件类型选择上传模式
            await self._select_upload_mode(page)
            
            # 上传文件
            await self._upload_file(page)
            
            # 设置标题和标签
            await self._set_title_and_tags(page)
            
            # 设置封面
            if self.thumbnail_path:
                await self.set_thumbnail(page, self.thumbnail_path)
            
            # 如果配置了地点，则设置地点
            if self.location:
                await self.set_location(page, self.location)
                logger.info(f"已设置发布地点: {self.location}")
            
            # 发布
            await self._publish(page, context)
            
            return True
            
        except Exception as e:
            logger.error(f"抖音上传失败: {e}")
            return False
            
        finally:
            if context:
                await context.close()
            if browser:
                await browser.close()

    async def _select_upload_mode(self, page: Page):
        """选择上传模式"""
        try:
            # 1. 获取文件类型并选择对应模式
            file_type = self._get_file_type()
            mode_text = "发布视频" if file_type == "video" else "发布图文"
            logger.info(f'  [-] 文件类型: {file_type}, 选择模式: {mode_text}')
            
            # 2. 点击对应的模式
            await page.locator(f'text={mode_text}').click()
            await asyncio.sleep(random.uniform(1.0, 1.5))
            
            # 3. 在激活的面板中定位上传区域
            upload_area = page.locator('div[role="tab-panel"][aria-hidden="false"] div[class*="container-drag-info-Tl0RGH"]')
            await upload_area.wait_for(state="visible")
            await upload_area.click()
            logger.info(f'  [-] 已点击{mode_text}上传区域')
            
        except Exception as e:
            logger.error(f"选择上传模式失败: {str(e)}")
            raise

    async def _upload_file(self, page: Page):
        """上传文件"""
        try:
            # 根据文件类型选择对应的文件上传输入框
            file_type = self._get_file_type()
            if file_type == "video":
                # 视频上传输入框
                file_input = page.locator('div[role="tab-panel"][aria-hidden="false"] input[accept*="video"]')
            else:
                # 图片上传输入框
                file_input = page.locator('div[role="tab-panel"][aria-hidden="false"] input[accept*="image"]')
            
            await file_input.wait_for(state="attached")
            
            if file_type == "video":
                await file_input.set_input_files(self.file_path)
            else:
                # 对于图片上传，可能有多个文件
                if isinstance(self.file_path, list):
                    await file_input.set_input_files(self.file_path)
                else:
                    await file_input.set_input_files([self.file_path])
                
            logger.info(f'  [-] 已上传{file_type}文件')
            
        except Exception as e:
            logger.error(f"文件上传失败: {str(e)}")
            raise

    async def _set_title_and_tags(self, page: Page):
        """设置标题和标签"""
        await asyncio.sleep(1)
        logger.info(f'  [-] 正在填充标题和话题...')
        
        if self.file_type == "image":
            # 图文编辑界面的标题和话题设置
            editor = page.locator('.ace-line')  # 定位编辑器区域
            if await editor.count():
                await editor.click()
                await page.keyboard.type(f"{self.title}\n")  # 输入标题并换行
                
                # 添加话题
                for tag in self.tags:
                    await page.keyboard.type(f"#{tag} ")
                
                logger.success(f'  [-] 标题和话题添加完成，共添加{len(self.tags)}个话题')
            else:
                raise Exception("未找到图文编辑区域")
        else:
            # 视频上传的标题和话题设置
            # 填充标题
            title_container = page.get_by_text('作品标题').locator("..").locator("xpath=following-sibling::div[1]").locator("input")
            if await title_container.count():
                await title_container.click()
                await page.keyboard.press("Control+KeyA")
                await page.keyboard.press("Delete")
                await title_container.fill(self.title[:30])
            else:
                titlecontainer = page.locator(".notranslate")
                await titlecontainer.click()
                await page.keyboard.press("Backspace")
                await page.keyboard.press("Control+KeyA")
                await page.keyboard.press("Delete")
                await page.keyboard.type(self.title)
                await page.keyboard.press("Enter")
            
            # 填充话题
            css_selector = ".zone-container"
            logger.info(f'  [-] 开始添加话题，共{len(self.tags)}个...')
            for index, tag in enumerate(self.tags, start=1):
                await page.type(css_selector, f"#{tag}")
                await page.press(css_selector, "Space")
                logger.info(f'  [-] 已添加第{index}个话题: #{tag}')
            
            await asyncio.sleep(0.5)
            logger.success(f'  [-] 标题和话题添加完成，共添加{len(self.tags)}个话题')

    async def set_thumbnail(self, page: Page, thumbnail_path: str):
        """设置视频封面"""
        try:
            if thumbnail_path:
                # 点击选择封面
                await page.click('text="选择封面"')
                await page.wait_for_selector("div.semi-modal-content:visible")
                
                # 点击设置竖封面
                await page.click('text="设置竖封面"')
                await page.wait_for_timeout(2000)  # 等待2秒
                
                # 上传封面文件
                await page.locator("div[class^='semi-upload upload'] >> input.semi-upload-hidden-input").set_input_files(thumbnail_path)
                await page.wait_for_timeout(2000)  # 等待2秒
                
                # 点击完成按钮 - 使用更精确的选择器
                complete_button = page.locator('button.semi-button-primary:has-text("完成")')
                await complete_button.wait_for(state="visible", timeout=5000)  # 等待按钮可见
                await complete_button.click()
                logger.info('  [-] 已完成封面设置')
                
        except Exception as e:
            logger.error(f"设置视频封面失败: {str(e)}")
            raise

    async def set_location(self, page: Page, location: str):
        """设置地区"""
        try:
            if self.file_type == "image":
                # 图文界面的地区设置
                location_selector = page.locator('div.semi-select span:has-text("输入相关位置，让更多人看到你的作品")').filter(
                    has_text="输入相关位置"
                ).first
            else:
                # 视频界面的地区设置
                location_selector = page.locator('div.semi-select span:has-text("输入地理位置")').first
            
            if await location_selector.count():
                await location_selector.click()
                await asyncio.sleep(random.uniform(0.5,1))
                
                # 输入地区
                await page.keyboard.type(location)
                await asyncio.sleep(random.uniform(0.5,1))
                
                # 等待并选择第一个选项
                await page.wait_for_selector('div[role="listbox"] [role="option"]', timeout=5000)
                first_option = page.locator('div[role="listbox"] [role="option"]').first
                if await first_option.count():
                    await first_option.click()
                    logger.info(f"已选择地区: {location}")
                else:
                    logger.warning("未找到匹配的地区选项")
            else:
                logger.warning("未找到地区输入框")
                
            await asyncio.sleep(random.uniform(0.5,1))
            
        except Exception as e:
            logger.error(f"设置地区时出错: {str(e)}")
            # 不抛出异常，允许地区设置失败
            pass

    async def _publish(self, page: Page, context):
        """发布内容"""
        try:
            max_retries = 3
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    publish_button = page.get_by_role('button', name="发布", exact=True)
                    if await publish_button.count():
                        await publish_button.click()
                        
                    # 等待跳转到管理页面
                    await page.wait_for_url(
                        "https://creator.douyin.com/creator-micro/content/manage**",
                        timeout=5000
                    )
                    logger.success("  [-]内容发布成功")
                    break
                except Exception as e:
                    retry_count += 1
                    if retry_count >= max_retries:
                        logger.error(f"发布失败: {str(e)}")
                        raise
                    logger.info("  [-] 正在发布中...")
                    await asyncio.sleep(random.uniform(0.5,1))
            
            # 更新cookie
            await context.storage_state(path=self.account_file)
            logger.success('  [-]cookie更新完毕！')
            await asyncio.sleep(random.uniform(0.5,1))
            
        except Exception as e:
            logger.error(f"发布过程出错: {str(e)}")
            raise

    with logger.contextualize(platform="douyin"):
        logger.info("开始获取 Cookie")
        # Cookie 获取过程
        logger.info("Cookie 获取完成")