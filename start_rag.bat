@echo off
title RAG Application Starter
color 0B

echo ===================================================
echo       Starting AI Document QA System (RAG)
echo ===================================================
echo.

echo [1/3] Checking environment variables...
if not exist ".env" (
    echo WARNING: .env file not found! API keys might be missing.
    echo Please ensure GROQ_API_KEY and NEO4J credentials are set.
) else (
    echo OK: .env file found.
)
echo.

echo [2/3] Attempting to launch Neo4j Desktop (if installed)...
REM This tries to open Neo4j Desktop using its typical Windows installation path.
REM If you run Neo4j differently (e.g., Docker or Service), you can safely ignore this.
set NEO4J_DESKTOP_PATH="%LOCALAPPDATA%\Programs\Neo4j Desktop\Neo4j Desktop.exe"
if exist %NEO4J_DESKTOP_PATH% (
    echo Launching Neo4j Desktop... Please ensure your specific Project/Database is "Active".
    start "" %NEO4J_DESKTOP_PATH%
    echo.
    echo Waiting 10 seconds for Neo4j to initialize...
    timeout /t 10 /nobreak
) else (
    echo Neo4j Desktop not found in default path. 
    echo If you use Neo4j Community Desktop, please start your database manually.
)
echo.

echo [3/3] Starting Python Backend and Dashboard...
echo The application will be available at: http://localhost:5000
echo.
echo Press CTRL+C at any time to stop the server.
echo ---------------------------------------------------

REM Start the Flask app
python app.py

pause
