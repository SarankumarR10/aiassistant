@echo off
setlocal
cd /d "%~dp0"

echo EduPilot isolated code runner setup
echo.
where docker >nul 2>&1
if errorlevel 1 (
    echo Docker was not found. Install Docker Desktop with Linux containers enabled,
    echo start Docker Desktop, then run this file again.
    pause
    exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
    echo Docker Desktop is installed but is not running or is not ready.
    echo Start Docker Desktop, wait until it reports that the engine is running,
    echo then run this file again.
    pause
    exit /b 1
)

echo Building the restricted runner image. The first build downloads its base image and compiler packages.
docker build -f docker\Dockerfile.runner -t edupilot-runner:latest docker
if errorlevel 1 (
    echo.
    echo The runner image could not be built. Check Docker Desktop and internet access, then retry.
    pause
    exit /b 1
)

echo.
echo EduPilot code runner is ready. Restart EduPilot and open Local Code Runner.
pause
exit /b 0
