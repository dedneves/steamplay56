#!/usr/bin/env python3
"""
FALA DED AQUI ESSA PARTE E A PARTE MANEIRA!!! SE VOCE QUISER SABER MAIS VA NOS FORUNS AIONHTTP LA TEM VARIAS COISAS MANEIRAS QUE VOCE DEVERIA VER TAMBEM
"""
import asyncio
import aiohttp
import xml.etree.ElementTree as ET
from urllib.parse import unquote
import sys, os

# Protecao de encoding (Windows)
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

S3_BASE = "https://stemplay-videos.s3.us-east-2.amazonaws.com/"
NAMESPACE = "{http://s3.amazonaws.com/doc/2006-03-01/}"
OUTPUT_PDFS = "pdfs_found.txt"

async def fetch_xml(session, params):
    base_url = S3_BASE.rstrip("/")
    async with session.get(base_url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
        if resp.status != 200:
            text = await resp.text()
            return None, f"Erro {resp.status}: {text[:200]}"
        return await resp.text(), None

async def list_directories(session, prefix=""):
    params = {"list-type": "2", "delimiter": "/", "max-keys": "1000"}
    if prefix:
        params["prefix"] = prefix

    xml_data, err = await fetch_xml(session, params)
    if err:
        return [], [], err

    root = ET.fromstring(xml_data)
    dirs = []
    for cp in root.findall(f"{NAMESPACE}CommonPrefixes"):
        prefix_elem = cp.find(f"{NAMESPACE}Prefix")
        if prefix_elem is not None and prefix_elem.text:
            dirs.append(prefix_elem.text)

    files = []
    for content in root.findall(f"{NAMESPACE}Contents"):
        key_elem = content.find(f"{NAMESPACE}Key")
        size_elem = content.find(f"{NAMESPACE}Size")
        if key_elem is not None and size_elem is not None:
            files.append({"key": unquote(key_elem.text), "size": int(size_elem.text)})

    return dirs, files, None

async def find_all_pdfs(session, prefix=""):
    pdfs = []
    params = {"list-type": "2", "prefix": prefix, "max-keys": "1000"}
    continuation_token = None

    while True:
        if continuation_token:
            params["continuation-token"] = continuation_token

        xml_data, err = await fetch_xml(session, params)
        if err:
            print(f"   [ERRO] {err}")
            break

        root = ET.fromstring(xml_data)

        for content in root.findall(f"{NAMESPACE}Contents"):
            key_elem = content.find(f"{NAMESPACE}Key")
            size_elem = content.find(f"{NAMESPACE}Size")
            if key_elem is not None and key_elem.text:
                key = unquote(key_elem.text)
                if key.lower().endswith(".pdf"):
                    size = int(size_elem.text) if size_elem is not None else 0
                    pdfs.append({"key": key, "size": size})

        is_truncated = root.find(f"{NAMESPACE}IsTruncated")
        next_token = root.find(f"{NAMESPACE}NextContinuationToken")

        if (is_truncated is not None and is_truncated.text.lower() == "true"
                and next_token is not None and next_token.text):
            continuation_token = next_token.text
        else:
            break

    return pdfs

async def main():
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0"
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        print("  [INFO] Mapeando o bucket (listando pastas raiz)...")

        root_dirs, root_files, err = await list_directories(session, prefix="")
        if err:
            print(f"  [ERRO] {err}")
            return

        print(f"  [INFO] Pastas raiz encontradas: {len(root_dirs)}")
        for d in root_dirs:
            print(f"     - {d}")

        pdf_related_dirs = []
        for d in root_dirs:
            d_lower = d.lower().rstrip("/")
            if any(k in d_lower for k in ["pdf", "course", "material", "content",
                                          "lesson", "class", "aula", "ebook", "book", "modul"]):
                pdf_related_dirs.append(d)

        if not pdf_related_dirs:
            print("  [AVISO] Nenhuma pasta obvia. Varrendo todas...")
            pdf_related_dirs = [d for d in root_dirs
                                if not d.startswith(("Annotations/", "Activities/"))]

        print(f"  [INFO] Pastas a varrer: {len(pdf_related_dirs)}")
        print("  [INFO] Buscando PDFs...")

        all_pdfs = []
        for dir_prefix in pdf_related_dirs:
            print(f"     Varrendo: {dir_prefix}")
            pdfs = await find_all_pdfs(session, prefix=dir_prefix)
            if pdfs:
                print(f"        + {len(pdfs)} PDFs")
                all_pdfs.extend(pdfs)
            else:
                print(f"        (nenhum PDF)")
            await asyncio.sleep(0.1)

        print("  " + "=" * 46)
        print(f"  [RESULTADO] Total de PDFs: {len(all_pdfs)}")

        if all_pdfs:
            with open(OUTPUT_PDFS, "w", encoding="utf-8") as f:
                for pdf in all_pdfs:
                    f.write(f"{S3_BASE}{pdf['key']}\n")

            total_mb = sum(p['size'] for p in all_pdfs) / (1024 * 1024)
            print(f"  [INFO] Lista salva em: {OUTPUT_PDFS}")
            print(f"  [INFO] Tamanho total: {total_mb:.1f} MB ({total_mb/1024:.1f} GB)")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n  [INFO] Interrompido.")
        sys.exit(0)
