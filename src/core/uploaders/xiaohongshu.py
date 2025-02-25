import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright
import os
from datetime import datetime

from conf import BASE_DIR
from src.utils.base_social_media import set_init_script
from src.utils.log import logger
from src.core.uploaders.base import BaseUploader

async def xhs_cookie_gen(account_file):
    """使用 playwright 获取小红书 cookie"""
    async with async_playwright() as playwright:
        # 启动浏览器，设置为有界面模式
        browser = await playwright.chromium.launch(headless=False)
        context = await browser.new_context()
        # 添加 stealth.min.js 以绕过检测
        context = await set_init_script(context)
        
        # 创建新页面
        page = await context.new_page()
        
        try:
            # 访问小红书登录页面
            logger.info("正在打开小红书登录页面...")
            await page.goto("https://creator.xiaohongshu.com/login?selfLogout=true")
            
            # 等待用户手动登录
            logger.info("请在浏览器中完成登录操作...")
            
            # 等待登录成功后跳转
            logger.info("等待登录完成...")
            # 修改这里的等待方式
            success = False
            timeout = 300  # 5分钟超时
            start_time = asyncio.get_event_loop().time()
            
            while not success and (asyncio.get_event_loop().time() - start_time) < timeout:
                current_url = page.url
                if (current_url.startswith("https://creator.xiaohongshu.com/new/home") or 
                    current_url.startswith("https://www.xiaohongshu.com/explore")):
                    success = True
                    break
                await asyncio.sleep(1)
            
            if not success:
                raise TimeoutError("登录超时，请重试")
            
            # 获取所有 cookies
            logger.info("登录成功，正在获取 cookies...")
            cookies = await context.cookies()
            
            # 确保 cookies 目录存在
            cookie_dir = Path(account_file).parent
            cookie_dir.mkdir(parents=True, exist_ok=True)
            
            # 保存 cookies 到文件
            with open(account_file, 'w', encoding='utf-8') as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            
            logger.success(f"Cookie 已保存到: {account_file}")
            return True
            
        except Exception as e:
            logger.error(f"获取 cookie 失败: {str(e)}")
            return False
            
        finally:
            # 关闭浏览器
            await context.close()
            await browser.close()

async def cookie_auth(account_file):
    """验证 cookie 是否有效且能访问创作平台"""
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=False)
        context = await browser.new_context()
        context = await set_init_script(context)
        
        try:
            # 加载已保存的 cookies
            with open(account_file, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            await context.add_cookies(cookies)
            
            # 创建新页面并直接访问创作平台
            page = await context.new_page()
            logger.info("正在验证小红书创作平台访问权限...")
            
            # 访问创作平台
            await page.goto("https://creator.xiaohongshu.com/new/home")
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)
            
            # 检查是否需要重新登录
            if "login" in page.url:
                logger.error("Cookie 已失效，需要重新登录")
                return False
            
            # 检查是否能访问创作平台（检查发布按钮）
            try:
                # 等待发布图文和视频按钮出现
                selectors = [
                    'div[class*="publish-card"]:has-text("发布图文笔记")', 
                    'div[class*="publish-card"]:has-text("发布视频笔记")'
                ]
                
                for selector in selectors:
                    element = page.locator(selector)
                    await element.wait_for(state='visible', timeout=5000)  # 等待按钮可见
                    if await element.count() == 0:
                        logger.error(f"无法找到发布按钮: {selector}")
                        return False
                
                logger.success("成功访问创作平台，发布功能可用")
                return True
                
            except Exception as e:
                logger.error(f"无法找到发布按钮: {str(e)}")
                return False
            
        except Exception as e:
            logger.error(f"验证创作平台访问权限时出错: {str(e)}")
            return False
        finally:
            await context.close()
            await browser.close()

async def xhs_setup(account_file, handle=False):
    """设置小红书登录并验证创作平台访问权限"""
    account_file = Path(account_file)
    
    if not account_file.exists() or not await cookie_auth(account_file):
        if not handle:
            logger.error("Cookie 文件不存在或已失效")
            return False
            
        logger.info("准备重新登录小红书...")
        success = await xhs_cookie_gen(account_file)
        if not success:
            return False
            
        # 再次验证
        if await cookie_auth(account_file):
            logger.success("登录成功且可以访问创作平台")
            return True
        else:
            logger.error("登录成功但无法访问创作平台，请确认是否有创作者权限")
            return False
    
    return True

