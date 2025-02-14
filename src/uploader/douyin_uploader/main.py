# -*- coding: utf-8 -*-
from datetime import datetime
from pathlib import Path
import random

from playwright.async_api import Playwright, async_playwright, Page
import os
import asyncio

from conf import LOCAL_CHROME_PATH
from utils.base_social_media import set_init_script
from src.utils.log import logger
from utils.constant import FileTypes


async def cookie_auth(account_file):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=account_file)
        context = await set_init_script(context)
        # 创建一个新的页面
        page = await context.new_page()
        # 访问指定的 URL
        await page.goto("https://creator.douyin.com/creator-micro/content/upload")
        try:
            await page.wait_for_url("https://creator.douyin.com/creator-micro/content/upload", timeout=5000)
        except:
            print("[+] 等待5秒 cookie 失效")
            await context.close()
            await browser.close()
            return False
        # 2024.06.17 抖音创作者中心改版
        if await page.get_by_text('手机号登录').count():
            print("[+] 等待5秒 cookie 失效")
            return False
        else:
            print("[+] cookie 有效")
            return True


async def douyin_setup(account_file, handle=False):
    if not os.path.exists(account_file) or not await cookie_auth(account_file):
        if not handle:
            # Todo alert message
            return False
        logger.info('[+] cookie文件不存在或已失效，即将自动打开浏览器，请扫码登录，登陆后会自动生成cookie文件')
        await douyin_cookie_gen(account_file)
    return True


async def douyin_cookie_gen(account_file):
    async with async_playwright() as playwright:
        options = {
            'headless': False
        }
        # Make sure to run headed.
        browser = await playwright.chromium.launch(**options)
        # Setup context however you like.
        context = await browser.new_context()  # Pass any options
        context = await set_init_script(context)
        # Pause the page, and start recording manually.
        page = await context.new_page()
        await page.goto("https://creator.douyin.com/")
        await page.pause()
        # 点击调试器的继续，保存cookie
        await context.storage_state(path=account_file)


