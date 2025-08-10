@echo off
echo 🚀 啟動 Potato Bot API 服務...
echo 📖 API 文檔將在 http://localhost:8001/docs 提供
echo 按 Ctrl+C 停止服務
echo.

cd /d "%~dp0"
set API_PORT=8001
python start_api.py

pause