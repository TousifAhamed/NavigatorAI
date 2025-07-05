@echo off
echo 🧹 Clearing AI Travel Planner Ports...
echo ==========================================

echo.
echo 🔍 Checking for processes listening on ports 8000 and 8501...
netstat -ano | findstr LISTENING | findstr ":8000"
if %errorlevel% equ 0 (
    echo ⚠️ Port 8000 is in use
) else (
    echo ✅ Port 8000 is free
)

netstat -ano | findstr LISTENING | findstr ":8501"
if %errorlevel% equ 0 (
    echo ⚠️ Port 8501 is in use
) else (
    echo ✅ Port 8501 is free
)

echo.
echo 🔥 Killing any Python/Streamlit processes...
taskkill /F /IM python.exe 2>nul
taskkill /F /IM pythonw.exe 2>nul
taskkill /F /IM streamlit.exe 2>nul

echo.
echo ⏳ Waiting 2 seconds...
timeout /t 2 /nobreak >nul

echo.
echo 🔍 Final check...
netstat -ano | findstr LISTENING | findstr ":8000\|:8501"
if %errorlevel% equ 0 (
    echo ⚠️ Some ports still in use
) else (
    echo ✅ All ports are now free!
)

echo.
echo 🎉 Ports cleared! Ready to start servers.
echo.
echo 📋 Next steps:
echo    1. Start backend: python start_backend.py
echo    2. Start frontend: streamlit run app.py
echo.
pause