class DouYinUploader(object):
    def __init__(self, title, file_path, tags, publish_date, account_file, thumbnail_path=None):
        self.title = title
        self.file_path = file_path
        self.tags = tags
        self.publish_date = publish_date
        self.account_file = account_file
        self.thumbnail_path = thumbnail_path
        self.file_type = self._get_file_type()

    def _get_file_type(self):
        """判断文件类型"""
        suffix = Path(self.file_path).suffix.lower()
        if suffix in FileTypes.VIDEO_EXTENSIONS:
            return "video"
        elif suffix in FileTypes.IMAGE_EXTENSIONS:
            return "image"
        else:
            raise ValueError(f"不支持的文件类型: {suffix}")

    async def upload(self, playwright):
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=False)
            context = await browser.new_context(storage_state=self.account_file)
            page = await context.new_page()
            
            try:
                # 访问抖音创作者页面
                await page.goto("https://creator.douyin.com/creator-micro/content/upload")
                await asyncio.sleep(random.uniform(0.5, 1.0))
                logger.info(f'[+]正在上传-------{self.title}')
                
                # 等待页面加载完成
                await page.wait_for_load_state("networkidle")
                await asyncio.sleep(random.uniform(0.1, 0.5))
                
                # 根据文件类型选择上传模式
                if self.file_type == "video":
                    await self._select_video_mode(page)
                else:
                    await self._select_image_mode(page)
                
                await asyncio.sleep(random.uniform(0.1, 0.5))
                
                # 上传文件
                await self._upload_file(page)
                
                await asyncio.sleep(random.uniform(0.5, 1.0))
                
                # 设置标题和标签
                await self._set_title_and_tags(page)
                
                await asyncio.sleep(random.uniform(0.5, 1.0))
                
                # 设置地区
                try:
                    logger.info("正在设置地区...")
                    await self.set_location(page, "上海市")
                    logger.success("地区设置完成")
                except Exception as e:
                    logger.error(f"设置地区失败: {str(e)}")
                
                await asyncio.sleep(random.uniform(0.5, 1.0))
                
                # 设置发布时间
                if self.publish_date != 0:
                    await self.set_schedule_time_douyin(page, self.publish_date)
                    await asyncio.sleep(random.uniform(0.5, 1.0))
                
                # 发布
                await self._publish(page, context)
                
            finally:
                await asyncio.sleep(random.uniform(0.5, 1.0))
                await context.close()
                await browser.close()

    async def _select_video_mode(self, page):
        """选择视频上传模式"""
        try:
            # 等待页面加载完成
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(random.uniform(0.1, 0.5))
            
            # 等待标签容器出现
            await page.wait_for_selector('div[class*="tab-container"]', timeout=5000)
            await asyncio.sleep(random.uniform(0.5, 1.0))
            
            # 使用更通用的选择器
            video_tab = page.locator('div[class*="tab-item"]:has-text("发布视频")')
            
            if await video_tab.count():
                # 检查当前是否已在视频模式
                parent = video_tab.locator('..')
                parent_class = await parent.get_attribute('class')
                
                if not parent_class or 'active' not in parent_class:
                    await asyncio.sleep(random.uniform(0.1, 0.5))
                    # 点击前先确保元素可见和可点击
                    await video_tab.wait_for(state='visible')
                    await video_tab.scroll_into_view_if_needed()
                    await video_tab.click()
                    await asyncio.sleep(random.uniform(0.5, 1.0))
                    logger.info("已切换到视频上传模式")
                else:
                    logger.info("当前已是视频上传模式")
            else:
                # 如果找不到，尝试其他可能的选择器
                video_button = page.get_by_role('tab', name='发布视频')
                if await video_button.count():
                    await asyncio.sleep(random.uniform(0.1,0.5))  # 点击前等待0.5秒
                    await video_button.click()
                    await asyncio.sleep(random.uniform(0.5,1))  # 点击后等待0.5-1秒
                    logger.info("已切换到视频上传模式")
                else:
                    raise Exception("未找到视频上传选项")
                
        except Exception as e:
            logger.error(f"切换视频模式失败: {str(e)}")
            raise

    async def _select_image_mode(self, page):
        """选择图文上传模式"""
        try:
            # 等待页面加载完成
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(1000)  # 等待1秒确保页面完全加载
            
            # 等待标签容器出现
            await page.wait_for_selector('div[class*="tab-container"]', timeout=5000)
            
            # 使用更通用的选择器
            image_tab = page.locator('div[class*="tab-item"]:has-text("发布图文")')
            
            if await image_tab.count():
                # 检查当前是否已在图文模式
                parent = image_tab.locator('..')
                parent_class = await parent.get_attribute('class')
                
                if not parent_class or 'active' not in parent_class:
                    # 点击前先确保元素可见和可点击
                    await image_tab.wait_for(state='visible')
                    await image_tab.scroll_into_view_if_needed()
                    await image_tab.click()
                    await page.wait_for_timeout(1000)
                    logger.info("已切换到图文上传模式")
                else:
                    logger.info("当前已是图文上传模式")
            else:
                # 如果找不到，尝试其他可能的选择器
                image_button = page.get_by_role('tab', name='发布图文')
                if await image_button.count():
                    await image_button.click()
                    await page.wait_for_timeout(1000)
                    logger.info("已切换到图文上传模式")
                else:
                    raise Exception("未找到图文上传选项")
                
        except Exception as e:
            logger.error(f"切换图文模式失败: {str(e)}")
            raise

    async def _upload_file(self, page):
        """上传文件"""
        try:
            logger.info("等待上传按钮出现...")
            
            # 根据文件类型选择正确的上传按钮
            if self.file_type == "video":
                # 视频上传按钮
                upload_selector = 'input[type="file"][accept*="video"]'
                success_text = "重新上传"
            else:
                # 图片上传按钮
                upload_selector = 'input[type="file"][accept*="image"]'
                success_text = "重新选择"
            
            # 等待对应的上传按钮出现
            await page.wait_for_selector(upload_selector, timeout=5000, state='attached')
            
            # 定位上传按钮并上传文件
            upload_button = page.locator(upload_selector)
            await upload_button.set_input_files(self.file_path)
            
            logger.info("文件上传中...")
            
            # 设置最大等待时间（1分钟）
            max_wait_time = 60  # 秒
            start_time = asyncio.get_event_loop().time()
            
            # 等待上传完成并跳转
            if self.file_type == "image":
                # 图文上传需要等待跳转到编辑页面
                try:
                    await page.wait_for_url(
                        "https://creator.douyin.com/creator-micro/content/publish-media/image-text**",
                        timeout=max_wait_time * 1000
                    )
                    logger.success("图片上传完毕，已进入编辑页面")
                    return
                except Exception as e:
                    raise Exception("等待跳转到图文编辑页面超时")
            else:
                # 视频上传的原有逻辑
                while True:
                    try:
                        if page.is_closed():
                            raise Exception("页面已关闭")
                        
                        if asyncio.get_event_loop().time() - start_time > max_wait_time:
                            raise TimeoutError("上传超时")

                        # 视频上传检查
                        success = await page.locator(f'div:has-text("{success_text}")').count() > 0
                        error = await page.locator('div:has-text("上传失败")').count() > 0
                        
                        if error:
                            logger.error("上传失败，准备重试")
                            await self.handle_upload_error(page)
                        elif success:
                            logger.success("视频上传完毕")
                            break
                        
                        await asyncio.sleep(1)
                        logger.info("等待上传完成...")
                        
                    except Exception as e:
                        if "页面已关闭" in str(e):
                            raise Exception("页面已关闭，上传失败")
                        elif "上传超时" in str(e):
                            raise Exception("上传超时，请检查网络状况")
                        elif "TimeoutError" not in str(e):
                            logger.error(f"上传过程出错: {str(e)}")
                        await asyncio.sleep(1)
                    
        except Exception as e:
            logger.error(f"上传出错: {str(e)}")
            raise

    async def set_schedule_time_douyin(self, page, publish_date):
        """设置发布时间"""
        try:
            logger.info("开始设置定时发布...")
            
            # 1. 先点击定时发布选项
            timing_selectors = [
                'div[class*="radio-wrapper"]:has-text("定时发布")',  # 最常见的选择器
                'div[class*="radio"]:has-text("定时发布")',
                'label:has-text("定时发布")',
                'div[role="radio"]:has-text("定时发布")'
            ]
            
            timing_found = False
            for selector in timing_selectors:
                timing_element = page.locator(selector).first
                if await timing_element.count():
                    logger.info(f"找到定时发布选项")
                    try:
                        await timing_element.wait_for(state='visible', timeout=5000)
                        await timing_element.click()
                        timing_found = True
                        await asyncio.sleep(2)  # 增加等待时间
                        break
                    except Exception as click_error:
                        logger.warning(f"点击定时发布选项失败，尝试下一个选择器")
                        continue
            
            if not timing_found:
                logger.error("未找到定时发布选项")
                return
            
            # 2. 点击日期时间输入框
            time_input_selectors = [
                'input.semi-input[placeholder="日期和时间"]',  # 最常见的选择器
                'input[placeholder*="日期和时间"]',
                'input[type="text"][placeholder*="日期"]',
                'div.semi-datepicker input'
            ]
            
            time_input_found = False
            for selector in time_input_selectors:
                time_input = page.locator(selector).first
                if await time_input.count():
                    logger.info(f"找到时间输入框")
                    try:
                        await time_input.wait_for(state='visible', timeout=5000)
                        await time_input.click()
                        await asyncio.sleep(1)
                        
                        # 3. 输入时间
                        publish_date_hour = publish_date.strftime("%Y-%m-%d %H:%M")
                        await page.keyboard.press("Control+A")
                        await asyncio.sleep(0.5)
                        await page.keyboard.type(publish_date_hour)
                        await asyncio.sleep(0.5)
                        await page.keyboard.press("Enter")
                        await asyncio.sleep(1)
                        
                        time_input_found = True
                        logger.success(f"已设置定时发布时间: {publish_date_hour}")
                        break
                    except Exception as input_error:
                        logger.warning(f"设置时间失败，尝试下一个选择器")
                        continue
            
            if not time_input_found:
                logger.error("未找到时间输入框")
                return
            
            # 4. 如果有确认按钮，点击确认
            try:
                confirm_button = page.locator('button:has-text("确定")').first
                if await confirm_button.count():
                    await confirm_button.click()
                    await asyncio.sleep(1)
                    logger.info("已点击确认按钮")
            except Exception as e:
                logger.warning("未找到或无需点击确认按钮")
            
            await asyncio.sleep(2)
            
        except Exception as e:
            logger.error(f"设置发布时间失败: {str(e)}")
            # 不抛出异常，允许时间设置失败
            pass

    async def handle_upload_error(self, page):
        logger.info('视频出错了，重新上传中')
        await page.locator('div.progress-div [class^="upload-btn-input"]').set_input_files(self.file_path)

    async def _set_title_and_tags(self, page):
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
            # 视频上传的原有标题和话题设置逻辑
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
                # 输入话题
                await page.type(css_selector, f"#{tag}")
                await page.press(css_selector, "Space")
                logger.info(f'  [-] 已添加第{index}个话题: #{tag}')
            
            await asyncio.sleep(0.5)  # 所有话题添加完成后等待1秒
            logger.success(f'  [-] 标题和话题添加完成，共添加{len(self.tags)}个话题')

    async def _publish(self, page, context):
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

    async def set_thumbnail(self, page: Page, thumbnail_path: str):
        if thumbnail_path:
            await page.click('text="选择封面"')
            await page.wait_for_selector("div.semi-modal-content:visible")
            await page.click('text="设置竖封面"')
            await page.wait_for_timeout(2000)  # 等待2秒
            # 定位到上传区域并点击
            await page.locator("div[class^='semi-upload upload'] >> input.semi-upload-hidden-input").set_input_files(thumbnail_path)
            await page.wait_for_timeout(2000)  # 等待2秒
            await page.locator("div[class^='extractFooter'] button:visible:has-text('完成')").click()
            # finish_confirm_element = page.locator("div[class^='confirmBtn'] >> div:has-text('完成')")
            # if await finish_confirm_element.count():
            #     await finish_confirm_element.click()
            # await page.locator("div[class^='footer'] button:has-text('完成')").click()

    async def set_location(self, page: Page, location: str = "上海市"):
        """设置地区"""
        try:
            if self.file_type == "image":
                # 图文界面的地区设置
                try:
                    # 使用更精确的选择器定位位置输入框
                    location_selector = page.locator('div.semi-select span:has-text("输入相关位置，让更多人看到你的作品")').filter(
                        has_text="输入相关位置"
                    ).first
                    
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
                except Exception as e:
                    logger.error(f"图文地区设置失败: {str(e)}")
            else:
                # 视频界面的地区设置
                try:
                    # 使用视频界面特有的选择器
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
                except Exception as e:
                    logger.error(f"视频地区设置失败: {str(e)}")
            
            await asyncio.sleep(random.uniform(0.5,1))
            
        except Exception as e:
            logger.error(f"设置地区时出错: {str(e)}")
            # 不抛出异常，允许地区设置失败
            pass

    async def main(self):
        async with async_playwright() as playwright:
            await self.upload(playwright)


