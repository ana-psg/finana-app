"""Robô de telas: abre todas as telas do AnaFins, no computador e na largura do celular.

Falha se aparecer erro de JavaScript ou pedido para fora do computador. Usa um banco temporário.
Precisa do Playwright: pip install -r requirements-dev.txt && python -m playwright install chromium
Rodar: python tests/e2e_telas.py     (capturas na pasta indicada em ANAFINS_TELAS)
"""

import os
import sys
import tempfile
import threading
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
os.environ['ANAFINS_DB'] = os.path.join(tempfile.mkdtemp(prefix='anafins-e2e-'), 'teste.db')
OUT = os.environ.get('ANAFINS_TELAS') or tempfile.mkdtemp(prefix='anafins-telas-')
PORT = 8079
BASE = f'http://127.0.0.1:{PORT}'
TELAS = ['/', '/rapido', '/contas', '/pix', '/categorias', '/cartoes', '/faturas', '/lancamentos',
         '/relatorio_mensal', '/orcamento', '/despesas_fixas', '/a_pagar', '/investimentos', '/celular']
PERMITIR_EXTERNOS = os.environ.get('ANAFINS_PERMITIR_EXTERNOS') == '1'  # para comparar com versões antigas


def main():
    from app import app
    from seed import seed_database

    seed_database()
    srv = make_server('127.0.0.1', PORT, app, threaded=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    erros = []

    def nome(url, sufixo):
        return (url.strip('/') or 'inicio').replace('/', '-') + f'-{sufixo}.png'

    with sync_playwright() as p:
        navegador = p.chromium.launch()
        for sufixo, tamanho in (('pc', {'width': 1300, 'height': 850}), ('celular', {'width': 390, 'height': 844})):
            contexto = navegador.new_context(viewport=tamanho)
            pagina = contexto.new_page()
            pagina.on('pageerror', lambda e: erros.append(f'JS: {e}'))
            pagina.on('console', lambda m: erros.append(f'console: {m.text}') if m.type == 'error' else None)

            def registrar(pedido):
                if not PERMITIR_EXTERNOS and urlsplit(pedido.url).hostname not in ('127.0.0.1', None):
                    erros.append(f'pedido para fora: {pedido.url}')

            pagina.on('request', registrar)
            for url in TELAS:
                pagina.goto(BASE + url, wait_until='networkidle')
                pagina.screenshot(path=os.path.join(OUT, nome(url, sufixo)), full_page=True)
            contexto.close()
        navegador.close()
    srv.shutdown()
    for erro in sorted(set(erros)):
        print('ERRO:', erro)
    print(f'{len(TELAS) * 2} capturas em {OUT}; {len(set(erros))} erro(s).')
    return 1 if erros else 0


if __name__ == '__main__':
    sys.exit(main())
