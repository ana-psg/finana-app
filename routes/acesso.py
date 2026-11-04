# =============================================================
# routes/acesso.py - acesso pelo celular (Wi-Fi de casa)
#
# No próprio computador (127.0.0.1) o app abre direto, como sempre.
# De qualquer outro aparelho da rede, pede o PIN definido em "Celular".
# =============================================================

import socket
import time

from flask import Blueprint, Response, abort, jsonify, redirect, render_template, request, session, url_for

from db import conectar
from net import host_allowed, is_local_request, outro_site, public_host
from qr import svg as qr_svg
from services import config
from utils import ErroNegocio

bp = Blueprint('acesso', __name__)

PORTA = 8000
MAX_TENTATIVAS = 5
BLOQUEIO_SEGUNDOS = 5 * 60
_falhas = {}  # ip -> (quantidade de erros seguidos, bloqueado até)
LIVRES = {'static', 'acesso.entrar', 'acesso.manifest', 'acesso.ping'}
ganchos = {}  # desktop.py preenche: 'mostrar' traz a janela para frente


def ip_na_rede():
    """IP deste computador no Wi-Fi (ex: 192.168.0.10). Não envia nada pela rede."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(('10.255.255.255', 1))
            return s.getsockname()[0]
    except OSError:
        return None


@bp.before_app_request
def bloquear_outros_sites():
    """Endereço de outro site (DNS rebinding) ou envio vindo de outro site (CSRF)."""
    if not (host_allowed(request.host) and host_allowed(public_host())):
        return Response('Endereço não permitido.', 403)
    if outro_site():
        return Response('Pedido de outro site bloqueado.', 403)
    return None


@bp.before_app_request
def exigir_pin():
    if request.endpoint in LIVRES or is_local_request():
        return None
    if session.get('autorizado'):
        with conectar() as conn:
            if session.get('pin_versao') == config.versao_pin(conn):
                return None
        session.clear()  # o PIN mudou depois que este aparelho entrou
    return redirect(url_for('acesso.entrar', proximo=request.path))


@bp.route('/entrar', methods=['GET', 'POST'])
def entrar():
    with conectar() as conn:
        tem_pin = config.tem_pin(conn)
    erro = None
    ip = request.remote_addr
    erros, bloqueado_ate = _falhas.get(ip, (0, 0))

    if request.method == 'POST' and tem_pin:
        if time.time() < bloqueado_ate:
            erro = 'Muitas tentativas erradas. Espere alguns minutos e tente de novo.'
        else:
            with conectar() as conn:
                ok = config.pin_correto(conn, request.form.get('pin'))
                versao = config.versao_pin(conn)
            if ok:
                _falhas.pop(ip, None)
                session.clear()
                session.permanent = True
                session['autorizado'] = True
                session['pin_versao'] = versao
                proximo = request.args.get('proximo', '')
                # só aceita caminhos internos (evita redirecionar para outro site);
                # o navegador lê "\" como "/", então "/\site.com" também é outro site
                interno = proximo.replace('\\', '/')
                return redirect(proximo if interno.startswith('/') and not interno.startswith('//')
                                else url_for('rapido.index'))
            erros += 1
            _falhas[ip] = (0, time.time() + BLOQUEIO_SEGUNDOS) if erros >= MAX_TENTATIVAS else (erros, 0)
            erro = 'PIN incorreto.'

    return render_template('entrar.html', tem_pin=tem_pin, erro=erro)


@bp.route('/sair')
def sair():
    session.clear()
    return redirect(url_for('acesso.entrar'))


@bp.route('/celular', methods=['GET', 'POST'])
def configuracoes():
    """Só no computador: definir o PIN e ver o endereço para abrir no celular."""
    if not is_local_request():
        abort(403)
    erro = ok = None
    if request.method == 'POST':
        try:
            with conectar() as conn:
                config.definir_pin(conn, request.form.get('pin'), request.form.get('confirmacao'))
            ok = 'PIN salvo. Agora é só abrir o endereço abaixo no celular.'
        except ErroNegocio as e:
            erro = str(e)
    with conectar() as conn:
        tem_pin = config.tem_pin(conn)
    ip = ip_na_rede()
    endereco = f'http://{ip}:{PORTA}' if ip else None
    return render_template('celular.html', tem_pin=tem_pin, endereco=endereco, erro=erro, ok=ok,
                           qr=qr_svg(endereco) if endereco else '')


@bp.route('/ping')
def ping():
    """Permite ao desktop.py descobrir se já tem um AnaFins aberto nesta porta."""
    return jsonify(app='AnaFins')


@bp.route('/janela/mostrar', methods=['POST'])
def mostrar_janela():
    if not is_local_request():
        abort(403)
    if ganchos.get('mostrar'):
        ganchos['mostrar']()
    return jsonify(ok=True)


@bp.route('/manifest.webmanifest')
def manifest():
    """Permite 'Adicionar à tela inicial' no celular, abrindo como um app."""
    resp = jsonify({
        'name': 'AnaFins', 'short_name': 'AnaFins',
        'start_url': url_for('rapido.index'), 'display': 'standalone',
        'background_color': '#0f0f13', 'theme_color': '#0f0f13',
        'icons': [{'src': url_for('static', filename=f'icon-{t}.png'), 'sizes': f'{t}x{t}', 'type': 'image/png'}
                  for t in (192, 512)],
    })
    resp.mimetype = 'application/manifest+json'
    return resp
