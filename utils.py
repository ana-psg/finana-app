# =============================================================
# utils.py - AnaFins
# Helpers reutilizáveis: dinheiro, datas/meses e leitura de formulários.
# =============================================================

import re
from datetime import datetime

from flask import Flask


# ---------------------------------------------------------------
# Dinheiro
# ---------------------------------------------------------------

def parse_money(value) -> float:
    """
    Converte string monetária (padrão BR ou US) para float.

        '1.234,56' / '1234,56' / '1,234.56' / '1234.56' / 'R$ 1.234,56' -> 1234.56
        '' ou None -> 0.0

    Retorna 0.0 em caso de falha (não estoura exceção).
    """
    if value is None or value == '':
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)

    s = str(value).strip().replace('R$', '').replace(' ', '').strip()
    if not s:
        return 0.0

    if ',' in s and '.' in s:
        if s.rfind(',') > s.rfind('.'):
            s = s.replace('.', '').replace(',', '.')  # padrão BR
        else:
            s = s.replace(',', '')                     # padrão US
    elif ',' in s:
        s = s.replace(',', '.')

    try:
        return round(float(s), 2)
    except ValueError:
        return 0.0


def brl(value) -> str:
    """Formata como moeda brasileira: 'R$ 1.234,56'. Aceita None/str/float e nunca estoura."""
    try:
        value = float(value or 0)
    except (ValueError, TypeError):
        value = 0.0
    return f"R$ {value:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')


# ---------------------------------------------------------------
# Meses ('AAAA-MM')
# ---------------------------------------------------------------

MESES_PT = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
            'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']


def mes_atual() -> str:
    return datetime.now().strftime('%Y-%m')


def add_months(ano, mes, n):
    total = ano * 12 + (mes - 1) + n
    return total // 12, total % 12 + 1


def nome_mes(competence) -> str:
    """'2026-10' -> 'outubro/2026'"""
    ano, mes = map(int, competence.split('-'))
    return f"{MESES_PT[mes - 1]}/{ano}"


def mes_valido(valor, padrao):
    """Aceita só 'AAAA-MM' (mês 01-12); qualquer outra coisa vira o padrão."""
    if valor and re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', valor):
        return valor
    return padrao


def lista_meses(mes_selecionado=None, antes=12, depois=15):
    """Opções do seletor de mês: 12 meses pra trás e 15 pra frente, sempre incluindo o selecionado."""
    hoje = datetime.now()
    meses = [f"{a}-{m:02d}" for a, m in (add_months(hoje.year, hoje.month, n) for n in range(-antes, depois + 1))]
    if mes_selecionado and mes_selecionado not in meses:
        meses = sorted(meses + [mes_selecionado])
    return [(v, nome_mes(v).replace('/', ' / ').capitalize()) for v in meses]


# ---------------------------------------------------------------
# Formulários
# ---------------------------------------------------------------

def inteiro(valor, padrao=None, minimo=None, maximo=None):
    """int seguro: texto inválido vira o padrão; limita a [minimo, maximo] se informados."""
    try:
        n = int(valor)
    except (TypeError, ValueError):
        return padrao
    if minimo is not None:
        n = max(n, minimo)
    if maximo is not None:
        n = min(n, maximo)
    return n


def data_valida(valor):
    """'AAAA-MM-DD' válido -> datetime; qualquer outra coisa -> None."""
    try:
        return datetime.strptime(valor or '', '%Y-%m-%d')
    except ValueError:
        return None


class ErroNegocio(ValueError):
    """Erro de regra de negócio com mensagem para mostrar na tela."""


def register_jinja_filters(app: Flask) -> None:
    """Registra filtros/globals do Jinja no app Flask."""
    app.jinja_env.filters['brl'] = brl
    app.jinja_env.globals['brl'] = brl
    app.jinja_env.globals['lista_meses'] = lista_meses
