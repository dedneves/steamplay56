#!/usr/bin/env python3
"""
StemPlay Library - launcher PC (CLI)
Servidor local com reader interno Steamplay 2, monitor de visitantes e BANimento.
Comandos durante a execucao: ls | ban <ip> | unban <ip> | bans | ajuda | sair
"""
import os, sys, time, socket, subprocess, threading, json, re, shutil
from datetime import datetime, timedelta
import http.server, socketserver
from urllib.parse import urlparse, parse_qs, unquote
from urllib.request import urlopen, Request
from urllib.error import URLError

if sys.platform == 'win32':
    os.system('')
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

import logging
logging.getLogger('urllib3').setLevel(logging.ERROR)

PORTA_LOCAL_PREF = 8000
PORTA_REDE_PREF = 8080
DIRETORIO = os.path.dirname(os.path.abspath(__file__))
HTML = "stemplay_library.html"
PDFS = "pdfs_found.txt"
REPO_API = "https://api.github.com/repos/dedneves/Stemplay/commits?per_page=1"
SHA_FILE = os.path.join(DIRETORIO, ".last_commit")
TEMPO_ATIVO = 60
ALLOWED_PROXY_PREFIX = "https://stemplay-videos.s3.us-east-2.amazonaws.com/"

CORES = ["\033[91m", "\033[92m", "\033[93m", "\033[94m",
         "\033[95m", "\033[96m", "\033[97m"]
VERDE = "\033[92m"
CIANO = "\033[96m"
AMARELO = "\033[93m"
VERMELHO = "\033[91m"
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

LETRAS = {
    'D': ["██████╗ ", "██╔══██╗", "██║  ██║", "██║  ██║", "██████╔╝", "╚═════╝ "],
    'E': ["███████╗", "██╔════╝", "█████╗  ", "██╔══╝  ", "███████╗", "╚══════╝"],
    'N': ["███╗   ██╗", "████╗  ██║", "██╔██╗ ██║", "██║╚██╗██║", "██║ ╚████║", "╚═╝  ╚═══╝"],
    'V': ["██╗   ██╗", "██║   ██║", "██║   ██║", "╚██╗ ██╔╝", " ╚████╔╝ ", "  ╚═══╝  "],
    'S': ["███████╗", "██╔════╝", "███████╗", "╚════██║", "███████║", "╚══════╝"],
    ' ': ["   ", "   ", "   ", "   ", "   ", "   "],
}


class RastreadorVisitantes:
    def __init__(self):
        self.visitantes = {}
        self.bloqueados = set()
        self.lock = threading.Lock()
        self.total_visitas = 0

    def registrar(self, ip, pagina):
        if pagina in ('/favicon.ico', '/robots.txt'):
            return
        with self.lock:
            if ip in self.bloqueados:
                return
            agora = datetime.now()
            if ip not in self.visitantes:
                self.total_visitas += 1
            antigo = self.visitantes.get(ip, {})
            self.visitantes[ip] = {
                'ultimo': agora,
                'requests': antigo.get('requests', 0) + 1,
                'pagina': pagina,
                'primeiro': antigo.get('primeiro', agora)
            }

    def ativos(self):
        with self.lock:
            agora = datetime.now()
            limite = timedelta(seconds=TEMPO_ATIVO)
            return {
                ip: dados for ip, dados in self.visitantes.items()
                if agora - dados['ultimo'] < limite
            }

    def banir(self, ip):
        with self.lock:
            self.bloqueados.add(ip)
            self.visitantes.pop(ip, None)
        CONEXOES.fechar_ip(ip)

    def desbanir(self, ip):
        with self.lock:
            self.bloqueados.discard(ip)

    def esta_bloqueado(self, ip):
        with self.lock:
            return ip in self.bloqueados


