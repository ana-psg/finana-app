from flask import Blueprint, render_template

from finana.db import conectar
from finana.services.relatorio import visao_geral
from finana.utils import mes_atual

bp = Blueprint('dashboard', __name__)


@bp.route('/')
def index():
    with conectar() as conn:
        v = visao_geral(conn, mes_atual())
        contas_lista = conn.execute(
            'SELECT name, balance FROM accounts WHERE is_active = 1 ORDER BY balance DESC, name'
        ).fetchall()
        lancamentos_lista = conn.execute(
            'SELECT description, amount, type, date FROM transactions ORDER BY date DESC, id DESC LIMIT 5'
        ).fetchall()

    return render_template(
        'index.html',
        saldo_contas=v['saldo'],
        obrigacoes=v['obrigacoes'],
        disponivel_real=v['disponivel'],
        contas_lista=contas_lista,
        lancamentos_lista=lancamentos_lista,
    )
