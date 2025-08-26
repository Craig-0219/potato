@echo off
REM 🚀 Potato Bot Windows 啟動批次檔
REM 支援自動環境檢查和依賴安裝

setlocal EnableDelayedExpansion

REM 獲取腳本目錄
set "SCRIPT_DIR=%~dp0"
set "BOT_FILE=%SCRIPT_DIR%bot\main.py"
set "ENV_FILE=%SCRIPT_DIR%.env"
set "ENV_EXAMPLE=%SCRIPT_DIR%.env.example"
set "REQUIREMENTS_FILE=%SCRIPT_DIR%requirements.txt"

REM 顏色代碼 (Windows 10/11 支援)
set "RED=[91m"
set "GREEN=[92m"
set "YELLOW=[93m"
set "BLUE=[94m"
set "PURPLE=[95m"
set "CYAN=[96m"
set "WHITE=[97m"
set "NC=[0m"

goto :main

:print_banner
echo %CYAN%
echo 🥔 ═══════════════════════════════════════════════════════════════
echo    ____        _        _          ____        _
echo   ^|  _ \ ___ ^| ^|_ __ _^| ^|_ ___   ^| __ )  ___ ^| ^|_
echo   ^| ^|_) / _ \^| __/ _` ^| __/ _ \  ^|  _ \ / _ \^| __^|
echo   ^|  __/ (^_) ^| ^|^| (^_^| ^| ^|^| (^_) ^| ^| ^|_) ^| (^_) ^| ^|_
echo   ^|_^|   \___/ \__\__,_^\__\___/  ^|____/ \___/ \__^|
echo
echo    🎮 Discord ^& Minecraft 社群管理平台
echo    ⚡ v3.2.0 - 專為遊戲社群打造
echo ═══════════════════════════════════════════════════════════════ 🥔
echo %NC%
goto :eof

:log_info
echo %BLUE%[INFO]%NC% %~1
goto :eof

:log_success
echo %GREEN%[SUCCESS]%NC% %~1
goto :eof

:log_warning
echo %YELLOW%[WARNING]%NC% %~1
goto :eof

:log_error
echo %RED%[ERROR]%NC% %~1
goto :eof

:check_python
call :log_info "檢查 Python 環境..."

REM 檢查 Python 是否存在
python --version >nul 2>&1
if !errorlevel! neq 0 (
    call :log_error "未找到 Python"
    call :log_error "請從 https://www.python.org/ 下載並安裝 Python 3.10 或更高版本"
    pause
    exit /b 1
)

REM 獲取 Python 版本
for /f "tokens=2" %%a in ('python --version 2^>^&1') do set "PYTHON_VERSION=%%a"
call :log_success "Python 版本: %PYTHON_VERSION%"

REM 檢查版本是否符合要求
python -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if !errorlevel! neq 0 (
    call :log_error "需要 Python 3.10 或更高版本"
    pause
    exit /b 1
)

call :log_success "Python 版本符合要求"
goto :eof

:check_environment
call :log_info "檢查環境設定..."

if not exist "%ENV_FILE%" (
    if exist "%ENV_EXAMPLE%" (
        call :log_warning "未找到 .env 檔案"
        set /p "response=是否要從 .env.example 複製設定？(y/n): "
        if /i "!response!" == "y" (
            copy "%ENV_EXAMPLE%" "%ENV_FILE%" >nul
            call :log_success "已複製 .env.example 到 .env"
            call :log_warning "請編輯 .env 檔案填入您的配置"
            set /p "edit_response=是否要現在編輯 .env 檔案？(y/n): "
            if /i "!edit_response!" == "y" (
                notepad "%ENV_FILE%"
            )
        ) else (
            call :log_error "需要 .env 檔案才能啟動"
            pause
            exit /b 1
        )
    ) else (
        call :log_error "未找到 .env 和 .env.example 檔案"
        pause
        exit /b 1
    )
) else (
    call :log_success "環境檔案存在"
)
goto :eof

:check_dependencies
call :log_info "檢查依賴套件..."

REM 檢查必要套件
python -c "import discord, aiomysql, dotenv, fastapi, uvicorn" >nul 2>&1
if !errorlevel! neq 0 (
    call :log_warning "部分依賴套件缺失"
    set /p "response=是否要自動安裝依賴套件？(y/n): "
    if /i "!response!" == "y" (
        call :install_dependencies
    ) else (
        call :log_error "請手動安裝依賴套件: pip install -r requirements.txt"
        pause
        exit /b 1
    )
) else (
    call :log_success "所有必要依賴套件已安裝"
)
goto :eof

:install_dependencies
call :log_info "安裝依賴套件..."

if not exist "%REQUIREMENTS_FILE%" (
    call :log_error "未找到 requirements.txt"
    pause
    exit /b 1
)

python -m pip install -r "%REQUIREMENTS_FILE%"
if !errorlevel! equ 0 (
    call :log_success "依賴套件安裝完成"
) else (
    call :log_error "依賴套件安裝失敗"
    pause
    exit /b 1
)
goto :eof

:check_bot_file
call :log_info "檢查 Bot 主程式..."

if not exist "%BOT_FILE%" (
    call :log_error "未找到 bot\main.py"
    pause
    exit /b 1
)

call :log_success "Bot 主程式存在"
goto :eof

:show_system_info
echo %CYAN%💻 系統資訊:%NC%
echo    作業系統: Windows
echo    Python: %PYTHON_VERSION%
echo    工作目錄: %SCRIPT_DIR%
echo    時間: %date% %time%
goto :eof

:start_bot
call :log_info "啟動 Potato Bot..."
echo %YELLOW%使用 Ctrl+C 停止 Bot%NC%
echo ==================================================

cd /d "%SCRIPT_DIR%"

python "%BOT_FILE%"
if !errorlevel! equ 0 (
    call :log_success "Bot 已正常停止"
) else (
    call :log_error "Bot 執行失敗"
    pause
    exit /b 1
)
goto :eof

:run_pre_checks
call :print_banner
call :show_system_info

echo.
call :log_info "執行啟動前檢查..."

call :check_python
if !errorlevel! neq 0 exit /b 1

call :check_environment
if !errorlevel! neq 0 exit /b 1

call :check_dependencies
if !errorlevel! neq 0 exit /b 1

call :check_bot_file
if !errorlevel! neq 0 exit /b 1

echo.
call :log_success "所有檢查通過!"
goto :eof

:show_help
echo 🚀 Potato Bot 啟動腳本
echo.
echo 用法:
echo     %~nx0 [選項]
echo.
echo 選項:
echo     start          立即啟動 Bot (跳過互動)
echo     check          只執行環境檢查
echo     install        只安裝依賴套件
echo     help           顯示此幫助訊息
echo.
echo 範例:
echo     %~nx0                # 互動模式啟動
echo     %~nx0 start         # 直接啟動
echo     %~nx0 check         # 只檢查環境
echo     %~nx0 install       # 只安裝依賴
echo.
goto :eof

:main
REM 解析命令列參數
if "%~1" == "start" (
    call :run_pre_checks
    if !errorlevel! equ 0 call :start_bot
    goto :end
) else if "%~1" == "check" (
    call :run_pre_checks
    goto :end
) else if "%~1" == "install" (
    call :check_python
    if !errorlevel! equ 0 call :install_dependencies
    goto :end
) else if "%~1" == "help" (
    call :show_help
    goto :end
) else if "%~1" == "" (
    REM 互動模式
    call :run_pre_checks
    if !errorlevel! neq 0 (
        pause
        exit /b 1
    )

    echo ==================================================
    set /p "response=準備就緒! 是否立即啟動 Bot？(y/n): "

    if /i "!response!" == "y" (
        call :start_bot
    ) else if /i "!response!" == "" (
        call :start_bot
    ) else (
        echo.
        call :log_info "您可以稍後手動執行:"
        echo    python bot\main.py
        echo    或
        echo    start.bat start
    )
    goto :end
) else (
    call :log_error "未知選項: %~1"
    echo.
    call :show_help
    pause
    exit /b 1
)

:end
pause
