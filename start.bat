@echo off
chcp 65001 >nul
title StemPlay Library
cd /d "%~dp0"

python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo   [ERRO] Python nao encontrado!
    echo   Baixe em: https://www.python.org/downloads/
    echo   Marque "Add Python to PATH" na instalacao.
    echo.
    pause
    exit /b 1
)

python -m pip install --upgrade pip >nul 2>&1
python -m pip install aiohttp tqdm qrcode pymupdf >nul 2>&1

python -c "import aiohttp" >nul 2>&1
if errorlevel 1 (
    echo   [ERRO] Falha ao instalar dependencias.
    pause
    exit /b 1
)

python launcher.py
pause
