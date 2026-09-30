@echo off
chcp 65001 >nul
title StemPlay Android Builder
cd /d "%~dp0"

echo.
echo   StemPlay Android - Builder
echo   ------------------------------------------------------------
echo.

:: Check for Java (JDK 17+ - Android Studio JBR serve)
java -version >nul 2>&1
if errorlevel 1 (
    if exist "C:\Program Files\Android\Android Studio\jbr\bin\java.exe" (
        set "JAVA_HOME=C:\Program Files\Android\Android Studio\jbr"
        set "PATH=%JAVA_HOME%\bin;%PATH%"
    ) else (
        echo   [ERRO] Java nao encontrado!
        echo   Instale o JDK 17: https://adoptium.net/
        echo.
        pause
        exit /b 1
    )
)

:: Check for ANDROID_HOME
if "%ANDROID_HOME%"=="" (
    if exist "%LOCALAPPDATA%\Android\Sdk" (
        set ANDROID_HOME=%LOCALAPPDATA%\Android\Sdk
    ) else (
        echo   [ERRO] Android SDK nao encontrado!
        echo   Instale o Android Studio: https://developer.android.com/studio
        echo.
        pause
        exit /b 1
    )
)

echo   [INFO] ANDROID_HOME: %ANDROID_HOME%
echo.

:: Copy latest HTML to assets
echo   [1/4] Copiando HTML para assets...
if exist "..\stemplay_library.html" (
    powershell -NoProfile -Command "(Get-Content -LiteralPath '..\stemplay_library.html' -Raw -Encoding UTF8) -replace 'const D=\[.*?\];','const D={courses_json};' | Set-Content -LiteralPath 'app\src\main\assets\stemplay_library.html' -Encoding UTF8" 2>nul
    echo   [ OK ] HTML copiado (placeholder restaurado)
) else (
    echo   [INFO] Usando HTML existente nos assets
)

:: Build debug APK
echo   [2/4] Buildando APK debug...
call gradlew.bat assembleDebug
if errorlevel 1 (
    echo.
    echo   [ERRO] Build falhou!
    echo   Verifique se o Android Studio esta instalado.
    echo.
    pause
    exit /b 1
)

echo   [ OK ] APK buildado com sucesso!
echo.

:: Show APK location
set APK_PATH=app\build\outputs\apk\debug\app-debug.apk
if exist "%APK_PATH%" (
    copy /Y "%APK_PATH%" "..\app-debug.apk" >nul
    echo   [3/4] APK copiado para a raiz do projeto: ..\app-debug.apk
    echo.
    echo   [4/4] Para instalar no celular:
    echo   1. Conecte o celular via USB
    echo   2. Ative "Depuracao USB" nas configuracoes
    echo   3. Execute: adb install -r %APK_PATH%
    echo.
    echo   Ou copie o APK para o celular e instale manualmente.
    echo.
) else (
    echo   [AVISO] APK nao encontrado em %APK_PATH%
)

pause
