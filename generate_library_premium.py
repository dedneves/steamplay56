#!/usr/bin/env python3
"""
Gera a biblioteca HTML (com reader interno Steamplay 2) a partir de pdfs_found.txt
"""
import re, json, sys
from pathlib import Path
from collections import defaultdict

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


def parse_pdf_info(url):
    """Parse v12.1 - corrige Student/Teacher/Workbook e Capitulo/Unidade, sem mudar visual"""
    filename = url.split("/")[-1].replace(".pdf", "")
    parts = url.split("/")
    course_raw = parts[4] if len(parts) > 4 else "OUTROS"
    course_clean = re.sub(r'[-_](TEACHER|STUDENT|WORKBOOK)$', '', course_raw, flags=re.IGNORECASE)
    # Title case mas preserva siglas curtas legiveis
    course = course_clean.replace("-", " ").replace("_", " ").title()

    fn_up = filename.upper()
    url_up = url.upper()
    # Tokens para classificacao estrita (evita substring falso)
    tokens = re.split(r'[-_\s\.]+', fn_up)
    has_workbook = "WORKBOOK" in tokens or "WORKBOOK" in fn_up
    has_student_book = "STUDENT" in fn_up and "BOOK" in fn_up
    has_teacher = "TEACHER" in tokens or fn_up.endswith("_TEACHER") or fn_up.endswith("-TEACHER") or fn_up.endswith("_TEACHER")
    has_student = "STUDENT" in tokens
    path_is_teacher = "/TEACHER/" in url_up and "/STUDENT/" not in url_up
    path_is_student = "/STUDENT/" in url_up
    path_is_workbook = "/WORKBOOK/" in url_up

    # Prioridade corrigida: Workbook > Student-Book > Student > Teacher
    if has_workbook:
        material_type = "Workbook"
    elif has_student_book:
        material_type = "Student"
    elif has_student and has_teacher:
        material_type = "Student"
    elif has_student:
        material_type = "Student"
    elif has_teacher:
        material_type = "Teacher"
    elif path_is_workbook:
        material_type = "Workbook"
    elif path_is_student:
        material_type = "Student"
    elif path_is_teacher:
        material_type = "Teacher"
    else:
        material_type = "Standard"

    # --- Extracao de numeros com suporte a Capitulo/Unidade ---
    lesson_m = re.search(r'(?:Aula|Lesson|Class)\s*0*(\d+)', filename, re.IGNORECASE)
    unit_m = re.search(r'(?:Unit|Unidade|Und)\s*0*(\d+)', filename, re.IGNORECASE)
    if not unit_m:
        unit_m = re.search(r'[_-]U0*(\d+)[_-]', filename, re.IGNORECASE)
    module_m = re.search(r'(?:Modulo|_M|[-_]M)0*(\d+)', filename, re.IGNORECASE)
    checkpoint_m = re.search(r'Checkpoint\s*0*(\d+)', filename, re.IGNORECASE)
    capitulo_m = re.search(r'Capitulo\s*0*(\d+)', filename, re.IGNORECASE)

    lesson_num = int(lesson_m.group(1)) if lesson_m else None
    unit_num = int(unit_m.group(1)) if unit_m else None
    module_num = int(module_m.group(1)) if module_m else None
    checkpoint_num = int(checkpoint_m.group(1)) if checkpoint_m else None
    capitulo_num = int(capitulo_m.group(1)) if capitulo_m else None

    display_name = None
    if lesson_num is not None:
        display_name = f"Aula {lesson_num:02d}"
    elif checkpoint_num is not None:
        display_name = f"Checkpoint {checkpoint_num:02d}"
    elif capitulo_num is not None:
        display_name = f"Capítulo {capitulo_num:02d}"
    elif unit_num is not None:
        display_name = f"Unidade {unit_num:02d}"
    elif module_num is not None:
        display_name = f"Modulo {module_num}"

    if not display_name:
        keywords = [
            (r'Grammar\s*Reference', 'Grammar Reference'),
            (r'Checkpoint\s*Key', 'Checkpoint Key'),
            (r'Answer\s*Key', 'Answer Key'),
            (r'Audio\s*Scripts?', 'Audio Script'),
            (r'Extra\s*Resources?', 'Extra Resources'),
            (r'Workbook\s*Answer\s*Key', 'Workbook Answer Key'),
            (r'Consolidation.*Key', 'Consolidation Key'),
            (r'Workbook(?!Answer)', 'Workbook'),
            (r'Unit\s*00', 'Unit 00'),
            (r'Teacher\s*Book', 'Teacher Book'),
            (r'Student\s*Book', 'Student Book'),
            (r'Song\s*Book', 'Song Book'),
        ]
        for pattern, name in keywords:
            if re.search(pattern, filename, re.IGNORECASE):
                display_name = name
                break

    if not display_name:
        segments = re.split(r'[-_]', filename)
        useless = {'ENGLISH', 'TEEN1', 'TEEN2', 'TEEN3', 'JUNIOR', 'PLENO',
                   'STUDENT', 'TEACHER', 'BOOK', 'WORKBOOK', 'COM', 'DE',
                   'AO', 'LV1', 'LV2', 'I', 'II', 'III', 'INICIANTE', 'CB', 'HAPPY', 'KIDS', 'SONG'}
        meaningful = [s for s in segments if s.upper() not in useless and len(s) > 2 and not s.isdigit()]
        if meaningful:
            display_name = " ".join(meaningful[-2:]).title() if len(meaningful) > 1 else meaningful[0].title()
        else:
            display_name = filename.replace("_", " ").replace("-", " ").title()

    # Agrupamento e ordenacao - Geral por ultimo (999) para nao misturar com Aulas
    if checkpoint_num is not None:
        sort_key = (0, 0, checkpoint_num)
        group_name = "Checkpoints"
    elif capitulo_num is not None:
        sort_key = (unit_num or 0, capitulo_num, 0)
        group_name = f"Unidade {unit_num:02d}" if unit_num is not None else "Capítulos"
    elif module_num is not None and lesson_num is not None:
        sort_key = (module_num, lesson_num, 0)
        group_name = f"Modulo {module_num}"
    elif module_num is not None:
        sort_key = (module_num, 0, 0)
        group_name = f"Modulo {module_num}"
    elif unit_num is not None:
        sort_key = (unit_num, 0, 0)
        group_name = "Unidades"
    else:
        sort_key = (999, 0, 0)
        group_name = "Geral"

    return {
        "url": url, "course": course, "course_raw": course_raw,
        "display_name": display_name, "material_type": material_type,
        "lesson_num": lesson_num, "unit_num": unit_num, "module_num": module_num,
        "checkpoint_num": checkpoint_num, "capitulo_num": capitulo_num, "sort_key": sort_key, "group_name": group_name
    }


def main():
    input_file = "pdfs_found.txt"
    output_html = "stemplay_library.html"

    if not Path(input_file).exists():
        print(f"  [ERRO] {input_file} nao encontrado!")
        return

    print("  [INFO] Carregando PDFs...")
    with open(input_file, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip()]

    print(f"  [INFO] Parseando {len(urls)} arquivos...")
    pdfs = [parse_pdf_info(url) for url in urls]

    # Deduplicacao por URL
    urls_vistas = set()
    pdfs_unicos = []
    for pdf in pdfs:
        if pdf['url'] not in urls_vistas:
            urls_vistas.add(pdf['url'])
            pdfs_unicos.append(pdf)
    pdfs = pdfs_unicos

    # Deduplicacao por conteudo
    vistos = {}
    pdfs_dedup = []
    for pdf in pdfs:
        chave = (pdf['course'].lower(), pdf['display_name'].lower(),
                 pdf['material_type'].lower(), pdf['group_name'].lower())
        if chave not in vistos:
            vistos[chave] = True
            pdfs_dedup.append(pdf)
    print(f"  [INFO] Deduplicacao: {len(pdfs_unicos)} -> {len(pdfs_dedup)} arquivos")
    pdfs = pdfs_dedup

    courses_dict = defaultdict(list)
    for pdf in pdfs:
        courses_dict[pdf['course']].append(pdf)

    courses = [{"name": n, "items": sorted(it, key=lambda x: x['sort_key'])}
               for n, it in sorted(courses_dict.items())]

    courses_json = json.dumps(courses, ensure_ascii=False)
    print("  [INFO] Gerando biblioteca HTML...")

    html_template = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover,maximum-scale=5">
