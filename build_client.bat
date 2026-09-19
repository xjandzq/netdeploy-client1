@echo off
REM ============================================
REM NetDeploy Client Builder
REM ============================================

echo ============================================
echo  NetDeploy Client Builder
echo  Company: JingBei Technology
echo ============================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found, please install Python 3.10+
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/5] Creating virtual environment...
if not exist venv (
    python -m venv venv
)
call venv\Scripts\activate.bat

echo.
echo [2/5] Installing dependencies...
pip install --upgrade pip >nul
pip install pyautogui pillow requests pystray PyQt5 mss pyinstaller >nul
if errorlevel 1 (
    echo [ERROR] pip install failed
    pause
    exit /b 1
)

echo.
echo [3/5] Copying client files...
if not exist build mkdir build
copy /Y netdeploy_client.py build\netdeploy_client.py >nul
copy /Y ca.crt build\ca.crt >nul
copy /Y client.crt build\client.crt >nul
copy /Y client.key build\client.key >nul

echo.
echo [4/5] Generating UTF-8 version info file (Chinese brand)...
python gen_version_info.py build\version_info.txt
if errorlevel 1 (
    echo [ERROR] version info generation failed
    pause
    exit /b 1
)

echo.
echo [5/5] Running PyInstaller...
cd build
pyinstaller --onefile --noconsole --name NetDeployClient --add-data "ca.crt;." --add-data "client.crt;." --add-data "client.key;." --version-file version_info.txt --hidden-import PyQt5 --hidden-import pystray netdeploy_client.py

if errorlevel 1 (
    cd ..
    echo.
    echo [ERROR] PyInstaller failed
    pause
    exit /b 1
)

cd ..
echo.
echo ============================================
echo  Build Complete! - POWER BY JingBei Technology
echo ============================================
echo.
echo  EXE location: build\dist\NetDeployClient.exe
echo.
echo Usage:
echo  1. Copy build\dist\NetDeployClient.exe to target PC
echo  2. Put ca.crt / client.crt / client.key in EXE folder
echo  3. Double-click NetDeployClient.exe
echo  4. Admin approves registration
echo  5. Send commands from Feishu
echo.
pause
