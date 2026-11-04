# =============================================================
# utils.py - AnaFins
# Helpers reutilizáveis: dinheiro, datas/meses e leitura de formulários.
# =============================================================

import math
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Flask

try:
    FUSO = ZoneInfo('America/Sao_Paulo')
except ZoneInfoNotFoundError:  # Windows sem o pacote tzdata; o Brasil não tem horário de verão desde 2019
    FUSO = timezone(timedelta(hours=-3))
VALOR_MAXIMO = 1e12
ANO_MINIMO, ANO_MAXIMO = 2000, 2100


# ---------------------------------------------------------------
# Dinheiro
# ---------------------------------------------------------------

def _ler_dinheiro(value):
    """Valor em float, ou None se o texto não for um valor em reais."""
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(value) else None
    s = str(value or '').replace('R$', '').replace(' ', '').strip()
    if re.fullmatch(r'[+-]?\d{1,3}(\.\d{3})+(,\d{1,2})?', s) or re.fullmatch(r'[+-]?\d+,\d{1,2}', s):
        s = s.replace('.', '').replace(',', '.')   # padrão BR: 1.500 / 1.234,56 / 10,5
    elif re.fullmatch(r'[+-]?\d{1,3}(,\d{3})+\.\d{1,2}', s):
        s = s.replace(',', '')                     # padrão US: 1,234.56
    elif not re.fullmatch(r'[+-]?\d+(\.\d{1,2})?', s):
        return None
    numero = round(float(s), 2)
    return numero if abs(numero) < VALOR_MAXIMO else None


def parse_money(value) -> float:
    """
    Converte texto em dinheiro, no padrão BR ou US.

        '1.234,56' / '1234,56' / '1,234.56' / '1234.56' / 'R$ 1.234,56' -> 1234.56
        '1.500' -> 1500.0 (ponto seguido de 3 dígitos é separador de milhar)
        vazio ou inválido ('abc', 'inf', '1,234') -> 0.0 (não estoura exceção)
    """
    return _ler_dinheiro(value) or 0.0


def dinheiro(value, campo) -> float:
    """Como parse_money, mas avisa quando o texto é inválido (para campos em que zero é um valor válido)."""
    numero = _ler_dinheiro(value)
    if numero is None:
        raise ErroNegocio(f'{campo}: valor inválido. Use o formato 1.234,56.')
    return numero


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


def agora() -> datetime:
    """Hora de São Paulo, sem fuso, seja qual for o fuso do computador."""
    return datetime.now(FUSO).replace(tzinfo=None)


def mes_atual() -> str:
    return agora().strftime('%Y-%m')


def add_months(ano, mes, n):
    total = ano * 12 + (mes - 1) + n
    return total // 12, total % 12 + 1


def nome_mes(competence) -> str:
    """'2026-10' -> 'outubro/2026'"""
    ano, mes = map(int, competence.split('-'))
    return f"{MESES_PT[mes - 1]}/{ano}"


def mes_valido(valor, padrao):
    """Aceita só 'AAAA-MM' (mês 01-12); qualquer outra coisa vira o padrão."""
    if valor and re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', valor) and ANO_MINIMO <= int(valor[:4]) <= ANO_MAXIMO:
        return valor
    return padrao


def lista_meses(mes_selecionado=None, antes=12, depois=15):
    """Opções do seletor de mês: 12 meses pra trás e 15 pra frente, sempre incluindo o selecionado."""
    hoje = agora()
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
    """'AAAA-MM-DD' válido e de um ano possível -> datetime; qualquer outra coisa -> None."""
    try:
        data = datetime.strptime(valor or '', '%Y-%m-%d')
    except ValueError:
        return None
    return data if ANO_MINIMO <= data.year <= ANO_MAXIMO else None


def texto_obrigatorio(valor, campo, maximo=200):
    """Texto sem espaços nas pontas; avisa se vier vazio."""
    texto = (valor or '').strip()
    if not texto:
        raise ErroNegocio(f'Informe {campo}.')
    return texto[:maximo]


class ErroNegocio(ValueError):
    """Erro de regra de negócio com mensagem para mostrar na tela."""


def register_jinja_filters(app: Flask) -> None:
    """Registra filtros/globals do Jinja no app Flask."""
    app.jinja_env.filters['brl'] = brl
    app.jinja_env.globals['brl'] = brl
    app.jinja_env.globals['lista_meses'] = lista_meses