class RegistroConexoes:
    """Registra sockets ativos por IP para derrubar na hora ao banir."""
    def __init__(self):
        self._map = {}
        self._lock = threading.Lock()

    def adicionar(self, ip, sock):
        with self._lock:
            self._map.setdefault(ip, set()).add(sock)

    def remover(self, ip, sock):
        with self._lock:
            self._map.get(ip, set()).discard(sock)

    def fechar_ip(self, ip):
        with self._lock:
            socks = list(self._map.get(ip, set()))
        for s in socks:
            # shutdown() primeiro: no Windows, close() sozinho nao acorda
            # um recv() bloqueado em outra thread
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            except Exception:
                pass
            try:
                s.close()
            except Exception:
                pass


rastreador = RastreadorVisitantes()
CONEXOES = RegistroConexoes()


def ascii_art(texto):
    linhas = [""] * 6
    for ch in texto.upper():
        for i in range(6):
            linhas[i] += LETRAS.get(ch, LETRAS[' '])[i]
    return linhas


def limpar():
    os.system('cls' if os.name == 'nt' else 'clear')


def tamanho_visivel(texto):
    return len(re.sub(r'\033\[[0-9;]*m', '', texto))


def banner_piscante():
    import random
    art = ascii_art("DEDNEVES")
    duracao = 2.0
    intervalo = 0.08
    frames = int(duracao / intervalo)

    limpar()
    sys.stdout.write("\n")
    for i in range(frames):
        cor = random.choice(CORES)
        sys.stdout.write("\033[6A")
        for linha in art:
            sys.stdout.write("    " + cor + BOLD + linha + RESET + "\n")
        sys.stdout.flush()
        time.sleep(intervalo)

    sys.stdout.write("\033[6A")
    for linha in art:
        sys.stdout.write("    " + VERDE + BOLD + linha + RESET + "\n")

    sys.stdout.write("\n")
    sys.stdout.write("    StemPlay Library  ·  Reader Steamplay 2\n")
    sys.stdout.write("    " + "─" * 44 + "\n")
    sys.stdout.write("\n")
    sys.stdout.flush()


def banner_estatico():
    art = ascii_art("DEDNEVES")
    for linha in art:
        sys.stdout.write("    " + VERDE + BOLD + linha + RESET + "\n")
    sys.stdout.write("\n")
    sys.stdout.write("    StemPlay Library  ·  Reader Steamplay 2\n")
    sys.stdout.write("    " + "─" * 44 + "\n")
    sys.stdout.write("\n")
    sys.stdout.flush()


def checar_updates():
    sys.stdout.write("    [CHECK] Verificando atualizacoes do repositorio...\n")
    sys.stdout.flush()

    sha_local = None
    if os.path.exists(SHA_FILE):
        try:
            with open(SHA_FILE, "r") as f:
                sha_local = f.read().strip()
        except Exception:
            pass

    try:
        req = Request(REPO_API, headers={"User-Agent": "StemPlay-Launcher"})
        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            if not data:
                sys.stdout.write("    [INFO] Repositorio vazio ou sem commits\n")
                sys.stdout.flush()
                return
            sha_remoto = data[0]["sha"]
            mensagem = data[0]["commit"]["message"].split("\n")[0][:60]
            data_commit = data[0]["commit"]["author"]["date"][:10]
    except (URLError, json.JSONDecodeError, KeyError, OSError):
        sys.stdout.write("    [INFO] Sem internet ou repo indisponivel - modo offline\n")
        sys.stdout.flush()
        return

    try:
        with open(SHA_FILE, "w") as f:
            f.write(sha_remoto)
    except Exception:
        pass

    if sha_local is None:
        sys.stdout.write(f"    [INFO] Primeira checagem. Commit: {sha_remoto[:8]} ({data_commit})\n")
        sys.stdout.write(f"    [INFO] \"{mensagem}\"\n")
    elif sha_local != sha_remoto:
        sys.stdout.write(f"    [UPDATE] Nova versao disponivel!\n")
        sys.stdout.write(f"    [UPDATE] Commit: {sha_remoto[:8]} ({data_commit})\n")
        sys.stdout.write(f"    [UPDATE] \"{mensagem}\"\n")
        sys.stdout.write("\n")
        sys.stdout.write("    Deseja baixar a nova versao? (s/N): ")
        sys.stdout.flush()
        try:
            resp = input().strip().lower()
        except EOFError:
            resp = 'n'

        if resp in ('s', 'sim', 'y', 'yes'):
            baixar_atualizacao()
    else:
        sys.stdout.write(f"    [ OK ] Versao atualizada (commit {sha_remoto[:8]})\n")
    sys.stdout.flush()