class XiaohongshuUploader(BaseUploader):
    def __init__(self, title, file_path, tags, publish_date, account_file, thumbnail_path=None):
        super().__init__(title, file_path, tags, publish_date, account_file, thumbnail_path)
        self.file_type = self._get_file_type()

    async def validate_cookie(self) -> bool:
        """验证cookie是否有效"""
        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                context = await browser.new_context()
                context = await set_init_script(context)
                
                # 加载 cookies
                with open(self.account_file, 'r', encoding='utf-8') as f:
                    cookies = json.load(f)
                await context.add_cookies(cookies)
                
                page = await context.new_page()
                await page.goto("https://creator.xiaohongshu.com/new/home")
                
                return "login" not in page.url
                
        except Exception as e:
            logger.error(f"验证Cookie失败: {str(e)}")
            return False

    async def generate_cookie(self) -> bool:
        """生成新的cookie"""
        return await xhs_cookie_gen(self.account_file)

    def _get_file_type(self):
        """根据文件后缀判断类型"""
        video_extensions = {'.mp4', '.mov', '.avi'}
        image_extensions = {'.jpg', '.jpeg', '.png'}
        file_ext = Path(self.file_path).suffix.lower()
        
        if file_ext in video_extensions:
            return "video"
        elif file_ext in image_extensions:
            return "image"
        else:
            raise ValueError(f"不支持的文件类型: {file_ext}")

    def _get_description(self):
        """从文件中读取描述内容"""
        try:
            # 获取视频文件的路径
            video_path = Path(self.file_path)
            # 构造描述文件路径（与视频文件同名，但后缀为.txt）
            description_file = video_path.with_suffix('.txt')
            
            if description_file.exists():
                with open(description_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    logger.info(f"已读取描述文件: {description_file}")
                    return content
            else:
                logger.warning(f"未找到描述文件: {description_file}")
                return "输入正文描述，真诚有价值的分享才入温暖"  # 默认描述文本
            
        except Exception as e:
            logger.error(f"读取描述文件失败: {str(e)}")
            return "输入正文描述，真诚有价值的分享才入温暖"  # 出错时返回默认描述文本

    async def upload(self, playwright):
        """上传内容到小红书"""
        browser = await playwright.chromium.launch(headless=False)
        context = await browser.new_context()
        context = await set_init_script(context)
        
        try:
            # 加载 cookies
            with open(self.account_file, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            await context.add_cookies(cookies)
            
            page = await context.new_page()
            
            # 访问创作平台主页
            await page.goto("https://creator.xiaohongshu.com/new/home")
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)
            
            # 检查是否需要重新登录
            if "login" in page.url:
                logger.error("Cookie 已失效，需要重新登录")
                raise Exception("Cookie 已失效，请重新登录")
            
            logger.info(f'[+]正在上传{self.file_type}-------{self.title}')
            
            # 根据文件类型选择发布按钮
            if self.file_type == "video":
                await self._select_video_mode(page)
            else:
                await self._select_image_mode(page)
            
            # 上传文件
            await self._upload_file(page)
            
            # 设置标题和标签
            await self._set_title_and_tags(page)
            
            # 如果是视频且有缩略图，则上传缩略图
            if self.file_type == "video" and self.thumbnail_path and Path(self.thumbnail_path).exists():
                logger.info(f"检测到缩略图：{self.thumbnail_path}")
                await self._upload_thumbnail(page)
            
            # 发布
            await self._publish(page, context)
            
        except Exception as e:
            logger.error(f"上传过程出错: {str(e)}")
            raise
        finally:
            await asyncio.sleep(2)
            await context.close()
            await browser.close()

    async def _select_video_mode(self, page):
        """选择视频上传模式"""
        try:
            button = page.locator('div[class*="publish-card"]:has-text("发布视频笔记")')
            await button.wait_for(state='visible', timeout=5000)
            await button.scroll_into_view_if_needed()
            await button.click()
            await asyncio.sleep(1)
            
            # 验证是否跳转到正确的上传页面
            expected_url = "https://creator.xiaohongshu.com/publish/publish"
            if not page.url.startswith(expected_url):
                raise Exception(f"页面跳转失败，当前URL: {page.url}")
            
        except Exception as e:
            logger.error(f"选择视频模式失败: {str(e)}")
            raise

    async def _select_image_mode(self, page):
        """选择图文上传模式"""
        try:
            button = page.locator('div[class*="publish-card"]:has-text("发布图文笔记")')
            await button.wait_for(state='visible', timeout=5000)
            await button.scroll_into_view_if_needed()
            await button.click()
            await asyncio.sleep(1)
            
            # 验证是否跳转到正确的上传页面
            expected_url = "https://creator.xiaohongshu.com/publish/publish"
            if not page.url.startswith(expected_url):
                raise Exception(f"页面跳转失败，当前URL: {page.url}")
            
        except Exception as e:
            logger.error(f"选择图文模式失败: {str(e)}")
            raise

    async def _upload_file(self, page):
        """上传文件"""
        try:
            logger.info("等待文件选择器出现...")
            
            # 等待文件选择器出现并上传
            if self.file_type == "video":
                file_input = page.locator('input[type="file"]')
            else:
                # 图片上传使用特定的选择器
                file_input = page.locator('div.upload-wrapper input[type="file"], input[type="file"][accept="image/*"]')
            
            await file_input.wait_for(state='attached', timeout=10000)
            await file_input.set_input_files(self.file_path)
            
            logger.info("文件上传中...")
            
            # 等待上传完成
            max_wait_time = 60  # 秒
            start_time = asyncio.get_event_loop().time()
            
            while True:
                if asyncio.get_event_loop().time() - start_time > max_wait_time:
                    raise TimeoutError("上传超时")
                
                try:
                    # 根据文件类型检查上传完成状态
                    if self.file_type == "video":
                        # 视频上传成功检查
                        success = await page.locator('div:has-text("视频上传成功")').count() > 0
                    else:
                        # 图片上传成功检查
                        success = (
                            await page.locator('div:has-text("图片上传成功")').count() > 0 or
                            await page.locator('img[src*="http"]').count() > 0 or  # 检查是否有已上传的图片
                            await page.locator('div.image-container img').count() > 0  # 检查预览图
                        )
                    
                    if success:
                        logger.success(f"{self.file_type}上传完成")
                        # 图片上传后等待预览加载
                        if self.file_type == "image":
                            await asyncio.sleep(2)
                        break
                    
                except Exception as e:
                    logger.warning(f"检查上传状态时出错: {str(e)}")
                
                await asyncio.sleep(1)
                logger.info("等待上传完成...")
            
        except Exception as e:
            logger.error(f"上传出错: {str(e)}")
            # 保存错误截图以便调试
            try:
                await page.screenshot(path=f"error_{self.file_type}_upload.png")
            except:
                pass
            raise

        # 上传完成后额外等待
        await asyncio.sleep(2)

    def count_length_with_emoji(self, text):
        """计算字符串长度，将表情符号计算为2个字符"""
        length = 0
        i = 0
        while i < len(text):
            # 获取当前字符的Unicode码点
            char = text[i]
            code_point = ord(char)
            
            # 检查是否是表情符号（包括组合表情符号）
            if code_point >= 0x10000 or (0xD800 <= code_point <= 0xDBFF):
                length += 2  # 表情符号计为2个字符
                # 如果是代理对（surrogate pair），跳过下一个字符
                if 0xD800 <= code_point <= 0xDBFF:
                    i += 2
                    continue
            else:
                length += 1  # 普通字符计为1个字符
            i += 1
        return length

    async def _set_title_and_tags(self, page):
        """设置标题、正文描述和标签"""
        try:
            logger.info("正在设置标题、正文描述和标签...")
            
            # 设置标题
            title_input = page.locator('div.d-input input.d-text[type="text"]')
            await title_input.wait_for(state='visible', timeout=5000)
            await title_input.click()
            await asyncio.sleep(0.5)
            
            # 清除默认内容
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Backspace")
            await asyncio.sleep(0.5)
            
            # 处理标题，确保不超过20个字符
            title = self.title
            current_length = self.count_length_with_emoji(title)
            if current_length > 20:
                truncated_title = ""
                for i in range(len(title)):
                    temp_title = title[:i+1]
                    if self.count_length_with_emoji(temp_title) > 20:
                        truncated_title = title[:i]
                        break
                    truncated_title = temp_title
                
                logger.warning(f"标题超过20个字符，已自动截断。原标题: {self.title}")
                logger.warning(f"截断后标题: {truncated_title}")
                title = truncated_title
            
            await title_input.type(title, delay=50)
            await asyncio.sleep(0.5)
            
            # 设置正文描述
            description = self._get_description()  # 从文件中读取描述内容
            content_input = page.locator('div.ql-editor.ql-blank[contenteditable="true"]')
            await content_input.wait_for(state='visible', timeout=5000)
            await content_input.click()
            await asyncio.sleep(0.5)
            
            # 清除默认内容
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Backspace")
            await asyncio.sleep(0.5)
            
            # 使用 type 方法输入正文
            await content_input.type(description, delay=50)
            await asyncio.sleep(0.5)
            
            
        except Exception as e:
            logger.error(f"设置标题、正文描述和标签失败: {str(e)}")
            raise

    async def _set_schedule_time(self, page, publish_date):
        """设置定时发布时间"""
        try:
            logger.info("正在设置定时发布...")
            
            # 点击定时发布选项
            schedule_button = page.locator('label:has-text("定时发布")')
            await schedule_button.click()
            await asyncio.sleep(1)  # 等待切换完成
            
            # 使用 force 选项点击时间选择器，避免被其他元素遮挡
            date_picker = page.locator('input[class*="el-input__inner"][type="text"][placeholder="选择日期和时间"]')
            await date_picker.wait_for(state='visible', timeout=50000)
            await date_picker.click(force=True)  # 添加 force=True
            await asyncio.sleep(0.5)
            
            # 清除默认时间
            await date_picker.press("Control+A")
            await date_picker.press("Backspace")
            await asyncio.sleep(0.5)
            
            # 输入定时发布时间
            schedule_time = publish_date.strftime("%Y-%m-%d %H:%M")
            await date_picker.type(schedule_time, delay=50)
            await asyncio.sleep(0.5)
            
            # 按回车确认时间
            await date_picker.press("Enter")
            await asyncio.sleep(0.5)
            
            logger.success(f"定时发布时间设置完成: {schedule_time}")
            
        except Exception as e:
            logger.error(f"设置定时发布失败: {str(e)}")
            raise

    async def _add_location(self, page):
        """添加地点"""
        try:
            logger.info("正在添加地点...")
            
            # 等待页面加载完成
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(0.5)
            
            # 1. 直接点击显示"添加地点"的占位符文本
            placeholder = page.locator('div.d-text.d-select-placeholder:has-text("添加地点")')
            if await placeholder.count() == 1:
                await placeholder.click()
                logger.info("点击添加地点")
                await asyncio.sleep(0.5)
                
                # 2. 输入地点
                location = "厦门市"
                await page.keyboard.type(location, delay=50)
                logger.info(f"输入地点: {location}")
                await asyncio.sleep(0.8)
                
                # 3. 直接选择第一个选项
                try:
                    first_option = page.locator('div.d-popover-default div.name[data-v-09078844]').first
                    await first_option.click()
                    logger.info("选择第一个地点选项")
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"选择地点选项失败: {str(e)}")
                    await page.screenshot(path="location_selection_error.png")
                    raise
            else:
                logger.error("未找到添加地点选项")
                await page.screenshot(path="no_location_placeholder.png")
                raise Exception("未找到添加地点选项")
            
        except Exception as e:
            logger.error(f"添加地点失败: {str(e)}")
            try:
                await page.screenshot(path="error_location.png")
            except:
                pass
            raise

    async def _upload_thumbnail(self, page):
        """上传缩略图"""
        try:
            logger.info("正在设置视频封面...")
            
            # 等待页面加载完成
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)
            
            # 1. 点击第一个"上传封面"按钮
            upload_cover_selectors = [
                'div[class="column center noCover pointer uploadCover"]',
                'div.uploadCover',
                'div[class*="uploadCover"]',
                'div.text:has-text("上传封面")'
            ]
            
            upload_button = None
            for selector in upload_cover_selectors:
                try:
                    button = page.locator(selector)
                    if await button.count() > 0:
                        upload_button = button
                        logger.info(f"找到上传封面按钮: {selector}")
                        break
                except Exception:
                    continue
            
            if not upload_button:
                logger.error("未找到上传封面按钮")
                await page.screenshot(path="debug_thumbnail.png")
                raise Exception("无法找到上传封面按钮")
            
            await upload_button.click()
            await asyncio.sleep(2)
            
            # 2. 点击"上传封面"标签页
            tab_selectors = [
                'h6.d-text.--color-static.--color-text-paragraph.--size-text-h6.d-tabs-header-label:has-text("上传封面")',
                'div.d-tabs-header h6:has-text("上传封面")',
                'h6[class*="d-text"]:has-text("上传封面")'
            ]
            
            upload_tab = None
            for selector in tab_selectors:
                try:
                    tab = page.locator(selector)
                    if await tab.count() > 0:
                        upload_tab = tab
                        logger.info(f"找到上传封面标签: {selector}")
                        break
                except Exception:
                    continue
            
            if upload_tab:
                await upload_tab.click()
                await asyncio.sleep(2)
            
            # 3. 定位并点击上传图片按钮
            upload_selectors = [
                'div.upload-wrapper input[type="file"][accept="image/png, image/jpeg, image/*"]',
                'input[type="file"][class="upload-input"]',
                'div[class*="upload-wrapper"] input[type="file"]'
            ]
            
            file_input = None
            for selector in upload_selectors:
                try:
                    input_elem = page.locator(selector)
                    if await input_elem.count() > 0:
                        file_input = input_elem
                        logger.info(f"找到文件上传输入框: {selector}")
                        break
                except Exception:
                    continue
            
            if not file_input:
                logger.error("未找到文件上传输入框")
                await page.screenshot(path="debug_upload.png")
                raise Exception("无法找到文件上传输入框")
            
            # 4. 上传缩略图
            logger.info(f"正在上传缩略图: {self.thumbnail_path}")
            await file_input.set_input_files(self.thumbnail_path)
            
            # 5. 等待缩略图上传完成
            try:
                await page.wait_for_selector('img[src*="data:image"]', state='visible', timeout=10000)
                logger.success("封面上传完成")
            except Exception as e:
                logger.error(f"等待封面上传完成超时: {str(e)}")
                raise
            
            # 6. 点击确定按钮（如果需要）
            try:
                confirm_button = page.locator('button:has-text("确定")')
                if await confirm_button.count() > 0:
                    await confirm_button.click()
                    await asyncio.sleep(1)
            except Exception:
                pass  # 如果没有确定按钮就跳过
            
        except Exception as e:
            logger.error(f"设置视频封面失败: {str(e)}")
            try:
                await page.screenshot(path="error_thumbnail.png")
            except:
                pass
            raise

    async def _publish(self, page, context):
        """发布内容"""
        try:
            logger.info("准备发布...")
            
            # 先等待页面稳定
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(1)
            
            # 直接选择发布方式，不检查标签
            if isinstance(self.publish_date, datetime):
                # 定时发布
                await self._set_schedule_time(page, self.publish_date)
            else:
                # 立即发布
                immediate_button = page.locator('label:has-text("发布")')
                await immediate_button.click()
                await asyncio.sleep(0.5)
            
            # 添加地点
            await self._add_location(page)
            
            # 使用更简单准确的选择器定位发布按钮
            publish_button = page.locator('button[type="button"]:has-text("定时发布")')
            await publish_button.wait_for(state='visible', timeout=5000)
            await publish_button.click()
            
            # 等待发布成功页面
            success_url = "https://creator.xiaohongshu.com/publish/success"
            await page.wait_for_url(lambda url: url.startswith(success_url), timeout=10000)
            
            if isinstance(self.publish_date, datetime):
                logger.success(f"定时发布设置成功，将在 {self.publish_date.strftime('%Y-%m-%d %H:%M')} 发布")
            else:
                logger.success("发布成功")
            
        except Exception as e:
            logger.error(f"发布失败: {str(e)}")
            raise

    async def main(self):
        """主函数"""
        async with async_playwright() as playwright:
            await self.upload(playwright)

    async def _add_location_for_video(self, page):
        """为视频添加地点"""
        try:
            logger.info("正在添加地点...")
            
            # 等待页面加载完成
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(0.5)
            
            # 1. 直接点击显示"添加地点"的占位符文本
            placeholder = page.locator('div.d-text.d-select-placeholder:has-text("添加地点")')
            if await placeholder.count() == 1:
                await placeholder.click()
                logger.info("点击添加地点")
                await asyncio.sleep(0.5)
                
                # 2. 输入地点
                location = "厦门市"
                await page.keyboard.type(location, delay=50)
                logger.info(f"输入地点: {location}")
                await asyncio.sleep(0.8)
                
                # 3. 直接选择第一个选项
                try:
                    first_option = page.locator('div.d-popover-default div.name[data-v-09078844]').first
                    await first_option.click()
                    logger.info("选择第一个地点选项")
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"选择地点选项失败: {str(e)}")
                    await page.screenshot(path="video_location_selection_error.png")
                    raise
            else:
                logger.error("未找到添加地点选项")
                await page.screenshot(path="video_no_location_placeholder.png")
                raise Exception("未找到添加地点选项")
            
        except Exception as e:
            logger.error(f"添加地点失败: {str(e)}")
            try:
                await page.screenshot(path="video_error_location.png")
            except:
                pass
            raise

if __name__ == "__main__":
    # 设置 cookie 文件路径
    account_file = Path(BASE_DIR / "cookies" / "xhs_uploader" / "account.json")
    
    # 运行登录流程
    asyncio.run(xhs_setup(account_file, handle=True)) 