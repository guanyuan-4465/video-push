import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
ROOT_DIR = Path(__file__).parent.parent
sys.path.append(str(ROOT_DIR))

from conf import BASE_DIR
from uploader.xhs_uploader.main import xhs_setup, XHSUploader
from utils.files_times import generate_schedule_time_next_day, get_title_and_hashtags
from utils.log import xhs_logger


def get_media_files(directory):
    """获取目录下的媒体文件，优先返回视频文件，如果没有视频则返回图片"""
    # 先查找视频文件
    video_files = list(directory.glob("*.mp4")) + list(directory.glob("*.mov")) + list(directory.glob("*.avi"))
    if video_files:
        return video_files, "video"
    
    # 如果没有视频文件，则查找图片文件
    image_files = list(directory.glob("*.jpg")) + list(directory.glob("*.jpeg")) + list(directory.glob("*.png"))
    if image_files:
        return image_files, "image"
    
    return [], None


if __name__ == '__main__':
    try:
        # 设置目录和账号文件路径
        filepath = Path(BASE_DIR) / "videos"  # 保持目录名不变，但可以存放图片
        account_file = Path(BASE_DIR / "cookies" / "xhs_uploader" / "account.json")
        
        # 验证cookie（静默验证）
        if not asyncio.run(xhs_setup(account_file, handle=False)):
            xhs_logger.error("Cookie 无效，请先运行 get_xhs_cookie.py 进行登录")
            exit(1)
        
        # 获取媒体文件
        files, media_type = get_media_files(filepath)
        
        if not files:
            xhs_logger.error(f"在 {filepath} 目录下未找到视频或图片文件")
            exit(1)
            
        file_num = len(files)
        xhs_logger.info(f"找到 {file_num} 个{media_type}文件，准备上传...")
        
        # 生成发布时间表（每天13点发布一个）
        publish_datetimes = generate_schedule_time_next_day(file_num, 1, daily_times=[13])
        
        # 遍历处理每个文件
        for index, file in enumerate(files, 1):
            try:
                xhs_logger.info(f"\n开始处理第 {index}/{file_num} 个{media_type}:")
                
                # 获取标题和标签
                title, tags = get_title_and_hashtags(str(file))
                
                # 检查是否存在同名缩略图（仅视频需要）
                thumbnail_path = None
                if media_type == "video":
                    thumbnail_path = file.with_suffix('.png')
                    if thumbnail_path.exists():
                        xhs_logger.info(f"使用缩略图：{thumbnail_path}")
                
                # 打印当前处理的文件信息
                xhs_logger.info(f"文件路径：{file}")
                xhs_logger.info(f"标题：{title}")
                xhs_logger.info(f"标签：{tags}")
                xhs_logger.info(f"计划发布时间：{publish_datetimes[index-1]}")
                
                # 创建上传器实例
                if media_type == "video" and thumbnail_path and thumbnail_path.exists():
                    app = XHSUploader(
                        title=title,
                        file_path=str(file),
                        tags=tags,
                        publish_date=publish_datetimes[index-1],
                        account_file=str(account_file),
                        thumbnail_path=str(thumbnail_path)
                    )
                else:
                    app = XHSUploader(
                        title=title,
                        file_path=str(file),
                        tags=tags,
                        publish_date=publish_datetimes[index-1],
                        account_file=str(account_file)
                    )
                
                # 执行上传
                asyncio.run(app.main(), debug=False)
                xhs_logger.success(f"第 {index} 个{media_type}处理完成")
                
            except Exception as e:
                xhs_logger.error(f"处理文件 {file} 时出错: {str(e)}")
                continue
            
    except Exception as e:
        xhs_logger.error(f"程序执行出错: {str(e)}") 