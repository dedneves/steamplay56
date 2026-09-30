#!/bin/bash
# StemPlay Android - Build Script
cd "$(dirname "$0")"

echo ""
echo "  StemPlay Android - Builder"
echo "  ═══════════════════════════"
echo ""

# Check for Java
if ! command -v java &> /dev/null; then
    echo "  [ERRO] Java nao encontrado!"
    echo "  Instale o JDK 17: https://adoptium.net/"
    exit 1
fi

# Check for Android SDK
if [ -z "$ANDROID_HOME" ]; then
    if [ -d "$HOME/Library/Android/sdk" ]; then
        export ANDROID_HOME="$HOME/Library/Android/sdk"
    elif [ -d "$HOME/Android/Sdk" ]; then
        export ANDROID_HOME="$HOME/Android/Sdk"
    else
        echo "  [ERRO] Android SDK nao encontrado!"
        echo "  Instale o Android Studio: https://developer.android.com/studio"
        exit 1
    fi
fi

echo "  [INFO] ANDROID_HOME: $ANDROID_HOME"
echo ""

# Copy latest HTML to assets
echo "  [1/4] Copiando HTML para assets..."
if [ -f "../stemplay_library.html" ]; then
    cp "../stemplay_library.html" "app/src/main/assets/stemplay_library.html"
    echo "  [ OK ] HTML copiado"
else
    echo "  [INFO] Usando HTML existente nos assets"
fi

# Build debug APK
echo "  [2/4] Buildando APK debug..."
chmod +x gradlew
./gradlew assembleDebug
if [ $? -ne 0 ]; then
    echo ""
    echo "  [ERRO] Build falhou!"
    exit 1
fi

echo "  [ OK ] APK buildado com sucesso!"
echo ""

# Show APK location
APK_PATH="app/build/outputs/apk/debug/app-debug.apk"
if [ -f "$APK_PATH" ]; then
    echo "  [3/4] APK encontrado em: $APK_PATH"
    echo "  [4/4] Para instalar: adb install $APK_PATH"
    echo ""
else
    echo "  [AVISO] APK nao encontrado em $APK_PATH"
fi
