@echo off
echo ========================================
echo    AI Travel Planner - MCP Backend
echo ========================================
echo.

REM Use system Python directly (virtual environment has issues)
echo Using system Python to avoid virtual environment issues...

REM Change to the correct directory
cd /d "c:\DEV\Trace_Advisory_MCP\ERAV3-CapstoneProject\agentic_ai"

echo Starting MCP Backend Server...
echo.
echo Checking dependencies...
C:\Users\tousi\AppData\Local\Programs\Python\Python313\python.exe -c "import currency_converter; print('✅ currency_converter available')" 2>nul || (
    echo ⚠️  Installing missing dependencies...
    C:\Users\tousi\AppData\Local\Programs\Python\Python313\python.exe -m pip install currency_converter forex-python python-weather geopy overpass
)
echo.
echo The server will be available at: http://localhost:8000
echo Health check: http://localhost:8000/health
echo Agent endpoint: http://localhost:8000/agent/execute
echo.
echo Press Ctrl+C to stop the server
echo.

REM Run the MCP backend server with system Python
C:\Users\tousi\AppData\Local\Programs\Python\Python313\python.exe start_backend.py

pause