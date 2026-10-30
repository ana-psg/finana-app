# =============================================================
# routes/rapido.py - "Lançar rápido": uma tela só, feita para o celular
# Despesa ou receita numa conta, ou compra (parcelada ou não) num cartão.
# =============================================================

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for

from db import conectar
from services.cartoes import registrar_compra
from services.contas import registrar_lancamento
from utils import ErroNegocio, brl, data_valida, inteiro, parse_money

bp = Blueprint('rapido', __name__)


@bp.route('/rapido', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        f = request.form
        try:
            tipo = f.get('tipo')
            valor = parse_money(f.get('valor'))
            descricao = f.get('descricao', '').strip() or ('Receita' if tipo == 'receita' else 'Despesa')
            data = data_valida(f.get('data')) or datetime.now()
            categoria = f.get('categoria') or None
            destino, _, destino_id = (f.get('destino') or '').partition(':')

            with conectar() as conn:
                if destino == 'conta':
                    registrar_lancamento(conn, tipo, descricao, valor, data.strftime('%Y-%m-%d'), destino_id, categoria)
                    nome = conn.execute('SELECT name FROM accounts WHERE id = ?', (destino_id,)).fetchone()[0]
                elif destino == 'cartao':
                    if tipo != 'despesa':
                        raise ErroNegocio('No cartão só dá para lançar despesa.')
                    if valor <= 0:
                        raise ErroNegocio('Informe um valor maior que zero.')
                    parcelas = inteiro(f.get('parcelas'), 1, 1, 99)
                    registrar_compra(conn, destino_id, descricao, valor, data, categoria, parcelas)
                    nome = conn.execute('SELECT name FROM cards WHERE id = ?', (destino_id,)).fetchone()[0]
                    if parcelas > 1:
                        nome += f' em {parcelas}x'
                else:
                    raise ErroNegocio('Escolha a conta ou o cartão.')
            flash(f"{'Receita' if tipo == 'receita' else 'Despesa'} de {brl(valor)} lançada: {descricao} ({nome}).", 'ok')
        except ErroNegocio as e:
            flash(str(e), 'erro')
        return redirect(url_for('rapido.index'))

    with conectar() as conn:
        contas = conn.execute("SELECT id, name, balance FROM accounts WHERE is_active = 1 ORDER BY balance DESC, name").fetchall()
        cartoes = conn.execute("SELECT id, name FROM cards WHERE is_active = 1 ORDER BY name").fetchall()
        categorias = conn.execute("SELECT id, name, type FROM categories ORDER BY name").fetchall()
        ultimos = conn.execute('''
            SELECT * FROM (
                SELECT t.date, t.description, t.amount, t.type, a.name AS onde, t.id AS ordem FROM transactions t
                LEFT JOIN accounts a ON a.id = t.account_id
                UNION ALL
                SELECT cp.date, cp.description, cp.total_amount, 'cartao', c.name, cp.id FROM card_purchases cp
                JOIN cards c ON c.id = cp.card_id
            ) ORDER BY date DESC, ordem DESC LIMIT 8
        ''').fetchall()
    return render_template('rapido.html', contas=contas, cartoes=cartoes, categorias=categorias, ultimos=ultimos,
                           hoje=datetime.now().strftime('%Y-%m-%d'))