<meta name="theme-color" content="#0a0a1a">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<title>StemPlay Library</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent}
:root{--bg:#0a0a1a;--bg2:#12122a;--bg3:#1a1a3e;--accent:#6c5ce7;--accent2:#a29bfe;--glow:rgba(108,92,231,.2);--txt:#f0f0ff;--txt2:#8888aa;--card:rgba(26,26,62,.7);--border:#2a2a5e;--ok:#00cec9;--warn:#fdcb6e;--radius:14px;--trans:.3s ease;--ease-out-expo:cubic-bezier(.16,1,.3,1)}
html[data-theme="light"]{--bg:#f4f6fb;--bg2:#ffffff;--bg3:#e8ecf5;--accent:#6c5ce7;--accent2:#5a4bd1;--glow:rgba(108,92,231,.1);--txt:#1a1a2e;--txt2:#666;--card:rgba(255,255,255,.9);--border:#dde1ea}
html{scroll-behavior:smooth}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--txt);min-height:100vh;min-height:100dvh;padding-bottom:calc(70px + env(safe-area-inset-bottom,0px));overflow-x:hidden;transition:background var(--trans),color var(--trans)}
.header{position:sticky;top:0;background:var(--bg2);border-bottom:1px solid var(--border);z-index:100;transition:background var(--trans),border-color var(--trans)}
.header-top{display:flex;align-items:center;justify-content:space-between;padding:.875rem 1rem;gap:.75rem}
.logo{font-size:1.25rem;font-weight:900;background:linear-gradient(135deg,var(--accent),#fd79a8);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;letter-spacing:-.5px}
.theme-btn{position:relative;width:44px;height:44px;border-radius:50%;background:var(--bg3);border:1.5px solid var(--border);color:var(--txt);cursor:pointer;display:flex;align-items:center;justify-content:center;transition:background var(--trans),transform .15s;font-size:1.2rem;touch-action:manipulation}
.theme-btn:active{transform:scale(.9) rotate(20deg)}
.stats-row{display:flex;gap:.5rem;padding:0 1rem .75rem;overflow-x:auto;scrollbar-width:none;-webkit-overflow-scrolling:touch}
.stats-row::-webkit-scrollbar{display:none}
.chip{background:var(--bg3);padding:.4rem .85rem;border-radius:20px;font-size:.75rem;white-space:nowrap;border:1px solid var(--border);flex-shrink:0;font-weight:600}
.chip b{color:var(--accent2);margin-right:.25rem;font-weight:800}
.search-wrap{padding:0 1rem .75rem}
.search{width:100%;padding:.875rem 1rem;background:var(--bg3);border:2px solid var(--border);border-radius:var(--radius);color:var(--txt);font-size:1rem;transition:border-color .2s,box-shadow .2s;touch-action:manipulation;-webkit-appearance:none}
.search:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px var(--glow)}
.search::placeholder{color:var(--txt2)}
.filters{display:flex;gap:.5rem;padding:0 1rem 1rem;overflow-x:auto;scrollbar-width:none;-webkit-overflow-scrolling:touch}
.filters::-webkit-scrollbar{display:none}
.fbtn{padding:.5rem 1rem;background:var(--bg3);border:1.5px solid var(--border);border-radius:20px;color:var(--txt2);cursor:pointer;font-weight:600;font-size:.8rem;white-space:nowrap;flex-shrink:0;transition:background .2s,border-color .2s,color .2s,transform .1s}
.fbtn.active{background:var(--accent);border-color:var(--accent);color:#fff}
.fbtn:active{transform:scale(.95)}
.main{padding:0 .75rem;max-width:1400px;margin:0 auto}
.course{background:var(--bg2);border-radius:var(--radius);margin-bottom:.75rem;border:1px solid var(--border);overflow:hidden;animation:fadeUp .35s var(--ease-out-expo) both}
@keyframes fadeUp{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
.chdr{padding:.875rem 1rem;cursor:pointer;display:flex;justify-content:space-between;align-items:center;user-select:none;-webkit-user-select:none;min-height:52px;transition:background .2s}
.chdr:active{background:var(--bg3)}
.ctitle{font-size:.95rem;font-weight:700;flex:1;margin-right:.5rem;line-height:1.35}
.ccount{background:var(--accent);color:#fff;padding:.2rem .6rem;border-radius:10px;font-size:.7rem;font-weight:800;flex-shrink:0}
.carrow{color:var(--txt2);transition:transform .3s var(--ease-out-expo);font-size:.9rem;margin-left:.5rem;flex-shrink:0}
.course.open .carrow{transform:rotate(180deg)}
.cbody{display:none;padding:0 1rem 1rem}
.course.open .cbody{display:block}
.gtitle{color:var(--accent2);font-size:.75rem;font-weight:700;margin:.75rem 0 .5rem;text-transform:uppercase;letter-spacing:.5px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:.6rem}
@media(max-width:480px){.grid{grid-template-columns:1fr}}
@media(min-width:768px){.grid{grid-template-columns:repeat(auto-fill,minmax(240px,1fr))}}
.card{background:var(--card);border-radius:var(--radius);color:var(--txt);border:1.5px solid var(--border);display:flex;flex-direction:column;overflow:hidden;transition:transform .18s ease,border-color .18s,box-shadow .18s;content-visibility:auto;contain-intrinsic-size:auto 300px}
.card:active{transform:scale(.98)}
@media(min-width:768px){.card:hover{transform:translateY(-3px);border-color:var(--accent);box-shadow:0 8px 24px var(--glow)}}
.thumb-wrap{position:relative;width:100%;aspect-ratio:4/3;background:var(--bg3);overflow:hidden;border-bottom:1px solid var(--border)}
.placeholder{width:100%;height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:.5rem;position:relative;overflow:hidden;transition:transform .3s var(--ease-out-expo)}
.ph-letter{font-size:3.5rem;font-weight:900;color:rgba(255,255,255,.95);letter-spacing:-2px;z-index:1;line-height:1}
.ph-type{font-size:.65rem;font-weight:700;text-transform:uppercase;letter-spacing:2px;color:rgba(255,255,255,.9);padding:.2rem .5rem;border-radius:8px;background:rgba(0,0,0,.2);z-index:1}
.ph-course{position:absolute;bottom:.4rem;left:.4rem;right:.4rem;font-size:.6rem;color:rgba(255,255,255,.85);font-weight:600;text-align:center;z-index:1;line-height:1.2;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.thumb-canvas{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;display:none;background:var(--bg3);opacity:0;transition:opacity .4s ease}
.thumb-wrap.has-thumb .thumb-canvas{display:block;opacity:1}
.thumb-wrap.has-thumb .placeholder{display:none}
.thumb-wrap.loading::after{content:'';position:absolute;inset:0;background:linear-gradient(90deg,transparent,rgba(255,255,255,.08),transparent);animation:shimmer 1.5s infinite}
@keyframes shimmer{0%{transform:translateX(-100%)}100%{transform:translateX(100%)}}
.card-body{padding:.75rem .875rem;display:flex;flex-direction:column;gap:.4rem;flex:1}
.card-name{font-weight:700;font-size:.9rem;line-height:1.3;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.card-badges{display:flex;gap:.25rem;flex-wrap:wrap}
.badge{padding:.15rem .5rem;border-radius:8px;font-size:.6rem;font-weight:800;text-transform:uppercase;transition:all var(--trans)}
.b-teacher{background:var(--warn);color:#1a1a2e}
.b-workbook{background:var(--ok);color:#1a1a2e}
.b-student,.b-standard{background:var(--accent);color:#fff}
.card-actions{display:flex;gap:.35rem;margin-top:auto;padding-top:.4rem}
.abtn{flex:1;padding:.6rem;border:none;border-radius:10px;font-size:.75rem;font-weight:700;cursor:pointer;text-align:center;display:flex;align-items:center;justify-content:center;gap:.3rem;color:inherit;touch-action:manipulation;min-height:44px;transition:transform .15s var(--ease-out-expo),background .15s,box-shadow .15s}
.abtn:hover{transform:translateY(-1px)}
.abtn:active{transform:scale(.96)}
.btn-read{background:linear-gradient(135deg,var(--accent),#fd79a8);color:#fff}
.btn-dl{background:var(--bg3);color:var(--txt);border:1.5px solid var(--border)}
.btn-fav{background:none;border:1.5px solid var(--border);color:var(--txt2);width:44px;flex:none;font-size:1.1rem;border-radius:10px;padding:0;transition:transform .2s var(--ease-out-expo),color .2s,border-color .2s}
.btn-fav:hover{transform:scale(1.05)}
.btn-fav.is-fav{color:var(--warn);border-color:var(--warn)}
.bottom-nav{position:fixed;bottom:0;left:0;right:0;background:var(--bg2);border-top:1px solid var(--border);display:flex;justify-content:space-around;padding:.5rem 0 calc(.5rem + env(safe-area-inset-bottom,0px));z-index:100;transition:background var(--trans)}
.nitem{background:none;border:none;color:var(--txt2);padding:.5rem .75rem;cursor:pointer;display:flex;flex-direction:column;align-items:center;gap:.2rem;font-size:.65rem;font-weight:600;transition:color .2s,transform .1s;touch-action:manipulation;min-width:60px}
.nitem.active{color:var(--accent)}
.nitem:active{opacity:.7;transform:scale(.9)}
.nicon{font-size:.9rem;font-weight:800;letter-spacing:-.5px}
.toast{position:fixed;bottom:calc(80px + env(safe-area-inset-bottom,0px));left:50%;transform:translateX(-50%) translateY(100px);background:var(--bg2);color:var(--txt);padding:.7rem 1.25rem;border-radius:25px;box-shadow:0 8px 25px rgba(0,0,0,.25);z-index:7000;opacity:0;transition:all .35s var(--ease-out-expo);pointer-events:none;border:1px solid var(--border);font-size:.85rem;font-weight:600;white-space:nowrap;max-width:90vw;overflow:hidden;text-overflow:ellipsis}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
.empty{text-align:center;padding:3rem 1rem;color:var(--txt2);animation:fadeUp .4s ease}
.empty-icon{font-size:1.5rem;font-weight:800;margin-bottom:1rem;color:var(--accent2)}
@media(min-width:768px){body{padding-bottom:0}.bottom-nav{display:none}.main{padding:0 2rem}.header-top,.search-wrap,.filters,.stats-row{padding-left:2rem;padding-right:2rem}}
/* GATE ID */
#idGate{position:fixed;inset:0;z-index:9999;background:var(--bg);display:flex;align-items:center;justify-content:center;padding:1.5rem;transition:opacity .45s var(--ease-out-expo),visibility .45s}
#idGate.hidden{opacity:0;visibility:hidden;pointer-events:none}
.gate-card{background:var(--bg2);border:1.5px solid var(--border);border-radius:20px;padding:2rem 1.5rem;max-width:380px;width:100%;text-align:center;box-shadow:0 20px 60px rgba(0,0,0,.4);animation:fadeUp .5s var(--ease-out-expo) both}
.gate-card.negado{animation:shake .45s ease}
@keyframes shake{10%,90%{transform:translateX(-2px)}20%,80%{transform:translateX(4px)}30%,50%,70%{transform:translateX(-7px)}40%,60%{transform:translateX(7px)}}
.gate-logo{font-size:1.8rem;font-weight:900;background:linear-gradient(135deg,var(--accent),#fd79a8);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin-bottom:.25rem}
.gate-sub{color:var(--txt2);font-size:.9rem;margin-bottom:1.25rem;font-weight:600}
.gate-input{width:100%;padding:.9rem 1rem;background:var(--bg3);border:2px solid var(--border);border-radius:12px;color:var(--txt);font-size:1rem;text-align:center;letter-spacing:1px;font-weight:700;margin-bottom:1rem;transition:border-color .2s,box-shadow .2s}
.gate-input:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px var(--glow)}
.gate-btn{width:100%;padding:.9rem;background:linear-gradient(135deg,var(--accent),#8b5cf6);border:none;border-radius:12px;color:#fff;font-weight:800;font-size:1rem;cursor:pointer;transition:transform .15s var(--ease-out-expo),opacity .2s}
.gate-btn:active{transform:scale(.98)}
.gate-hint{margin-top:.75rem;font-size:.72rem;color:var(--txt2);line-height:1.4}
/* BULK PANEL */
.bulk-toggle{width:40px;height:40px;border-radius:10px;background:var(--bg3);border:1.5px solid var(--border);color:var(--txt);cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:1.15rem;transition:background .2s,border-color .2s,transform .2s var(--ease-out-expo);flex-shrink:0}
.bulk-toggle:active{transform:scale(.92)}
.bulk-toggle.open{background:var(--accent);border-color:var(--accent);color:#fff}
.bulk-panel{overflow:hidden;max-height:0;opacity:0;transition:max-height .45s var(--ease-out-expo),opacity .3s,padding .3s;background:var(--bg2);border-top:1px solid transparent}
.bulk-panel.open{max-height:420px;opacity:1;border-top-color:var(--border);padding:.85rem 1rem 1rem}
.bulk-head{display:flex;gap:.5rem;align-items:center;margin-bottom:.65rem;flex-wrap:wrap}
.bulk-search{flex:1;min-width:140px;padding:.55rem .8rem;background:var(--bg3);border:1.5px solid var(--border);border-radius:10px;color:var(--txt);font-size:.82rem;transition:border-color .2s}
.bulk-search:focus{outline:none;border-color:var(--accent)}
.bulk-stats{font-size:.75rem;color:var(--txt2);font-weight:700;white-space:nowrap}
.bulk-stats b{color:var(--accent2)}
.course-sel-list{max-height:220px;overflow-y:auto;border:1px solid var(--border);border-radius:10px;background:var(--bg)}
.course-sel-item{display:flex;align-items:center;gap:.6rem;padding:.55rem .75rem;border-bottom:1px solid var(--border);cursor:pointer;transition:background .15s}
.course-sel-item input{width:16px;height:16px;accent-color:var(--accent)}
.course-sel-info{flex:1;min-width:0}
.course-sel-name{font-size:.82rem;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.course-sel-count{font-size:.68rem;color:var(--txt2)}
.course-sel-item.selected{background:rgba(108,92,231,.08)}
.bulk-actions{display:flex;gap:.4rem;margin-top:.65rem;flex-wrap:wrap}
.bulk-actions .abtn{flex:1;min-width:90px;padding:.55rem;font-size:.72rem;min-height:38px}
.btn-ghost{background:var(--bg3);color:var(--txt);border:1.5px solid var(--border)}
.bulk-progress{margin-top:.6rem;height:5px;background:var(--bg3);border-radius:3px;overflow:hidden;display:none}
.bulk-progress .bar{height:100%;background:linear-gradient(90deg,var(--accent),#fd79a8);width:0%;transition:width .3s var(--ease-out-expo)}
.bulk-progress-label{margin-top:.3rem;font-size:.7rem;color:var(--txt2);text-align:center;display:none}
/* BANNER REDE */
#netBanner{position:fixed;top:0;left:0;right:0;z-index:5000;background:#d63031;color:#fff;text-align:center;padding:.55rem;font-size:.85rem;font-weight:700;transform:translateY(-110%);transition:transform .35s var(--ease-out-expo)}
#netBanner.show{transform:translateY(0)}
/* TELA DE BLOQUEIO */
#blockedScreen{position:fixed;inset:0;z-index:99999;background:#0a0a1a;display:flex;align-items:center;justify-content:center;padding:1.5rem;opacity:0;visibility:hidden;transition:opacity .4s,visibility .4s;pointer-events:none}
#blockedScreen.show{opacity:1;visibility:visible;pointer-events:auto}
.bs-card{max-width:420px;text-align:center;background:#12122a;border:1.5px solid #2a2a5e;border-radius:20px;padding:2.5rem 1.5rem;animation:fadeUp .5s var(--ease-out-expo) both}
.bs-card h1{color:#ff6b6b;font-size:1.4rem;margin-bottom:.75rem}
.bs-card p{color:#8888aa;font-size:.9rem;line-height:1.5}
/* ============ READER "Steamplay 2" ============ */
#reader{position:fixed;inset:0;z-index:4000;background:#0d0d1f;display:flex;flex-direction:column;color:#f0f0ff;opacity:0;visibility:hidden;transition:opacity .18s ease,visibility .18s;pointer-events:none}
#reader.open{opacity:1;visibility:visible;pointer-events:auto}
.rd-head{display:flex;align-items:center;gap:.6rem;padding:.5rem .75rem;background:#12122a;border-bottom:1px solid #2a2a5e;flex-shrink:0}
.rd-brand{font-weight:900;font-size:1.1rem;background:linear-gradient(135deg,#6c5ce7,#fd79a8);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;white-space:nowrap}
.rd-title{flex:1;font-size:.8rem;color:#a29bfe;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.rd-sync{font-size:.65rem;color:#8888aa;white-space:nowrap;transition:color .3s}
.rd-sync.ok{color:#00cec9}
.rd-hbtn{background:#1a1a3e;border:1px solid #2a2a5e;color:#f0f0ff;border-radius:8px;padding:.4rem .7rem;font-size:.75rem;font-weight:700;cursor:pointer;white-space:nowrap;transition:background .2s,transform .1s}
.rd-hbtn:active{transform:scale(.95)}
.rd-tools{display:flex;align-items:center;gap:.35rem;padding:.4rem .6rem;background:#101024;border-bottom:1px solid #2a2a5e;overflow-x:auto;flex-shrink:0;scrollbar-width:none;-webkit-overflow-scrolling:touch}
.rd-tools::-webkit-scrollbar{display:none}
.rt{background:#1a1a3e;border:1px solid #2a2a5e;color:#f0f0ff;border-radius:8px;padding:.4rem .6rem;font-size:.72rem;font-weight:700;cursor:pointer;white-space:nowrap;flex-shrink:0;transition:background .2s,border-color .2s,color .2s,transform .1s}
.rt:active{transform:scale(.94)}
.rt.active{background:#6c5ce7;border-color:#6c5ce7;color:#fff;box-shadow:0 2px 12px rgba(108,92,231,.45)}
.rtb{background:#1a1a3e;border:1px solid #2a2a5e;color:#f0f0ff;width:34px;height:34px;border-radius:8px;cursor:pointer;font-size:1rem;flex-shrink:0;transition:background .2s,transform .1s}
.rtb:active{transform:scale(.9)}
.rd-sep{width:1px;height:24px;background:#2a2a5e;flex-shrink:0;margin:0 .25rem}
.rd-pagein{width:44px;padding:.35rem;background:#1a1a3e;border:1px solid #2a2a5e;border-radius:8px;color:#f0f0ff;text-align:center;font-size:.8rem}
.rd-zoomlbl{font-size:.75rem;color:#a29bfe;min-width:44px;text-align:center;font-weight:700}
.rd-sw{width:24px;height:24px;border-radius:50%;border:2px solid transparent;cursor:pointer;flex-shrink:0;transition:transform .15s var(--ease-out-expo),border-color .15s;padding:0}
.rd-sw.sel{border-color:#fff;transform:scale(1.15)}
.rd-size{width:80px;accent-color:#6c5ce7;flex-shrink:0}
.rd-body{display:flex;flex:1;min-height:0}
.rd-stage{flex:1;overflow:auto;background:#05050f;display:flex;justify-content:center;align-items:flex-start;padding:12px;touch-action:pan-x pan-y;overscroll-behavior:contain}
#rWrap{position:relative;flex-shrink:0;box-shadow:0 8px 40px rgba(0,0,0,.6);background:#fff}
#rPage{display:block;position:relative}
#rOverlay{display:block;position:absolute;top:0;left:0;z-index:5;touch-action:none}
#rLive{display:none;position:absolute;top:0;left:0;z-index:6;pointer-events:none;opacity:.35}
#rdLoading{position:absolute;inset:0;display:flex;flex-direction:column;gap:.8rem;align-items:center;justify-content:center;background:rgba(5,5,15,.8);color:#a29bfe;font-weight:700;z-index:30;font-size:.85rem;text-align:center;padding:1rem}
.spinner{width:34px;height:34px;border:3px solid rgba(108,92,231,.25);border-top-color:#6c5ce7;border-radius:50%;animation:spin .7s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
/* BLOCOS DE NOTA */
.note-block{position:absolute;z-index:10;background:#fff8b8;color:#222;border-radius:10px;box-shadow:0 6px 20px rgba(0,0,0,.45);display:flex;flex-direction:column;animation:notePop .22s var(--ease-out-expo) both;overflow:hidden;border:1px solid rgba(0,0,0,.12)}
@keyframes notePop{from{transform:scale(.6);opacity:0}to{transform:scale(1);opacity:1}}
.nb-head{display:flex;align-items:center;gap:.3rem;background:rgba(0,0,0,.08);padding:.25rem .45rem;font-size:.62rem;font-weight:800;cursor:grab;touch-action:none;user-select:none;-webkit-user-select:none}
.nb-head:active{cursor:grabbing}
.nb-label{flex:1;color:#6b5d00;letter-spacing:.3px}
.nb-btn{background:none;border:none;color:#6b5d00;font-weight:900;cursor:pointer;font-size:.75rem;padding:.05rem .25rem;border-radius:5px;line-height:1}
.nb-btn:hover{background:rgba(0,0,0,.1)}
.nb-body{flex:1;border:none;background:transparent;padding:.4rem .5rem;font-size:.72rem;resize:none;font-family:inherit;outline:none;color:#333;min-height:30px;line-height:1.4}
.note-block.min .nb-body{display:none}
.note-block.min{height:auto!important}
.nb-resize{position:absolute;right:0;bottom:0;width:18px;height:18px;cursor:nwse-resize;touch-action:none;opacity:.4}
.nb-resize::after{content:'';position:absolute;right:3px;bottom:3px;width:8px;height:8px;border-right:2px solid #6b5d00;border-bottom:2px solid #6b5d00;border-radius:0 0 3px 0}
.note-ghost{position:fixed;z-index:9000;width:110px;height:70px;background:#fff8b8;border-radius:10px;box-shadow:0 10px 30px rgba(0,0,0,.5);pointer-events:none;opacity:.85;transform:translate(-50%,-50%) rotate(-3deg)}
/* celular: menos sombra/animacao pesada = rolagem fluida */
@media (pointer:coarse){
.course{animation:none}
.card{transition:transform .12s}
#rWrap{box-shadow:0 4px 18px rgba(0,0,0,.5)}
.toast,.rd-sync{transition-duration:.15s}
}
</style>
<script src="https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/build/pdf.min.js"></script>
</head>
<body>
<div id="idGate" style="display:flex">
  <div class="gate-card" id="gateCard">
    <div class="gate-logo">StemPlay Library</div>
    <div class="gate-sub">Digite seu ID para acessar</div>
    <input type="text" id="gateInput" class="gate-input" placeholder="seu ID" autocomplete="off" autocorrect="off" spellcheck="false">
    <button type="button" class="gate-btn" id="gateEnter">Entrar →</button>
    <div class="gate-hint">Seu ID sincroniza desenhos e notas na nuvem.<br>Acesso ao material do professor somente com ID autorizado.</div>
  </div>
</div>
<div id="netBanner">Servidor desconectado — tentando reconectar...</div>
<div id="blockedScreen"><div class="bs-card"><h1>VIXEeeee...</h1><p>Alguém foi banido pelo visto 😅<br>Se você acha que foi injustiça, chama o administrador da StemPlay Library e pede pra te desbanir.</p></div></div>
<div class="header">
  <div class="header-top">
    <div style="display:flex;align-items:center;gap:.6rem">
      <div class="logo">StemPlay Library</div>
      <button class="bulk-toggle" id="bulkToggle" aria-label="Baixar cursos" title="Baixar cursos">☰</button>
      <button class="fbtn" id="idChip" title="Toque para trocar o ID" style="flex:none;max-width:150px;overflow:hidden;text-overflow:ellipsis;display:none">ID</button>
    </div>
    <button class="theme-btn" id="themeBtn" aria-label="Alternar tema">☾</button>
  </div>
  <div class="bulk-panel" id="bulkPanel">
    <div class="bulk-head">
      <input type="text" id="bulkSearch" class="bulk-search" placeholder="Pesquisar curso... ex: english teen2" autocomplete="off" spellcheck="false">
      <div class="bulk-stats"><b id="selCount">0</b> cursos · <b id="selFiles">0</b> livros</div>
    </div>
    <div class="course-sel-list" id="bulkList"></div>
    <div class="bulk-actions">
      <button class="abtn btn-ghost" id="bulkSelAll">Selecionar visíveis</button>
      <button class="abtn btn-ghost" id="bulkClear">Limpar</button>
      <button class="abtn btn-read" id="bulkDownload" style="flex:1.3">⬇ Baixar selecionados</button>
    </div>
    <div class="bulk-progress" id="bulkProgress"><div class="bar" id="bulkBar"></div></div>
    <div class="bulk-progress-label" id="bulkLabel"></div>
  </div>
  <div class="stats-row">
    <div class="chip"><b id="sT">0</b>materiais</div>
    <div class="chip"><b id="sC">0</b>cursos</div>
    <div class="chip"><b id="sV">0</b>visiveis</div>
  </div>
  <div class="search-wrap">
    <input type="text" class="search" id="searchBox" placeholder="Buscar curso, aula, modulo..." autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false">
  </div>
  <div class="filters" id="filterBar">
    <button class="fbtn active" data-t="all">Todos</button>
    <button class="fbtn" data-t="Standard">Padrao</button>
    <button class="fbtn" data-t="Teacher">Teacher</button>
    <button class="fbtn" data-t="Workbook">Workbook</button>
    <button class="fbtn" data-t="Student">Student</button>
  </div>
</div>
<div class="main" id="app"></div>
<div class="bottom-nav">
  <button class="nitem active" data-a="home"><span class="nicon">HOME</span>Inicio</button>
  <button class="nitem" data-a="courses"><span class="nicon">CURSOS</span>Cursos</button>
  <button class="nitem" data-a="fav"><span class="nicon">FAV</span>Favoritos</button>
  <button class="nitem" data-a="top"><span class="nicon">TOPO</span>Topo</button>
</div>
<div class="toast" id="toast"></div>

<!-- ============ READER Steamplay 2 ============ -->
<div id="reader">
  <div class="rd-head">
    <div class="rd-brand">Steamplay 2</div>
    <div class="rd-title" id="rdTitle">—</div>
    <div class="rd-sync" id="rdSync"></div>
    <button class="rd-hbtn" id="rdClose">✕ Fechar</button>
  </div>
  <div class="rd-tools">
    <button class="rtb" id="rdPrev" title="Pagina anterior">‹</button>
    <input class="rd-pagein" id="rdPageNum" type="number" min="1" value="1">
    <span class="rd-zoomlbl" id="rdTot">/ 0</span>
    <button class="rtb" id="rdNext" title="Proxima pagina">›</button>
    <span class="rd-sep"></span>
    <button class="rtb" id="rdZoomOut" title="Diminuir zoom">−</button>
    <span class="rd-zoomlbl" id="rdZoom">100%</span>
    <button class="rtb" id="rdZoomIn" title="Aumentar zoom">+</button>
    <button class="rt" id="rdFit">Ajustar</button>
    <span class="rd-sep"></span>
    <button class="rt" data-rt="draw">✎ Caneta</button>
    <button class="rt" data-rt="hl">▮ Marca-texto</button>
    <button class="rt" data-rt="erase">◻ Borracha</button>
    <span class="rd-sep"></span>
    <span id="rdColors" style="display:flex;gap:.3rem;flex-shrink:0"></span>
    <input class="rd-size" id="rdSize" type="range" min="2" max="24" value="5" title="Espessura">
    <span class="rd-sep"></span>
    <button class="rt" id="rdNoteBtn" title="Arraste até a página ou toque para criar">✚ Nota <b id="rdNoteCount">0</b></button>
    <button class="rt" id="rdUndo">↶ Desfazer</button>
    <button class="rt" id="rdClear">✕ Limpar pag.</button>
  </div>
  <div class="rd-body">
    <div class="rd-stage" id="rStage">
      <div id="rWrap">
        <canvas id="rPage"></canvas>
        <canvas id="rOverlay"></canvas>
        <canvas id="rLive"></canvas>
        <div id="rdLoading"><div class="spinner"></div>Carregando PDF...</div>
      </div>
    </div>
  </div>
</div>

<script>
const D={courses_json};
let cF='all',cS='',cV='home';
let favs=new Set(JSON.parse(localStorage.getItem('sp_favs')||'[]'));
let userId=localStorage.getItem('sp_userId')||'';
const $=id=>document.getElementById(id);
const $$=(s,p)=>(p||document).querySelectorAll(s);
function hashString(s){let h=0;for(let i=0;i<s.length;i++)h=((h<<5)-h)+s.charCodeAt(i);return Math.abs(h)}
function courseGradient(course){const h=hashString(course);const hue1=h%360;const hue2=(hue1+40)%360;const sat=65+(h%20);const lit=45+(h%15);return`linear-gradient(135deg,hsl(${hue1} ${sat}% ${lit}%) 0%,hsl(${hue2} ${sat}% ${lit-10}%) 100%)`}
let toastTimer;
function toast(m){const t=$('toast');t.textContent=m;t.classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>t.classList.remove('show'),2200)}
function rafThrottle(fn){let q=false;return(...a)=>{if(q)return;q=true;requestAnimationFrame(()=>{fn(...a);q=false})}}
async function downloadPDF(url,name){try{toast('Iniciando download...');const r=await fetch(url);if(!r.ok)throw 0;const b=await r.blob();const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download=name+'.pdf';document.body.appendChild(a);a.click();setTimeout(()=>{a.remove();URL.revokeObjectURL(a.href)},100);toast('Download iniciado')}catch(e){try{const r2=await fetch('/pdf?key='+encodeURIComponent(url));if(!r2.ok)throw 0;const b2=await r2.blob();const a2=document.createElement('a');a2.href=URL.createObjectURL(b2);a2.download=name+'.pdf';document.body.appendChild(a2);a2.click();setTimeout(()=>{a2.remove();URL.revokeObjectURL(a2.href)},100);toast('Download iniciado (proxy)')}catch(e2){window.open(url,'_blank');toast('Aberto em nova aba')}}}
function renderPlaceholder(course,type,url){const letter=course.charAt(0).toUpperCase();const bg=courseGradient(course);const safeUrl=(url||'').replace(/"/g,'&quot;');return`<div class="thumb-wrap" data-pdf="${safeUrl}"><canvas class="thumb-canvas" width="320" height="240"></canvas><div class="placeholder" style="background:${bg}"><div class="ph-letter">${letter}</div><div class="ph-type">${type}</div><div class="ph-course">${course}</div></div></div>`}
const _cardHtmlCache=new Map();
function buildCardHtml(i){const k=i.url;if(_cardHtmlCache.has(k))return _cardHtmlCache.get(k);const bc='b-'+i.material_type.toLowerCase();const isF=favs.has(i.url);let badges=`<span class="badge ${bc}">${i.material_type}</span>`;if(i.module_num)badges+=`<span class="badge" style="background:#8b5cf6;color:#fff">M${i.module_num}</span>`;if(i.unit_num)badges+=`<span class="badge" style="background:#ec4899;color:#fff">U${i.unit_num}</span>`;const h=`${renderPlaceholder(i.course,i.material_type,i.url)}<div class="card-body"><div class="card-name">${i.display_name}</div><div class="card-badges">${badges}</div><div class="card-actions"><button class="abtn btn-read">▶ Ler</button><button class="abtn btn-dl">Download</button><button class="abtn btn-fav${isF?' is-fav':''}">${isF?'★':'☆'}</button></div></div>`;_cardHtmlCache.set(k,h);return h}
function render(){const app=$('app');const frag=document.createDocumentFragment();let vc=0;const sl=cS.toLowerCase();D.forEach(c=>{const fi=visItems(c).filter(i=>{const ms=!sl||i.course.toLowerCase().includes(sl)||i.display_name.toLowerCase().includes(sl)||i.group_name.toLowerCase().includes(sl);const mf=cF==='all'||i.material_type===cF;if(cV==='fav')return favs.has(i.url);if(cV==='courses')return true;return ms&&mf});if(!fi.length)return;vc+=fi.length;const gs={};fi.forEach(i=>{(gs[i.group_name]=gs[i.group_name]||[]).push(i)});const ce=document.createElement('div');ce.className='course';ce.innerHTML=`<div class="chdr"><div class="ctitle">${c.name}</div><div class="ccount">${fi.length}</div><div class="carrow">&#9660;</div></div><div class="cbody"></div>`;const cb=ce.querySelector('.cbody');Object.entries(gs).forEach(([gn,items])=>{const gt=document.createElement('div');gt.className='gtitle';gt.textContent=gn+' · '+items.length+' itens';cb.appendChild(gt);const gr=document.createElement('div');gr.className='grid';items.forEach(i=>{const a=document.createElement('div');a.className='card '+i.material_type.toLowerCase();a.innerHTML=buildCardHtml(i);a.querySelector('.btn-read').onclick=e=>{e.stopPropagation();openReader(i)};a.querySelector('.btn-dl').onclick=e=>{e.stopPropagation();downloadPDF(i.url,i.display_name)};a.querySelector('.btn-fav').onclick=e=>{e.stopPropagation();toggleFav(i.url)};gr.appendChild(a)});cb.appendChild(gr)});ce.querySelector('.chdr').onclick=()=>ce.classList.toggle('open');frag.appendChild(ce)});app.innerHTML='';app.appendChild(frag);$('sT').textContent=D.reduce((s,c)=>s+visItems(c).length,0);$('sC').textContent=D.length;$('sV').textContent=vc;if(!vc){app.innerHTML=`<div class="empty"><div class="empty-icon">${cV==='fav'?'FAV':'BUSCA'}</div><h3>${cV==='fav'?'Nenhum favorito':'Nada encontrado'}</h3><p style="margin-top:.5rem;font-size:.85rem;color:var(--txt2)">${cV==='fav'?'Toque na estrela para favoritar':'Tente outra busca'}</p></div>`};if(_thumbObserver)try{_thumbObserver.disconnect()}catch(e){}if(window.requestIdleCallback)requestIdleCallback(()=>{try{initThumbs()}catch(e){}},{timeout:2000});else setTimeout(()=>{try{initThumbs()}catch(e){}},600)}
function toggleFav(u){if(favs.has(u)){favs.delete(u);toast('Removido dos favoritos')}else{favs.add(u);toast('Adicionado aos favoritos')}localStorage.setItem('sp_favs',JSON.stringify([...favs]));render()}
function toggleTheme(){const html=document.documentElement;const btn=$('themeBtn');const current=html.getAttribute('data-theme');const next=current==='dark'?'light':'dark';html.setAttribute('data-theme',next);localStorage.setItem('sp_theme',next);btn.innerHTML=next==='dark'?'☾':'☀';toast(next==='dark'?'Modo escuro':'Modo claro')}
$('themeBtn').onclick=toggleTheme;

// --- GATE: qualquer ID entra; Teacher só para IDs autorizados ---
const IDS_PROFESSOR=['TIA ISA E A MELHOR','1A2B3C'];
function normalizarId(s){return (s||'').trim().replace(/\\s+/g,' ').toUpperCase()}
function ehProfessor(){return !!userId&&IDS_PROFESSOR.includes(normalizarId(userId))}
function visItems(course){return ehProfessor()? course.items : course.items.filter(i=>i.material_type!=='Teacher')}
function atualizarPermissoes(){
  const fb=$('filterBar');if(!fb)return;
  const tb=fb.querySelector('[data-t="Teacher"]');
  if(tb)tb.style.display=ehProfessor()?'':'none';
  if(!ehProfessor()&&cF==='Teacher'){cF='all';$$('.fbtn').forEach(x=>x.classList.remove('active'));const all=fb.querySelector('[data-t="all"]');if(all)all.classList.add('active')}
}
function atualizarChipId(){const c=$('idChip');if(!c)return;if(userId){c.style.display='';c.textContent='ID: '+userId}else c.style.display='none'}
function enterWithId(v){const id=(v||'').trim();if(!id){toast('Digite um ID');return false}userId=id;localStorage.setItem('sp_userId',userId);const gate=$('idGate');if(gate)gate.classList.add('hidden');document.body.style.overflow='';toast(ehProfessor()?'Modo professor ativado':'Bem-vindo(a): '+userId);atualizarChipId();atualizarPermissoes();render();return true}
try{
  const gate=$('idGate');
  if(gate){
    if(userId){gate.classList.add('hidden');document.body.style.overflow=''}
    else{gate.classList.remove('hidden');document.body.style.overflow='hidden';setTimeout(()=>{try{$('gateInput').focus()}catch(e){}},250)}
  }
  if($('gateEnter'))$('gateEnter').onclick=()=>enterWithId($('gateInput').value);
  if($('gateInput'))$('gateInput').onkeydown=e=>{if(e.key==='Enter')enterWithId($('gateInput').value)};
  const chip=$('idChip');
  if(chip)chip.onclick=()=>{const g=$('idGate');if(!g)return;g.classList.remove('hidden');document.body.style.overflow='hidden';const inp=$('gateInput');if(inp){inp.value=userId||'';setTimeout(()=>{try{inp.focus();inp.select()}catch(e){}},200)}};
  atualizarChipId();
  atualizarPermissoes();
}catch(e){}

// --- BULK DOWNLOAD ---
let bulkSelected=new Set();let bulkFilter='';
function getBulkFiltered(){const q=bulkFilter.toLowerCase().trim();return q? D.filter(c=>c.name.toLowerCase().includes(q)) : D}
function updateBulkStats(){const c=$('selCount'),f=$('selFiles');if(!c||!f)return;c.textContent=bulkSelected.size;let total=0;bulkSelected.forEach(n=>{const course=D.find(x=>x.name===n);if(course)total+=visItems(course).length});f.textContent=total;const btn=$('bulkDownload');if(btn){btn.disabled=bulkSelected.size===0;btn.style.opacity=bulkSelected.size===0?'0.5':'1'}}
function renderBulkList(){const list=$('bulkList');if(!list)return;const filtered=getBulkFiltered();list.innerHTML='';if(!filtered.length){list.innerHTML='<div style="padding:1rem;text-align:center;color:var(--txt2);font-size:.82rem">Nenhum curso encontrado</div>';return}filtered.forEach(course=>{const isSel=bulkSelected.has(course.name);const row=document.createElement('label');row.className='course-sel-item'+(isSel?' selected':'');row.innerHTML=`<input type="checkbox" ${isSel?'checked':''}><div class="course-sel-info"><div class="course-sel-name">${course.name}</div><div class="course-sel-count">${visItems(course).length} livros</div></div>`;const cb=row.querySelector('input');const toggle=()=>{if(cb.checked)bulkSelected.add(course.name);else bulkSelected.delete(course.name);updateBulkStats()};cb.onchange=toggle;row.onclick=e=>{if(e.target!==cb){cb.checked=!cb.checked;toggle()}};list.appendChild(row)});updateBulkStats()}
try{
  const t=$('bulkToggle'),p=$('bulkPanel');
  if(t&&p){t.onclick=()=>{const isOpen=p.classList.contains('open');if(isOpen){p.classList.remove('open');t.classList.remove('open');t.textContent='☰'}else{p.classList.add('open');t.classList.add('open');t.textContent='✕';renderBulkList();setTimeout(()=>{try{$('bulkSearch').focus()}catch(e){}},150)}}}
  if($('bulkSearch'))$('bulkSearch').oninput=e=>{bulkFilter=e.target.value;renderBulkList()};
  if($('bulkSelAll'))$('bulkSelAll').onclick=()=>{getBulkFiltered().forEach(c=>bulkSelected.add(c.name));renderBulkList();toast('Visíveis selecionados')};
  if($('bulkClear'))$('bulkClear').onclick=()=>{bulkSelected.clear();renderBulkList();toast('Seleção limpa')};
  if($('bulkDownload'))$('bulkDownload').onclick=async()=>{
    if(!bulkSelected.size){toast('Selecione ao menos 1 curso');return}
    const files=[];bulkSelected.forEach(name=>{const co=D.find(x=>x.name===name);if(co)files.push(...visItems(co).map(it=>({url:it.url,name:co.name+' - '+it.display_name})))});
    if(!files.length){toast('Nenhum livro');return}
    if(files.length>80&&!confirm(`Você vai baixar ${files.length} livros. Continuar?`))return;
    const prog=$('bulkProgress'),bar=$('bulkBar'),lab=$('bulkLabel');if(prog)prog.style.display='block';if(lab){lab.style.display='block';lab.textContent='Iniciando...'};const btn=$('bulkDownload');btn.disabled=true;let ok=0,err=0;
    for(let i=0;i<files.length;i++){const f=files[i];if(lab)lab.textContent=`Baixando ${i+1}/${files.length}: ${f.name}`;if(bar)bar.style.width=((i/files.length)*100).toFixed(1)+'%';
      try{let r;try{r=await fetch(f.url);if(!r.ok)throw 0}catch(e1){r=await fetch('/pdf?key='+encodeURIComponent(f.url))}if(!r.ok)throw 0;const blob=await r.blob();const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=f.name+'.pdf';document.body.appendChild(a);a.click();setTimeout(()=>{a.remove();URL.revokeObjectURL(a.href)},900);ok++}catch(e){err++;try{window.open(f.url,'_blank')}catch(e2){}}
      if(i<files.length-1)await new Promise(res=>setTimeout(res,420))}
    if(bar)bar.style.width='100%';if(lab)lab.textContent=`Concluído: ${ok} OK, ${err} em nova aba`;toast(`Lote: ${ok} baixados`);btn.disabled=false;setTimeout(()=>{if(prog)prog.style.display='none';if(lab)lab.style.display='none';if(bar)bar.style.width='0%'},4000);
  };
}catch(e){}

// --- THUMBNAILS PDF.js (no celular fica desligado: cada thumb consome CPU/rede
// e deixava a rolagem pesada; la aparece o gradiente bonito do placeholder) ---
const isCoarse=(window.matchMedia&&matchMedia('(pointer:coarse)').matches)||innerWidth<768;
let thumbCache=new Map();let _thumbObserver=null;
try{if(typeof pdfjsLib!=='undefined')pdfjsLib.GlobalWorkerOptions.workerSrc='https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/build/pdf.worker.min.js'}catch(e){}
async function renderPdfThumb(url,canvas,wrap){if(!url||!canvas||thumbCache.get(url)==='done')return;if(thumbCache.get(url)==='loading')return;thumbCache.set(url,'loading');wrap.classList.add('loading');try{const task=pdfjsLib.getDocument({url:url,rangeChunkSize:65536,withCredentials:false});const pdf=await task.promise;const page=await pdf.getPage(1);const vp=page.getViewport({scale:0.5});const ctx=canvas.getContext('2d');canvas.width=vp.width;canvas.height=vp.height;await page.render({canvasContext:ctx,viewport:vp}).promise;wrap.classList.add('has-thumb');wrap.classList.remove('loading');thumbCache.set(url,'done');try{await pdf.destroy()}catch(e){}}catch(e){thumbCache.delete(url);wrap.classList.remove('loading')}}
function initThumbs(){if(isCoarse)return;const wraps=document.querySelectorAll('.thumb-wrap[data-pdf]');if(!wraps.length)return;if(!('IntersectionObserver' in window)){wraps.forEach(w=>{const c=w.querySelector('.thumb-canvas');const u=w.getAttribute('data-pdf');if(c&&u)renderPdfThumb(u,c,w)});return}if(_thumbObserver)try{_thumbObserver.disconnect()}catch(e){}_thumbObserver=new IntersectionObserver(entries=>{entries.forEach(en=>{if(en.isIntersecting){const w=en.target;const c=w.querySelector('.thumb-canvas');const u=w.getAttribute('data-pdf');if(c&&u)renderPdfThumb(u,c,w);_thumbObserver.unobserve(w)}})},{rootMargin:'200px',threshold:0.01});wraps.forEach(w=>_thumbObserver.observe(w))}

// --- BUSCA / FILTROS / NAV ---
const _renderPending={value:false};
function scheduleRender(){if(_renderPending.value)return;_renderPending.value=true;requestAnimationFrame(()=>{render();_renderPending.value=false})}
const _debouncedSearch=rafThrottle(e=>{cS=e.target.value;scheduleRender()});
$('searchBox').addEventListener('input',_debouncedSearch,{passive:true});
$('filterBar').addEventListener('click',e=>{const b=e.target.closest('.fbtn');if(!b)return;$$('.fbtn').forEach(x=>x.classList.remove('active'));b.classList.add('active');cF=b.dataset.t;scheduleRender()},{passive:true});
$$('.nitem').forEach(b=>b.addEventListener('click',function(){if(this.dataset.a==='top'){window.scrollTo({top:0,behavior:'smooth'});return}$$('.nitem').forEach(x=>x.classList.remove('active'));this.classList.add('active');cV=this.dataset.a;scheduleRender()},{passive:true}));
const savedTheme=localStorage.getItem('sp_theme')||'dark';document.documentElement.setAttribute('data-theme',savedTheme);$('themeBtn').innerHTML=savedTheme==='dark'?'☾':'☀';

// ================= HEARTBEAT / BLOQUEIO =================
let blocked=false;
async function heartbeat(){
  if(location.protocol!=='http:'&&location.protocol!=='https:')return;
  try{
    const r=await fetch('/__hb',{cache:'no-store'});
    if(r.status===403){setBlocked(true)}else{setBlocked(false);$('netBanner').classList.remove('show')}
  }catch(e){if(!blocked)$('netBanner').classList.add('show')}
}
function setBlocked(b){blocked=b;const bs=$('blockedScreen');if(b){bs.classList.add('show');closeReader()}else bs.classList.remove('show')}
setInterval(heartbeat,4000);heartbeat();

// ================= SHA-256 (subtle + fallback JS identico) =================
function sha256Js(bytes){
  const K=[0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
  0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
  0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
  0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
  0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
  0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
  0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
  0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2];
  const rotr=(x,n)=>(x>>>n)|(x<<(32-n));
  const l=bytes.length, bitLen=l*8;
  const blocks=Math.ceil((l+9)/64);
  const buf=new Uint8Array(blocks*64); buf.set(bytes); buf[l]=0x80;
  const dv=new DataView(buf.buffer);
  dv.setUint32(blocks*64-8, Math.floor(bitLen/4294967296));
  dv.setUint32(blocks*64-4, bitLen>>>0);
  let[h0,h1,h2,h3,h4,h5,h6,h7]=[0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19];
  const w=new Uint32Array(64);
  for(let b=0;b<blocks;b++){
    const o=b*64;
    for(let i=0;i<16;i++)w[i]=dv.getUint32(o+i*4);
    for(let i=16;i<64;i++){
      const x=w[i-15],y=w[i-2];
      const s0=rotr(x,7)^rotr(x,18)^(x>>>3);
      const s1=rotr(y,17)^rotr(y,19)^(y>>>10);
      w[i]=(w[i-16]+s0+w[i-7]+s1)>>>0;
    }
    let a=h0,bh=h1,c=h2,d=h3,e=h4,f=h5,g=h6,h=h7;
    for(let i=0;i<64;i++){
      const S1=rotr(e,6)^rotr(e,11)^rotr(e,25);
      const ch=(e&f)^(~e&g);
      const t1=(h+S1+ch+K[i]+w[i])>>>0;
      const S0=rotr(a,2)^rotr(a,13)^rotr(a,22);
      const mj=(a&bh)^(a&c)^(bh&c);
      const t2=(S0+mj)>>>0;
      h=g;g=f;f=e;e=(d+t1)>>>0;d=c;c=bh;bh=a;a=(t1+t2)>>>0;
    }
    h0=(h0+a)>>>0;h1=(h1+bh)>>>0;h2=(h2+c)>>>0;h3=(h3+d)>>>0;
    h4=(h4+e)>>>0;h5=(h5+f)>>>0;h6=(h6+g)>>>0;h7=(h7+h)>>>0;
  }
  return [h0,h1,h2,h3,h4,h5,h6,h7].map(x=>x.toString(16).padStart(8,'0')).join('');
}
async function sha256Hex(u8){
  try{
    if(window.crypto&&window.crypto.subtle&&window.isSecureContext!==false){
      const b=await crypto.subtle.digest('SHA-256',u8);
      return Array.from(new Uint8Array(b)).map(x=>x.toString(16).padStart(2,'0')).join('');
    }
  }catch(e){}
  try{return sha256Js(u8)}catch(e){return 'h'+hashString(u8.length+':'+Array.from(u8.subarray(0,4096)).join(',')).toString(16)}
}

// ================= READER Steamplay 2 =================
const CLOUD_BASE='https://us-central1-stemplay-v2.cloudfunctions.net/Annotations/';
const PALETTE=['#dd3736','#0a3d62','#27ae60','#fcb017','#6c5ce7'];
const RD={pdf:null,doc:null,url:'',name:'',docKey:'',page:1,total:0,zoom:1,fitBase:1,
  tool:null,color:PALETTE[0],size:5,strokes:{},notes:[],undoStack:[],
  drawing:false,curStroke:null,saveTimer:null,updatedAt:0,loading:false,
  renderSeq:0,curTask:null};

function rdSyncStatus(txt,ok){const el=$('rdSync');el.textContent=txt||'';el.classList.toggle('ok',!!ok)}
function setTool(t){
  RD.tool=(RD.tool===t)?null:t;
  $$('.rt[data-rt]').forEach(b=>b.classList.toggle('active',b.dataset.rt===RD.tool));
  $('rOverlay').style.pointerEvents=RD.tool?'auto':'none';
}
function selectColor(c){RD.color=c;$$('.rd-sw').forEach(s=>s.classList.toggle('sel',s.dataset.c===c));if(!RD.tool)setTool('draw')}
try{
  const colorsBox=$('rdColors');
  PALETTE.forEach(c=>{const b=document.createElement('button');b.className='rd-sw';b.dataset.c=c;b.style.background=c;b.title=c;
    b.onclick=()=>selectColor(c);colorsBox.appendChild(b)});
  $$('.rt[data-rt]').forEach(b=>b.onclick=()=>setTool(b.dataset.rt));
  $('rdSize').oninput=e=>{RD.size=Number(e.target.value)};
  selectColor(RD.color);
  RD.tool=null;$$('.rt[data-rt]').forEach(b=>b.classList.remove('active'));
  $('rdClose').onclick=closeReader;
  $('rdPrev').onclick=()=>goPage(RD.page-1);
  $('rdNext').onclick=()=>goPage(RD.page+1);
  $('rdPageNum').onchange=e=>goPage(Number(e.target.value)||1);
  $('rdZoomIn').onclick=()=>{RD.zoom=Math.min(4,Math.round(RD.zoom*120)/100);setZoomLabel();scheduleRenderPage()};
  $('rdZoomOut').onclick=()=>{RD.zoom=Math.max(0.3,Math.round((RD.zoom/1.2)*100)/100);setZoomLabel();scheduleRenderPage()};
  $('rdFit').onclick=()=>{RD.zoom=1;setZoomLabel();scheduleRenderPage()};
  $('rdUndo').onclick=undoStroke;
  $('rdClear').onclick=()=>{if(!confirm('Limpar todos os desenhos desta página?'))return;RD.strokes[RD.page]=[];markDirty();redrawStrokes()};
  initNoteButtonDrag();
}catch(e){console.error('reader init',e)}

// --- helpers de performance ---
function curDpr(){return RD.dprEff||Math.min(2,window.devicePixelRatio||1)}
function setZoomLabel(){const el=$('rdZoom');if(el)el.textContent=Math.round(RD.zoom*100)+'%'}
let _zoomTimer=null;
function scheduleRenderPage(){if(_zoomTimer)clearTimeout(_zoomTimer);_zoomTimer=setTimeout(()=>{_zoomTimer=null;renderPage()},90)}
const _pdfMem=new Map();
async function fetchPdfBytes(url,onProg){
  if(_pdfMem.has(url)){if(onProg)onProg(1);return _pdfMem.get(url)}
  const baixar=async(u)=>{
    const r=await fetch(u,{cache:'no-store'});
    if(!r.ok)throw new Error('http '+r.status);
    const total=Number(r.headers.get('Content-Length'))||0;
    if(!total||!r.body||!r.body.getReader){const b=await r.arrayBuffer();if(onProg)onProg(1);return b}
    const reader=r.body.getReader();const partes=[];let got=0;
    for(;;){const{done,value}=await reader.read();if(done)break;partes.push(value);got+=value.length;if(onProg)onProg(got/total)}
    const out=new Uint8Array(got);let off=0;for(const p of partes){out.set(p,off);off+=p.length}
    return out.buffer;
  };
  let buf;
  try{buf=await baixar(url)}catch(e){buf=await baixar('/pdf?key='+encodeURIComponent(url))}
  if(_pdfMem.size>=4){const k=_pdfMem.keys().next().value;_pdfMem.delete(k)}
  _pdfMem.set(url,buf);
  return buf;
}
async function openReader(item){
  if(RD.loading)return;RD.loading=true;
  const R=$('reader');R.classList.add('open');document.body.style.overflow='hidden';
  $('rdTitle').textContent=item.course+' — '+item.display_name;
  $('rdLoading').style.display='flex';
  $('rdLoading').innerHTML='<div class="spinner"></div>Preparando PDF...';
  rdSyncStatus('');
  try{
    if(!window.pdfjsLib)throw new Error('sem internet para o motor de PDF (pdf.js)');
    const emCache=_pdfMem.has(item.url);
    const buf=await fetchPdfBytes(item.url,(frac)=>{
      $('rdLoading').innerHTML='<div class="spinner"></div>'+(emCache?'Abrindo (cache)...':('Baixando PDF... '+Math.round(frac*100)+'%'));
    });
    const u8=new Uint8Array(buf.slice(0));
    // hash ANTES do pdf.js transferir/detachar o buffer
    RD.docKey=await sha256Hex(u8);
    RD.pdf=await pdfjsLib.getDocument({data:u8}).promise;
    RD.total=RD.pdf.numPages;RD.page=1;RD.zoom=1;RD.url=item.url;RD.name=item.display_name;
    RD.strokes={};RD.notes=[];RD.undoStack=[];RD.renderSeq++;
    await carregarSincronizacao();
    await renderPage();
    atualizarContadorNotas();
  }catch(e){
    $('rdLoading').innerHTML='<div style="color:#ff6b6b">Erro: '+(e.message||e)+'<br><span style="font-size:.7rem;color:#8888aa">Toque em Ajustar para tentar de novo</span></div>';
    toast('Erro ao abrir o PDF');
  }
  RD.loading=false;
}
function closeReader(){
  $('reader').classList.remove('open');document.body.style.overflow='';
  if(RD.saveTimer){clearTimeout(RD.saveTimer);RD.saveTimer=null;flushSave()}
  try{if(RD.pdf)RD.pdf.destroy()}catch(e){}
  RD.pdf=null;RD.doc=null;RD.curTask=null;
}
async function renderPage(){
  if(!RD.pdf)return;
  const my=++RD.renderSeq;
  if(RD.curTask){try{RD.curTask.cancel()}catch(e){}RD.curTask=null}
  try{RD.doc=await RD.pdf.getPage(RD.page)}catch(e){return}
  if(my!==RD.renderSeq)return;
  const stage=$('rStage');
  const availW=Math.max(200,stage.clientWidth-28);
  RD._lastStageW=stage.clientWidth;
  const vp0=RD.doc.getViewport({scale:1});
  RD.fitBase=Math.min(2.2,Math.max(.2,availW/vp0.width));
  const s=RD.fitBase*RD.zoom;
  const vp=RD.doc.getViewport({scale:s});
  const cv=$('rPage'),ov=$('rOverlay'),wrap=$('rWrap');
  const W=Math.round(vp.width),H=Math.round(vp.height);
  // budget de ~3.2MP: sem isso, zoom alto + tela retina gera canvas de 8-12MP e o render leva segundos
  let dpr=Math.min(2,window.devicePixelRatio||1);
  const px=W*H*dpr*dpr;
  if(px>3200000)dpr=Math.max(0.5,dpr*Math.sqrt(3200000/px));
  RD.dprEff=dpr;
  wrap.style.transform='';
  wrap.style.width=W+'px';wrap.style.height=H+'px';
  cv.width=Math.round(W*dpr);cv.height=Math.round(H*dpr);
  cv.style.width=W+'px';cv.style.height=H+'px';
  ov.width=cv.width;ov.height=cv.height;
  ov.style.width=W+'px';ov.style.height=H+'px';
  const lv=$('rLive');
  lv.width=cv.width;lv.height=cv.height;
  lv.style.width=W+'px';lv.style.height=H+'px';
  lv.style.display='none';
  const ctx=cv.getContext('2d');
  const task=RD.doc.render({canvasContext:ctx,viewport:vp,transform:[dpr,0,0,dpr,0,0]});
  RD.curTask=task;
  try{await task.promise;RD.curTask=null}catch(e){RD.curTask=null;if(e&&(e.name==='RenderingCancelledException'||my!==RD.renderSeq))return}
  if(my!==RD.renderSeq)return;
  $('rdLoading').style.display='none';
  $('rdPageNum').value=RD.page;$('rdPageNum').max=RD.total;
  $('rdTot').textContent='/ '+RD.total;
  setZoomLabel();
  RD.renderedZoom=RD.zoom;
  redrawStrokes();
  const notaFoco=document.activeElement&&document.activeElement.classList&&document.activeElement.classList.contains('nb-body');
  if(notaFoco&&RD._renderedPage===RD.page)RD.pendingNotes=true;
  else{RD.pendingNotes=false;renderNotes()}
  RD._renderedPage=RD.page;
}
async function goPage(n){
  if(!RD.pdf)return;
  n=Math.min(Math.max(1,n|0),RD.total);
  if(n===RD.page)return;
  RD.page=n;
  $('rdLoading').style.display='flex';
  $('rdLoading').innerHTML='<div class="spinner"></div>Página '+n+'...';
  await renderPage();
  atualizarContadorNotas();
}
// --- desenho ---
function strokeRadiusPx(st,w){return Math.max(1,(st.w/1000)*w*(st.t==='hl'?3:1))}
function drawStroke(ctx,st,cssW,cssH){
  if(!st.pts||!st.pts.length)return;
  ctx.save();
  ctx.lineCap='round';ctx.lineJoin='round';
  const r=strokeRadiusPx(st,cssW);
  if(st.t==='erase'){ctx.globalCompositeOperation='destination-out';ctx.strokeStyle='rgba(0,0,0,1)';ctx.lineWidth=r*2}
  else if(st.t==='hl'){ctx.globalAlpha=.35;ctx.strokeStyle=st.c;ctx.lineWidth=r*2}
  else{ctx.strokeStyle=st.c;ctx.lineWidth=r*2}
  ctx.beginPath();
  ctx.moveTo(st.pts[0][0]*cssW,st.pts[0][1]*cssH);
  if(st.pts.length===1)ctx.lineTo(st.pts[0][0]*cssW+0.01,st.pts[0][1]*cssH);
  for(let i=1;i<st.pts.length;i++)ctx.lineTo(st.pts[i][0]*cssW,st.pts[i][1]*cssH);
  ctx.stroke();ctx.restore();
}
function redrawStrokes(){
  clearLive();
  const ov=$('rOverlay');const ctx=ov.getContext('2d');
  const dpr=curDpr();
  ctx.setTransform(1,0,0,1,0,0);ctx.clearRect(0,0,ov.width,ov.height);
  ctx.setTransform(dpr,0,0,dpr,0,0);
  (RD.strokes[RD.page]||[]).forEach(st=>drawStroke(ctx,st,ov.width/dpr,ov.height/dpr));
}
function drawLastSegment(){
  const st=RD.curStroke;if(!st||st.pts.length<2)return;
  const el=$('rOverlay');const dpr=curDpr();const ctx=el.getContext('2d');
  const cssW=el.width/dpr,cssH=el.height/dpr;
  ctx.save();ctx.lineCap='round';ctx.lineJoin='round';
  const r=strokeRadiusPx(st,cssW);
  if(st.t==='erase'){ctx.globalCompositeOperation='destination-out';ctx.strokeStyle='rgba(0,0,0,1)';ctx.lineWidth=r*2}
  else if(st.t==='hl'){ctx.globalAlpha=.35;ctx.strokeStyle=st.c;ctx.lineWidth=r*2}
  else{ctx.strokeStyle=st.c;ctx.lineWidth=r*2}
  const a=st.pts[st.pts.length-2],b=st.pts[st.pts.length-1];
  ctx.beginPath();ctx.moveTo(a[0]*cssW,a[1]*cssH);ctx.lineTo(b[0]*cssW,b[1]*cssH);
  ctx.stroke();ctx.restore();
}
// --- camada viva: o traco atual do marca-texto (alpha uniforme, sem emendas) ---
function clearLive(){
  const lv=$('rLive');if(!lv)return;
  lv.style.display='none';
  const ctx=lv.getContext('2d');
  ctx.setTransform(1,0,0,1,0,0);ctx.clearRect(0,0,lv.width,lv.height);
}
function drawLiveStroke(){
  const st=RD.curStroke;if(!st)return;
  const lv=$('rLive');const dpr=curDpr();const ctx=lv.getContext('2d');
  ctx.setTransform(1,0,0,1,0,0);ctx.clearRect(0,0,lv.width,lv.height);
  ctx.setTransform(dpr,0,0,dpr,0,0);
  lv.style.display='block';
  // caminho UNICO por frame: cor opaca na camada; a translucidez vem do CSS
  // (opacity no elemento) -> nunca soma alpha nas sobreposicoes = faixa uniforme
  ctx.save();
  ctx.lineCap='round';ctx.lineJoin='round';
  ctx.strokeStyle=st.c;ctx.lineWidth=strokeRadiusPx(st,lv.width/dpr)*2;
  ctx.beginPath();
  ctx.moveTo(st.pts[0][0]*(lv.width/dpr),st.pts[0][1]*(lv.height/dpr));
  if(st.pts.length===1)ctx.lineTo(st.pts[0][0]*(lv.width/dpr)+0.01,st.pts[0][1]*(lv.height/dpr));
  for(let i=1;i<st.pts.length;i++)ctx.lineTo(st.pts[i][0]*(lv.width/dpr),st.pts[i][1]*(lv.height/dpr));
  ctx.stroke();ctx.restore();
}
function evPos(ev,el){const r=el.getBoundingClientRect();return[Math.min(Math.max((ev.clientX-r.left)/r.width,0),1),Math.min(Math.max((ev.clientY-r.top)/r.height,0),1)]}
const ov=$('rOverlay');
ov.style.pointerEvents='none';
ov.addEventListener('pointerdown',ev=>{
  if(!RD.tool||ev.button!==0)return;
  ev.preventDefault();
  RD.drawing=true;
  const p=evPos(ev,ov);
  const st={t:RD.tool,c:RD.color,w:RD.size*(RD.tool==='erase'?2.2:1),pts:[p]};
  if(!RD.strokes[RD.page])RD.strokes[RD.page]=[];
  RD.strokes[RD.page].push(st);
  RD.undoStack.push({page:RD.page,idx:RD.strokes[RD.page].length-1});
  RD.curStroke=st;
  try{ov.setPointerCapture(ev.pointerId)}catch(e){}
  if(st.t==='hl'){drawLiveStroke()}
  else{const dpr=curDpr();const ctx=ov.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);drawStroke(ctx,st,ov.width/dpr,ov.height/dpr)}
},{passive:false});
ov.addEventListener('pointermove',ev=>{
  if(!RD.drawing||!RD.curStroke)return;
  ev.preventDefault();
  const p=evPos(ev,ov);
  const pts=RD.curStroke.pts;const last=pts[pts.length-1];
  if(Math.hypot(p[0]-last[0],p[1]-last[1])<0.0012)return;
  pts.push(p);
  if(RD.curStroke.t==='hl')drawLiveStroke();
  else drawLastSegment();
},{passive:false});
function endStroke(ev){
  if(!RD.drawing)return;
  const st=RD.curStroke;
  RD.drawing=false;RD.curStroke=null;
  try{ov.releasePointerCapture(ev.pointerId)}catch(e){}
  if(st&&st.t==='hl'){
    clearLive();
    const dpr=curDpr();const ctx=ov.getContext('2d');
    ctx.setTransform(dpr,0,0,dpr,0,0);
    drawStroke(ctx,st,ov.width/dpr,ov.height/dpr);
  }
  markDirty();
}
ov.addEventListener('pointerup',endStroke);
ov.addEventListener('pointercancel',()=>{RD.drawing=false;RD.curStroke=null;clearLive();markDirty()});
function undoStroke(){
  const u=RD.undoStack.pop();if(!u)return;
  const arr=RD.strokes[u.page];if(!arr||arr[u.idx]===undefined)return;
  arr.splice(u.idx,1);
  RD.undoStack.forEach(x=>{if(x.page===u.page&&x.idx>u.idx)x.idx--});
  markDirty();redrawStrokes();
}
// --- notas: blocos arrastaveis na pagina ---
function notaAtual(){return RD.notes.filter(n=>n.p===RD.page)}
function atualizarContadorNotas(){const b=$('rdNoteCount');if(b)b.textContent=notaAtual().length}
function renderNotes(){
  const wrap=$('rWrap');
  $$('.note-block',wrap).forEach(el=>el.remove());
  notaAtual().forEach(n=>wrap.appendChild(criarNotaEl(n)));
  atualizarContadorNotas();
}
function criarNotaEl(n){
  const el=document.createElement('div');
  el.className='note-block'+(n.min?' min':'');
  el.dataset.id=n.id;
  el.style.left=(n.x*100)+'%';el.style.top=(n.y*100)+'%';
  el.style.width=(n.w*100)+'%';el.style.height=(n.h*100)+'%';
  el.innerHTML=`<div class="nb-head"><span class="nb-label">🗒 nota</span><button class="nb-btn nb-min" title="Recolher/expandir">${n.min?'▢':'—'}</button><button class="nb-btn nb-del" title="Excluir">✕</button></div><textarea class="nb-body" placeholder="Escreva aqui..."></textarea><div class="nb-resize"></div>`;
  const ta=el.querySelector('.nb-body');
  ta.value=n.text||'';
  ta.addEventListener('input',()=>{n.text=ta.value;n.ts=Date.now();markDirty()});
  ta.addEventListener('pointerdown',e=>e.stopPropagation());
  el.querySelector('.nb-del').onclick=e=>{e.stopPropagation();RD.notes=RD.notes.filter(x=>x.id!==n.id);el.remove();markDirty();atualizarContadorNotas()};
  el.querySelector('.nb-min').onclick=e=>{e.stopPropagation();n.min=!n.min;el.classList.toggle('min',n.min);e.target.textContent=n.min?'▢':'—';markDirty()};
  // arrastar pelo cabecalho
  const head=el.querySelector('.nb-head');
  head.addEventListener('pointerdown',ev=>{
    if(ev.target.classList.contains('nb-btn'))return;
    ev.preventDefault();ev.stopPropagation();
    const wrapRect=$('rWrap').getBoundingClientRect();
    const startX=ev.clientX,startY=ev.clientY,origX=n.x,origY=n.y;
    const move=me=>{
      n.x=Math.min(Math.max(origX+(me.clientX-startX)/wrapRect.width,0),1-n.w);
      n.y=Math.min(Math.max(origY+(me.clientY-startY)/wrapRect.height,0),1-.04);
      el.style.left=(n.x*100)+'%';el.style.top=(n.y*100)+'%';
    };
    const up=()=>{document.removeEventListener('pointermove',move);document.removeEventListener('pointerup',up);markDirty()};
    document.addEventListener('pointermove',move,{passive:true});
    document.addEventListener('pointerup',up);
  });
  // redimensionar
  const rz=el.querySelector('.nb-resize');
  rz.addEventListener('pointerdown',ev=>{
    ev.preventDefault();ev.stopPropagation();
    const wrapRect=$('rWrap').getBoundingClientRect();
    const startX=ev.clientX,startY=ev.clientY,origW=n.w,origH=n.h;
    const move=me=>{
      n.w=Math.min(Math.max(origW+(me.clientX-startX)/wrapRect.width,.08),1-n.x);
      n.h=Math.min(Math.max(origH+(me.clientY-startY)/wrapRect.height,.05),1-n.y);
      el.style.width=(n.w*100)+'%';el.style.height=(n.h*100)+'%';
    };
    const up=()=>{document.removeEventListener('pointermove',move);document.removeEventListener('pointerup',up);markDirty()};
    document.addEventListener('pointermove',move,{passive:true});
    document.addEventListener('pointerup',up);
  });
  return el;
}
function criarNota(x,y){
  const n={id:'n'+Date.now()+Math.random().toString(36).slice(2,6),p:RD.page,
    x:Math.min(Math.max(x,0),0.7),y:Math.min(Math.max(y,0),0.8),w:0.24,h:0.16,text:'',min:false,ts:Date.now()};
  RD.notes.push(n);
  renderNotes();markDirty();
  const el=$('rWrap').querySelector(`.note-block[data-id="${n.id}"] .nb-body`);
  if(el)setTimeout(()=>el.focus(),60);
}
function initNoteButtonDrag(){
  const btn=$('rdNoteBtn');
  let ghost=null,moved=false,startPt=null;
  btn.addEventListener('pointerdown',ev=>{
    if(!RD.pdf)return;
    ev.preventDefault();
    startPt={x:ev.clientX,y:ev.clientY};moved=false;
    ghost=document.createElement('div');ghost.className='note-ghost';ghost.textContent='✎';
    ghost.style.left=ev.clientX+'px';ghost.style.top=ev.clientY+'px';ghost.style.display='none';
    document.body.appendChild(ghost);
    const move=me=>{
      if(Math.hypot(me.clientX-startPt.x,me.clientY-startPt.y)>8){moved=true;ghost.style.display='block'}
      if(moved){ghost.style.left=me.clientX+'px';ghost.style.top=me.clientY+'px'}
    };
    const up=me=>{
      document.removeEventListener('pointermove',move);document.removeEventListener('pointerup',up);document.removeEventListener('pointercancel',cancel);
      if(ghost){ghost.remove();ghost=null}
      const stage=$('rStage').getBoundingClientRect();
      if(moved&&me.clientX>=stage.left&&me.clientX<=stage.right&&me.clientY>=stage.top&&me.clientY<=stage.bottom){
        const wrapRect=$('rWrap').getBoundingClientRect();
        criarNota((me.clientX-wrapRect.left)/wrapRect.width,(me.clientY-wrapRect.top)/wrapRect.height);
      }else if(!moved){
        criarNota(0.08,0.08);
      }
    };
    const cancel=()=>{
      document.removeEventListener('pointermove',move);document.removeEventListener('pointerup',up);document.removeEventListener('pointercancel',cancel);
      if(ghost){ghost.remove();ghost=null}
    };
    document.addEventListener('pointermove',move,{passive:true});
    document.addEventListener('pointerup',up);
    document.addEventListener('pointercancel',cancel);
  });
}
// --- sincronizacao local + nuvem (corrigida) ---
function localKey(){return 'sp2_doc_'+(userId||'anon')+'_'+RD.docKey}
function cloudUrl(){return CLOUD_BASE+encodeURIComponent(userId||'anon')+'/'+RD.docKey}
function payloadAtual(){return JSON.stringify({docId:RD.url,drawings:RD.strokes,notes:RD.notes,ts:RD.updatedAt})}
function markDirty(){
  RD.updatedAt=Date.now();
  if(RD.saveTimer)clearTimeout(RD.saveTimer);
  RD.saveTimer=setTimeout(()=>{RD.saveTimer=null;flushSave()},700);
}
function flushSave(){
  if(!RD.docKey)return;
  const p=payloadAtual();
  try{localStorage.setItem(localKey(),p)}catch(e){toast('Sem espaço local para salvar')}
  if(userId){
    fetch(cloudUrl(),{method:'PUT',headers:{'Content-Type':'application/json'},body:p})
      .then(r=>rdSyncStatus(r.ok?'☁ sincronizado':'☁ falhou ao enviar',r.ok))
      .catch(()=>rdSyncStatus('☁ sem conexão'))
  }else rdSyncStatus('salvo local')
}
async function carregarSincronizacao(){
  let local=null,localTs=0;
  try{const raw=localStorage.getItem(localKey());if(raw){local=JSON.parse(raw);localTs=local.ts||0}}catch(e){}
  let remoto=null,remotoTs=0;
  if(userId){
    try{
      const r=await fetch(cloudUrl(),{headers:{Accept:'application/json'}});
      if(r.ok){remoto=await r.json().catch(()=>null);if(remoto)remotoTs=remoto.ts||0}
    }catch(e){}
  }
  const alvo=(remoto&&remotoTs>=localTs)?remoto:local;
  RD.strokes=(alvo&&alvo.drawings)||{};
  RD.notes=(alvo&&alvo.notes)||[];
  RD.undoStack=[];
  RD.updatedAt=Math.max(localTs,remotoTs)||Date.now();
  if(remoto&&remotoTs<localTs){flushSave()}          // servidor atrasado -> atualiza
  else if(!remoto&&local&&localTs){flushSave()}      // primeira vez na nuvem -> sobe
  else rdSyncStatus(userId?(remoto?'☁ da nuvem':'pronto'):'salvo local',!!remoto);
}

window.addEventListener('resize',rafThrottle(()=>{
  if(!RD.pdf||!$('reader').classList.contains('open'))return;
  const w=$('rStage').clientWidth;
  // re-renderir so quando a LARGURA muda (>24px): mudar altura ao rolar no celular
  // nao deve re-renderizar a pagina inteira (era causa de travadinhas ao rolar)
  if(RD._lastStageW&&Math.abs(w-RD._lastStageW)<=24)return;
  renderPage();
}));
document.addEventListener('focusout',e=>{
  if(RD.pendingNotes&&e.target&&e.target.classList&&e.target.classList.contains('nb-body'))
    setTimeout(()=>{if(RD.pendingNotes){RD.pendingNotes=false;renderNotes()}},80);
},true);

// --- PINCH-TO-ZOOM + toque duplo (celular) ---
// durante o gesto a pagina e escalada via transform (GPU, imediato);
// quando o dedo para, o canvas e re-renderizado na resolucao real
const _stage=$('rStage');
let _pinch=null,_lastTap=0;
function previewZoom(){
  const wrap=$('rWrap');
  const f=RD.zoom/(RD.renderedZoom||RD.zoom);
  wrap.style.transformOrigin='top left';
  wrap.style.transform=(Math.abs(f-1)<0.001)?'':'scale('+f.toFixed(3)+')';
}
_stage.addEventListener('touchstart',e=>{
  if(e.touches.length===2){
    const a=e.touches[0],b=e.touches[1];
    _pinch={d0:Math.max(1,Math.hypot(a.clientX-b.clientX,a.clientY-b.clientY)),z0:RD.zoom};
  }else _pinch=null;
},{passive:true});
_stage.addEventListener('touchmove',e=>{
  if(e.touches.length!==2||!_pinch)return;
  e.preventDefault();
  const a=e.touches[0],b=e.touches[1];
  const d=Math.max(1,Math.hypot(a.clientX-b.clientX,a.clientY-b.clientY));
  RD.zoom=Math.min(4,Math.max(.3,Math.round(_pinch.z0*(d/_pinch.d0)*100)/100));
  setZoomLabel();previewZoom();scheduleRenderPage();
},{passive:false});
function _pinchEnd(e){if(e.touches.length<2)_pinch=null}
_stage.addEventListener('touchend',_pinchEnd,{passive:true});
_stage.addEventListener('touchcancel',_pinchEnd,{passive:true});
_stage.addEventListener('touchend',e=>{
  if(_pinch||e.touches.length>0||(e.changedTouches||[]).length!==1)return;
  if(RD.tool||!RD.pdf)return; // nao confunde desenhar com toque duplo
  if(e.target&&e.target.closest&&e.target.closest('.note-block'))return; // nao dar zoom ao mexer na nota
  const now=Date.now();
  if(now-_lastTap<320){
    _lastTap=0;
    RD.zoom=(RD.renderedZoom&&RD.renderedZoom>1.05)?1:2;
    setZoomLabel();previewZoom();scheduleRenderPage();
  }else _lastTap=now;
},{passive:true});
document.addEventListener('keydown',e=>{
  if(!$('reader').classList.contains('open'))return;
  const inCampo=e.target&&(e.target.tagName==='TEXTAREA'||e.target.tagName==='INPUT');
  if(e.key==='Escape')closeReader();
  else if(!inCampo&&e.key==='ArrowRight')goPage(RD.page+1);
  else if(!inCampo&&e.key==='ArrowLeft')goPage(RD.page-1);
  else if((e.ctrlKey||e.metaKey)&&e.key==='z'&&!inCampo){e.preventDefault();undoStroke()}
});

console.log('StemPlay Library v13.1 (Steamplay 2 reader) |',D.reduce((s,c)=>s+c.items.length,0),'materiais em',D.length,'cursos');
render();
</script>
</body>
</html>"""

    html = html_template.replace("{courses_json}", courses_json)
    with open(output_html, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"  [OK] Biblioteca gerada: {output_html}")
    print(f"  [INFO] {len(courses)} cursos | {len(pdfs)} materiais (sem duplicatas)")


if __name__ == "__main__":
    main()
