@echo off
chcp 65001 >nul
echo 正在启动 Ollama Hub Web 界面...
echo 请确保 Ollama 服务已经在后台运行。
echo 正在打开浏览器访问 http://localhost:8000 ...
start http://localhost:8000
python -m http.server 8000 --directory web
pause
