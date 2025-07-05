@echo off
echo Starting AI Travel Planner...
echo.

REM Use system Python directly (virtual environment has issues)
echo Using system Python to avoid virtual environment issues...

REM Change to the correct directory
cd /d "c:\DEV\Trace_Advisory_MCP\ERAV3-CapstoneProject\agentic_ai"

echo Starting Streamlit application...
echo The app will be available at: http://localhost:8501
echo.
echo Press Ctrl+C to stop the application
echo.

REM Run the Streamlit app with system Python
C:\Users\tousi\AppData\Local\Programs\Python\Python313\python.exe -m streamlit run app.py --server.port 8501

pause