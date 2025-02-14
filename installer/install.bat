@echo off
echo 正在安装视频自动发布工具...

:: 创建桌面快捷方式
powershell "$s=(New-Object -COM WScript.Shell).CreateShortcut('%userprofile%\Desktop\视频自动发布工具.lnk');$s.TargetPath='%~dp0\dist\run.exe';$s.Save()"

echo 安装完成！
pause 