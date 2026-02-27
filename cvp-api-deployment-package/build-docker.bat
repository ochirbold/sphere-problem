@echo off
REM Docker image build script for CVP API (Windows)
REM Usage: build-docker.bat [tag]

setlocal enabledelayedexpansion

REM Default values
set IMAGE_NAME=cvp-sphere-api
set DEFAULT_TAG=latest

REM Get tag from command line or use default
if "%~1"=="" (
    set TAG=%DEFAULT_TAG%
) else (
    set TAG=%~1
)

set FULL_IMAGE_NAME=%IMAGE_NAME%:%TAG%

echo Building Docker image: %FULL_IMAGE_NAME%

REM Build the Docker image
docker build -t %FULL_IMAGE_NAME% .

if %ERRORLEVEL% neq 0 (
    echo Error building Docker image
    exit /b %ERRORLEVEL%
)

echo Docker image built successfully: %FULL_IMAGE_NAME%

echo.
echo Image information:
docker images | findstr %IMAGE_NAME%

echo.
echo To run the image locally:
echo   docker run -p 8000:8000 -e DB_USER=your_user -e DB_PASSWORD=your_password %FULL_IMAGE_NAME%
echo.
echo To push to Docker Hub (if configured):
echo   docker tag %FULL_IMAGE_NAME% yourusername/%FULL_IMAGE_NAME%
echo   docker push yourusername/%FULL_IMAGE_NAME%
echo.
echo To save image to file:
echo   docker save %FULL_IMAGE_NAME% | gzip > cvp-sphere-api-%TAG%.tar.gz