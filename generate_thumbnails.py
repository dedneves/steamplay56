#!/usr/bin/env python3
"""
Gera thumbnails da primeira pagina de cada PDF
Usa PyMuPDF (fitz) - instalar: pip install pymupdf
"""
import os, sys, hashlib
from pathlib import Path
from urllib.request import urlopen, Request

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

PDFS_FILE = "pdfs_found.txt"
THUMBS_DIR = "thumbnails"
MAX_THUMBS = 300  # limite pra nao demorar horas
LARGURA = 240

def carregar_urls():
    with open(PDFS_FILE) as f:
        return [l.strip() for l in f if l.strip()]

def url_para_hash(url):
    return hashlib.md5(url.encode()).hexdigest()

def gerar_thumbnails():
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("  [ERRO] PyMuPDF nao instalado!")
        print("  Instale:  pip install pymupdf")
        print("  Pulando geracao de thumbnails (usando placeholders)")
        return

    os.makedirs(THUMBS_DIR, exist_ok=True)
    urls = carregar_urls()[:MAX_THUMBS]
    print(f"  [INFO] Gerando ate {len(urls)} thumbnails...")

    for i, url in enumerate(urls, 1):
        h = url_para_hash(url)
        out_path = os.path.join(THUMBS_DIR, f"{h}.jpg")
        if os.path.exists(out_path):
            continue

        sys.stdout.write(f'\r  [{i}/{len(urls)}] {url.split("/")[-1][:40]:<40}')
        sys.stdout.flush()

        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(req, timeout=15) as resp:
                data = resp.read()

            doc = fitz.open(stream=data, filetype="pdf")
            page = doc[0]
            zoom = LARGURA / page.rect.width
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            pix.save(out_path)
            doc.close()
        except Exception:
            pass  # silencioso - usa placeholder

    print()
    print(f"  [ OK ] Thumbnails salvos em {THUMBS_DIR}/")

if __name__ == "__main__":
    gerar_thumbnails()
