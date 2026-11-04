# =============================================================
# net.py - AnaFins
# Quem está pedindo, de onde e por qual endereço.
# =============================================================

import ipaddress
from urllib.parse import urlsplit

from flask import request

LOCAL_NAMES = ('localhost', '127.0.0.1', '::1')
# Cabeçalhos que só um intermediário (o `tailscale serve`) coloca; o navegador do PC nunca manda
PROXY_HEADERS = ('Tailscale-User-Login', 'X-Forwarded-For', 'X-Forwarded-Host')


def _host_name(host):
    return (urlsplit('//' + (host or '')).hostname or '').lower()


def public_host():
    """Endereço que o aparelho digitou (o `tailscale serve` pode trocar o Host pelo destino local)."""
    return request.headers.get('X-Forwarded-Host') or request.host


def is_local_request():
    """O pedido veio deste computador, digitado como localhost?

    Pedidos do celular chegam pelo `tailscale serve`, que também conecta de 127.0.0.1,
    mas com o endereço *.ts.net e cabeçalhos de intermediário: esses contam como de fora.
    """
    try:
        loopback = ipaddress.ip_address(request.remote_addr or '').is_loopback
    except ValueError:
        return False
    via_proxy = any(h in request.headers for h in PROXY_HEADERS)
    return loopback and not via_proxy and _host_name(public_host()) in LOCAL_NAMES


def host_allowed(host):
    """Só aceita localhost, endereço IP ou o endereço do Tailscale (*.ts.net) no Host.

    Um site com domínio próprio apontando para 127.0.0.1 (DNS rebinding) chega com o
    domínio dele no Host e é recusado.
    """
    name = _host_name(host)
    if name == 'localhost' or name.endswith('.ts.net'):
        return True
    try:
        ipaddress.ip_address(name)
        return True
    except ValueError:
        return False


def outro_site():
    """Pedido de escrita enviado por outro site (no PC o app não pede senha, então qualquer site poderia tentar)."""
    if request.method in ('GET', 'HEAD', 'OPTIONS'):
        return False
    origem = request.headers.get('Origin')
    return request.headers.get('Sec-Fetch-Site') == 'cross-site' or bool(
        origem and origem != 'null' and urlsplit(origem).netloc != public_host())