def baixar_atualizacao():
    sys.stdout.write("\n")
    sys.stdout.write("    [DL] Baixando arquivos atualizados...\n")
    sys.stdout.flush()
    arquivos = [
        ("launcher.py", "https://raw.githubusercontent.com/dedneves/Stemplay/main/launcher.py"),
        ("s3_god_mode.py", "https://raw.githubusercontent.com/dedneves/Stemplay/main/s3_god_mode.py"),
        ("generate_library_premium.py", "https://raw.githubusercontent.com/dedneves/Stemplay/main/generate_library_premium.py"),
        ("start.bat", "https://raw.githubusercontent.com/dedneves/Stemplay/main/start.bat"),
        ("README.md", "https://raw.githubusercontent.com/dedneves/Stemplay/main/README.md"),
    ]

    for nome, url in arquivos:
        try:
            req = Request(url, headers={"User-Agent": "StemPlay-Launcher"})
            with urlopen(req, timeout=10) as resp:
                conteudo = resp.read()
            caminho = os.path.join(DIRETORIO, nome)
            with open(caminho, "wb") as f:
                f.write(conteudo)
            sys.stdout.write(f"    [ OK ] {nome}\n")
        except Exception as e:
            sys.stdout.write(f"    [ERRO] {nome}: {e}\n")
        sys.stdout.flush()

    sys.stdout.write("\n")
    sys.stdout.write("    [INFO] Atualizacao concluida. Reinicie o launcher.\n")
    sys.stdout.flush()
    input("    Pressione Enter para sair...")
    sys.exit(0)


def spinner(mensagem, parar_event):
    frames = ['|', '/', '-', '\\']
    i = 0
    while not parar_event.is_set():
        sys.stdout.write(f'\r    [{frames[i % 4]}] {mensagem}')
        sys.stdout.flush()
        i += 1
        time.sleep(0.1)
    sys.stdout.write('\r' + ' ' * (len(mensagem) + 10) + '\r')
    sys.stdout.flush()


def rodar_script(script, mensagem):
    proc = subprocess.Popen(
        [sys.executable, script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=DIRETORIO
    )
    parar = threading.Event()
    sp = threading.Thread(target=spinner, args=(mensagem, parar), daemon=True)
    sp.start()
    proc.communicate()
    parar.set()
    sp.join(timeout=1)
    if proc.returncode == 0:
        sys.stdout.write(f'\r    [ OK ] {mensagem}              \n')
        sys.stdout.flush()
        return True
    else:
        sys.stdout.write(f'\r    [ERRO] {mensagem}              \n')
        sys.stdout.flush()
        sys.stdout.write("    Rodando novamente para capturar erro...\n")
        sys.stdout.flush()
        proc2 = subprocess.run(
            [sys.executable, script],
            capture_output=True, text=True, cwd=DIRETORIO
        )
        if proc2.stderr:
            sys.stdout.write("\n    Detalhes:\n")
            for linha in proc2.stderr.split('\n')[:10]:
                sys.stdout.write("    " + linha + "\n")
        sys.stdout.flush()
        return False


def encontrar_porta_livre(preferida):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("0.0.0.0", preferida))
        s.close()
        return preferida
    except OSError:
        s.close()
        s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s2.bind(("0.0.0.0", 0))
        porta = s2.getsockname()[1]
        s2.close()
        return porta


