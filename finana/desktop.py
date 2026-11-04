# =============================================================
# desktop.py - AnaFins
# Abre o app numa janela própria. Abrir de novo traz para frente a janela que já existe.
# =============================================================

import ctypes
import json
import logging
import os
import sys
import threading
import urllib.request
from logging.handlers import RotatingFileHandler

import webview
from werkzeug.serving import ThreadedWSGIServer, make_server

from finana.app import app
from finana.db import DB_FILE
from finana.routes import acesso

PORTA = 8000
ENDERECO = f'http://127.0.0.1:{PORTA}'
log = logging.getLogger('anafins')


def configurar_log():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
        handlers=[
            RotatingFileHandler(
                os.path.join(os.path.dirname(DB_FILE), 'anafins.log'),
                maxBytes=1_000_000,
                backupCount=3,
                encoding='utf-8',
            )
        ],
    )


def ja_aberto():
    """Se já tem um AnaFins aberto, traz a janela dele para frente e devolve True."""
    try:
        with urllib.request.urlopen(f'{ENDERECO}/ping', timeout=1.5) as r:
            if json.loads(r.read()).get('app') != 'AnaFins':
                return False
        pedido = urllib.request.Request(f'{ENDERECO}/janela/mostrar', method='POST', data=b'')
        urllib.request.urlopen(pedido, timeout=2).read()
        return True
    except Exception:
        return False


def avisar(texto):
    ctypes.windll.user32.MessageBoxW(0, texto, 'AnaFins', 0x10)


def main():
    configurar_log()
    if ja_aberto():
        return
    # No Windows, reaproveitar o endereço deixaria uma segunda cópia abrir na mesma porta sem dar erro
    ThreadedWSGIServer.allow_reuse_address = False
    try:
        # 0.0.0.0 = aceita o celular no Wi-Fi de casa (fora do computador, pede o PIN; ver routes/acesso.py)
        servidor = make_server('0.0.0.0', PORTA, app, threaded=True)
    except OSError as e:
        log.error('porta %s ocupada: %s', PORTA, e)
        avisar(f'A porta {PORTA} está em uso por outro programa. Feche esse programa e abra o AnaFins de novo.')
        sys.exit(1)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()

    janela = webview.create_window('AnaFins', ENDERECO, width=1300, height=850, background_color='#0f0f13')

    def mostrar():
        janela.show()
        janela.restore()

    acesso.ganchos['mostrar'] = mostrar
    webview.settings['ALLOW_DOWNLOADS'] = True  # baixar o PDF do relatório mensal
    webview.start()


if __name__ == '__main__':
    main()
