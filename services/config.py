# =============================================================
# services/config.py - configurações guardadas no banco (tabela settings)
# =============================================================

import secrets

from werkzeug.security import check_password_hash, generate_password_hash

from utils import ErroNegocio


def obter(conn, chave, padrao=None):
    row = conn.execute('SELECT value FROM settings WHERE key = ?', (chave,)).fetchone()
    return row[0] if row else padrao


def definir(conn, chave, valor):
    conn.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (chave, valor))


def chave_secreta(conn):
    """Chave das sessões. Fica salva para o celular não precisar entrar de novo a cada vez que o app abre."""
    chave = obter(conn, 'secret_key')
    if not chave:
        chave = secrets.token_hex(32)
        definir(conn, 'secret_key', chave)
    return chave


def tem_pin(conn):
    return bool(obter(conn, 'pin_hash'))


def definir_pin(conn, pin, confirmacao):
    pin = (pin or '').strip()
    if not pin.isdigit() or not 4 <= len(pin) <= 8:
        raise ErroNegocio('O PIN precisa ter de 4 a 8 números.')
    if pin != (confirmacao or '').strip():
        raise ErroNegocio('A confirmação não bate com o PIN.')
    definir(conn, 'pin_hash', generate_password_hash(pin))


def pin_correto(conn, pin):
    hash_salvo = obter(conn, 'pin_hash')
    return bool(hash_salvo) and check_password_hash(hash_salvo, (pin or '').strip())
