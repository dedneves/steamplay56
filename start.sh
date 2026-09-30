#!/bin/bash
# StemPlay Library - Launcher Linux
cd "$(dirname "$0")"

echo ""
echo "  =============================================="
echo "     StemPlay Library - Inicializacao (Linux)"
echo "  =============================================="
echo ""

# Verifica Python 3
if ! command -v python3 &> /dev/null; then
    echo "  [ERRO] Python3 nao encontrado!"
    echo "  Instale com:  sudo apt install python3 python3-pip"
    echo "  Ou:           sudo pacman -S python python-pip"
    exit 1
fi
echo "  [OK] Python3 detectado: $(python3 --version)"

# Verifica pip
if ! command -v pip3 &> /dev/null; then
    echo "  [ERRO] pip3 nao encontrado!"
    echo "  Instale com:  sudo apt install python3-pip"
    exit 1
fi

# Instala dependencias
echo ""
echo "  [1/3] Instalando dependencias..."
pip3 install --break-system-packages aiohttp tqdm qrcode pymupdf 2>/dev/null || \
pip3 install --user aiohttp tqdm qrcode pymupdf 2>/dev/null || \
pip3 install aiohttp tqdm qrcode pymupdf

# Verifica se instalou de verdade
python3 -c "import aiohttp" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "  [ERRO] Falha ao instalar dependencias."
    echo "  Tente manualmente:  pip3 install aiohttp tqdm qrcode pymupdf"
    exit 1
fi
echo "  [OK] Dependencias prontas"

# Permissao de execucao no launcher
chmod +x launcher.py 2>/dev/null

echo ""
echo "  [2/3] Iniciando launcher..."
echo ""

# Executa o launcher
python3 launcher.py