class HandlerHTTP(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "StemPlay/13"

    def log_message(self, *args):
        pass

    def setup(self):
        super().setup()
        try:
            CONEXOES.adicionar(self.client_address[0], self.connection)
        except Exception:
            pass

    def finish(self):
        try:
            CONEXOES.remover(self.client_address[0], self.connection)
        except Exception:
            pass
        try:
            super().finish()
        except Exception:
            pass

    def _res(self, codigo, ctype, corpo, extra=None):
        if isinstance(corpo, str):
            corpo = corpo.encode('utf-8')
        self.send_response(codigo)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(corpo)))
        self.send_header('Access-Control-Allow-Origin', '*')
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != 'HEAD' and corpo:
            self.wfile.write(corpo)

    def _servir_html(self):
        caminho = os.path.join(DIRETORIO, HTML)
        if not os.path.exists(caminho):
            self._res(503, 'text/plain; charset=utf-8', 'Biblioteca ainda nao foi gerada. Rode o launcher novamente.')
            return
        try:
            with open(caminho, 'rb') as f:
                dados = f.read()
            self._res(200, 'text/html; charset=utf-8', dados)
        except Exception as e:
            self._res(500, 'text/plain', f'Erro ao ler HTML: {e}')

    def _proxy_pdf(self, query):
        chave = (parse_qs(query).get('key') or [''])[0]
        if not chave.startswith(ALLOWED_PROXY_PREFIX):
            self._res(403, 'text/plain', 'Chave de arquivo nao permitida.')
            return
        if self.command == 'HEAD':
            self.send_response(200)
            self.send_header('Content-Type', 'application/pdf')
            self.send_header('Content-Length', '0')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            return
        try:
            req = Request(chave, headers={"User-Agent": "Mozilla/5.0 StemPlay-Proxy"})
            with urlopen(req, timeout=30) as resp:
                self.send_response(200)
                self.send_header('Content-Type', 'application/pdf')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.close_connection = True
                self.end_headers()
                shutil.copyfileobj(resp, self.wfile, 65536)
        except Exception as e:
            try:
                self._res(502, 'text/plain', f'Falha no proxy S3: {e}')
            except Exception:
                self.close_connection = True

    def do_GET(self):
        ip = self.client_address[0]
        parsed = urlparse(self.path)
        pagina = parsed.path

        if pagina == '/__hb':
            if rastreador.esta_bloqueado(ip):
                self._res(403, 'text/plain', 'blocked')
            else:
                rastreador.registrar(ip, '/reader')
                self._res(200, 'text/plain', 'ok')
            return

        if rastreador.esta_bloqueado(ip):
            self._res(403, 'text/plain; charset=utf-8', 'Voce foi bloqueado pelo administrador da StemPlay Library.')
            return

        rastreador.registrar(ip, pagina)

        if pagina in ('/', '/index.html', '/' + HTML):
            self._servir_html()
        elif pagina == '/pdf':
            self._proxy_pdf(parsed.query)
        elif pagina in ('/favicon.ico', '/robots.txt', '/apple-touch-icon.png'):
            self._res(200, 'text/plain', '')
        else:
            self._res(404, 'text/plain', 'Nao encontrado')

    def do_HEAD(self):
        self.do_GET()


