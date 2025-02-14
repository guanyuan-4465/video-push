import argparse
import asyncio
from datetime import datetime
from os.path import exists
from pathlib import Path

from conf import BASE_DIR
from uploader.douyin_uploader.main import douyin_setup, DouYinUploader
from uploader.xhs_uploader.main import xhs_setup, XHSUploader
from utils.base_social_media import get_supported_social_media, get_cli_action, SOCIAL_MEDIA_DOUYIN, SOCIAL_MEDIA_XHS
from utils.constant import FileTypes
from utils.files_times import get_title_and_hashtags


def parse_schedule(schedule_str):
    """解析定时发布时间"""
    if schedule_str:
        try:
            return datetime.strptime(schedule_str, '%Y-%m-%d %H:%M')
        except ValueError:
            print("时间格式错误，请使用 YYYY-MM-DD HH:MM 格式")
            exit()
    return None


def main():
    parser = argparse.ArgumentParser(description='社交媒体自动发布工具')
    parser.add_argument('platform', choices=get_supported_social_media(), help='选择平台')
    parser.add_argument('action', choices=get_cli_action(), help='选择操作')
    parser.add_argument('command', help='具体命令')
    parser.add_argument('file_path', nargs='?', help='文件路径')
    parser.add_argument('-pt', '--publish-type', type=int, default=0, help='发布类型：0-立即发布，1-定时发布')
    parser.add_argument('-t', '--schedule', help='定时发布时间，格式：YYYY-MM-DD HH:MM')
    parser.add_argument('-th', '--thumbnail', help='缩略图路径')  # 添加缩略图参数

    args = parser.parse_args()

    if args.action == "uploader":
        if args.command == "upload":
            if not args.file_path or not exists(args.file_path):
                print("请指定有效的文件路径")
                exit()

            # 获取标题和标签
            title, tags = get_title_and_hashtags(args.file_path)
            
            # 设置账号文件路径
            if args.platform == SOCIAL_MEDIA_DOUYIN:
                account_file = Path(BASE_DIR / "cookies" / "douyin_uploader" / "account.json")
            else:
                account_file = Path(BASE_DIR / "cookies" / "xhs_uploader" / "account.json")

            # 设置发布时间
            if args.publish_type == 1:
                if not args.schedule:
                    print("定时发布需要指定发布时间")
                    exit()
                print("定时发布...")
                publish_date = parse_schedule(args.schedule)
            else:
                print("立即发布...")
                publish_date = None

            # 检查缩略图路径
            thumbnail_path = None
            if args.thumbnail and exists(args.thumbnail):
                thumbnail_path = args.thumbnail
            else:
                # 尝试查找同名的png文件作为缩略图
                auto_thumbnail = Path(args.file_path).with_suffix('.png')
                if auto_thumbnail.exists():
                    thumbnail_path = str(auto_thumbnail)

            async def run():
                if args.platform == SOCIAL_MEDIA_DOUYIN:
                    await douyin_setup(account_file, handle=False)
                    app = DouYinUploader(
                        title=title,
                        file_path=args.file_path,
                        tags=tags,
                        publish_date=publish_date,
                        account_file=str(account_file),
                        thumbnail_path=thumbnail_path
                    )
                    await app.main()
                else:
                    await xhs_setup(account_file, handle=False)
                    app = XHSUploader(
                        title=title,
                        file_path=args.file_path,
                        tags=tags,
                        publish_date=publish_date,
                        account_file=str(account_file),
                        thumbnail_path=thumbnail_path
                    )
                    await app.main()

            asyncio.run(run())
        elif args.command == "login":
            # ... 其他代码保持不变 ...
            pass


if __name__ == "__main__":
    main()
