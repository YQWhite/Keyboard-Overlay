@echo off
echo 开始打包项目...

pyinstaller --noconfirm --onefile --windowed ^
  --add-data "index.html;." ^
  --add-data "config.html;." ^
  --add-data "config.json;." ^
  --add-data "stats.json;." ^
  --name "KeyboardOverlay" ^
  server.py

echo 打包完成！生成的文件位于 dist 文件夹下。
pause