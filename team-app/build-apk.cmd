@echo off
rem Builds the SunBird app to put on phones: apk\SunBird.apk (README.md says how).
setlocal
set "JAVA_HOME=%USERPROFILE%\.jdks\jdk-21.0.13+9"
set "ANDROID_HOME=%LOCALAPPDATA%\Android\Sdk"
set "ANDROID_SDK_ROOT=%ANDROID_HOME%"
cd /d "%~dp0"
if not exist keystore.properties (
  echo The signing key is missing: keystore.properties and keystore\ must be in this folder.
  pause
  exit /b 1
)
call gradlew.bat assembleRelease
if errorlevel 1 (
  echo The build failed. See the messages above.
  pause
  exit /b 1
)
if not exist apk mkdir apk
copy /y app\build\outputs\apk\release\app-release.apk apk\SunBird.apk >nul
echo.
echo Made apk\SunBird.apk
pause