class ServidorHTTP(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def rodar_servidor(porta, event_parar):
    try:
        with ServidorHTTP(("0.0.0.0", porta), HandlerHTTP) as httpd:
            httpd.timeout = 1
            while not event_parar.is_set():
                httpd.handle_request()
    except OSError:
        pass


def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def mostrar_qr(url):
    try:
        import qrcode
        qr = qrcode.QRCode(box_size=1, border=1)
        qr.add_data(url)
        qr.print_ascii(invert=True)
    except ImportError:
        sys.stdout.write("    [AVISO] Instale 'qrcode':  pip install qrcode\n")
        sys.stdout.write(f"    Ou acesse: {url}\n")
    sys.stdout.flush()


console_lock = threading.Lock()


def linhas_visitantes():
    ativos = rastreador.ativos()
    linhas = []
    linhas.append(f"    {CIANO}{BOLD}Visitantes ativos: {len(ativos)}{RESET}")
    if ativos:
        for ip, dados in sorted(ativos.items(), key=lambda x: x[1]['ultimo'], reverse=True):
            origem = "LOCAL" if ip.startswith("127.") else "REDE "
            linhas.append(f"      {VERDE}*{RESET} {ip:<15} {AMARELO}[{origem}]{RESET} {DIM}{dados['pagina'][:24]}{RESET}")
    with rastreador.lock:
        bans = sorted(rastreador.bloqueados)
    if bans:
        linhas.append(f"      {VERMELHO}Bloqueados:{RESET} " + ", ".join(bans))
    return linhas


def _chave_visitantes():
    ativos = rastreador.ativos()
    with rastreador.lock:
        bans = frozenset(rastreador.bloqueados)
    return (frozenset(ativos.keys()), bans)


def painel_estatico():
    """Printa o estado atual como log simples (sem reposicionar cursor)."""
    with console_lock:
        for linha in linhas_visitantes():
            sys.stdout.write(linha + "\n")
        sys.stdout.flush()


def loop_visitantes(event_parar):
    """Loga apenas MUDANCAS (entrou/saiu/ban) - nada de redesenhar a tela,
    entao digitar comandos nunca duplica o painel."""
    ult_ips, ult_bans = _chave_visitantes()
    with console_lock:
        sys.stdout.write("\n")
        painel_estatico()
        sys.stdout.write(f"    {DIM}Comandos: ls | ban <ip> | unban <ip> | bans | ajuda | sair{RESET}\n")
        sys.stdout.write(f"    {DIM}Ctrl+C para encerrar.{RESET}\n\n")
        sys.stdout.flush()
    while not event_parar.is_set():
        for _ in range(10):
            if event_parar.is_set():
                return
            time.sleep(0.1)
        ips, bans = _chave_visitantes()
        if ips == ult_ips and bans == ult_bans:
            continue
        novos = ips - ult_ips
        saidos = ult_ips - ips
        novos_bans = bans - ult_bans
        soltos = ult_bans - bans
        with console_lock:
            for ip in sorted(novos):
                sys.stdout.write(f"    {VERDE}[+ENTROU]{RESET} {ip}\n")
            for ip in sorted(saidos):
                sys.stdout.write(f"    {DIM}[-saiu]   {ip}{RESET}\n")
            for ip in sorted(novos_bans):
                sys.stdout.write(f"    {VERMELHO}[BAN]     {ip}{RESET}\n")
            for ip in sorted(soltos):
                sys.stdout.write(f"    {VERDE}[UNBAN]   {ip}{RESET}\n")
            sys.stdout.write(f"    {DIM}Visitantes ativos: {len(ips)}{RESET}\n")
            sys.stdout.flush()
        ult_ips, ult_bans = ips, bans


def _say(texto):
    try:
        sys.stdout.write("\n" + texto + "\n")
        sys.stdout.flush()
    except Exception:
        pass


def processar_comando(linha):
    partes = linha.strip().split()
    if not partes:
        return True
    cmd = partes[0].lower()

    if cmd in ('ajuda', 'help', '?'):
        _say("  ls            -> visitantes ativos\n"
             "  ban <ip>      -> bloqueia e derruba conexoes do IP\n"
             "  unban <ip>    -> desbloqueia o IP\n"
             "  bans          -> lista bloqueados\n"
             "  sair          -> encerra os servidores")
    elif cmd in ('ls', 'visitantes'):
        ativos = rastreador.ativos()
        if not ativos:
            _say("  (nenhum visitante ativo)")
        else:
            for ip, d in sorted(ativos.items()):
                _say(f"  {ip:<15} {d['pagina']:<20} req={d['requests']}")
    elif cmd == 'bans':
        with rastreador.lock:
            bans = sorted(rastreador.bloqueados)
        _say("  Bloqueados: " + (", ".join(bans) if bans else "(nenhum)"))
    elif cmd in ('ban', 'bloquear'):
        if len(partes) < 2:
            _say("  Uso: ban <ip>   (veja 'ls' para listar IPs)")
        else:
            ip = partes[1]
            rastreador.banir(ip)
            _say(f"  {VERMELHO}[BAN]{RESET} {ip} bloqueado e conexoes encerradas.")
    elif cmd in ('unban', 'desbloquear'):
        if len(partes) < 2:
            _say("  Uso: unban <ip>")
        else:
            ip = partes[1]
            rastreador.desbanir(ip)
            _say(f"  {VERDE}[UNBAN]{RESET} {ip} liberado.")
    elif cmd in ('sair', 'exit', 'quit'):
        return False
    else:
        _say(f"  Comando desconhecido: {cmd}  (digite 'ajuda')")
    return True


def loop_cli(event_parar):
    while not event_parar.is_set():
        try:
            linha = sys.stdin.readline()
        except (EOFError, OSError, KeyboardInterrupt):
            return
        if not linha:
            return
        if not processar_comando(linha):
            event_parar.set()
            return


def main():
    os.chdir(DIRETORIO)
    limpar()

    checar_updates()
    banner_piscante()

    if not os.path.exists(PDFS):
        sys.stdout.write("    Primeira execucao: gerando lista de PDFs...\n")
        sys.stdout.flush()
        if not rodar_script("s3_god_mode.py", "Gerando lista de PDFs"):
            input("\n    Pressione Enter para sair...")
            sys.exit(1)
    else:
        sys.stdout.write("    [ OK ] Lista de PDFs encontrada\n")
        sys.stdout.flush()

    if not os.path.exists(HTML):
        if not rodar_script("generate_library_premium.py", "Gerando biblioteca HTML"):
            input("\n    Pressione Enter para sair...")
            sys.exit(1)
    else:
        sys.stdout.write("    [ OK ] Biblioteca HTML encontrada\n")
        sys.stdout.flush()

    sys.stdout.write("\n")
    sys.stdout.write("    Subindo servidores...\n")
    sys.stdout.flush()
    time.sleep(0.5)

    porta_local = encontrar_porta_livre(PORTA_LOCAL_PREF)
    porta_rede = encontrar_porta_livre(PORTA_REDE_PREF)

    ip = get_ip()
    url_local = f"http://localhost:{porta_local}/"
    url_rede = f"http://{ip}:{porta_rede}/"

    parar_event = threading.Event()
    t_local = threading.Thread(target=rodar_servidor, args=(porta_local, parar_event), daemon=True)
    t_rede = threading.Thread(target=rodar_servidor, args=(porta_rede, parar_event), daemon=True)
    t_local.start()
    t_rede.start()
    time.sleep(0.5)

    limpar()
    banner_estatico()
    sys.stdout.write("    Servidores no ar!\n")
    sys.stdout.write("    " + "─" * 44 + "\n")
    sys.stdout.write(f"    Local  :  {url_local}\n")
    sys.stdout.write(f"    Rede   :  {url_rede}\n")
    sys.stdout.write(f"    Pasta  :  {DIRETORIO}\n")
    if porta_local != PORTA_LOCAL_PREF:
        sys.stdout.write(f"    [INFO] Porta local ajustada: {porta_local}\n")
    if porta_rede != PORTA_REDE_PREF:
        sys.stdout.write(f"    [INFO] Porta rede ajustada: {porta_rede}\n")
    sys.stdout.write("    " + "─" * 44 + "\n")
    sys.stdout.write("\n")
    sys.stdout.write("    Escaneie o QR Code com o celular:\n")
    sys.stdout.write("\n")
    sys.stdout.flush()
    mostrar_qr(url_rede)
    sys.stdout.write("\n")
    sys.stdout.flush()

    t_cli = threading.Thread(target=loop_cli, args=(parar_event,), daemon=True)
    t_cli.start()

    t_visitantes = threading.Thread(target=loop_visitantes, args=(parar_event,), daemon=True)
    t_visitantes.start()

    try:
        while not parar_event.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    sys.stdout.write("\n\n    Encerrando servidores...\n")
    sys.stdout.flush()
    parar_event.set()
    time.sleep(0.3)
    sys.stdout.write("    Ate logo!\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
