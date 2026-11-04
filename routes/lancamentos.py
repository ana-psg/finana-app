from flask import Blueprint, flash, redirect, render_template, request, url_for

from db import conectar
from services.contas import excluir_lancamento, registrar_lancamento
from utils import ErroNegocio, data_valida, mes_atual, mes_valido, nome_mes, parse_money, texto_obrigatorio

bp = Blueprint('lancamentos', __name__)


@bp.route('/lancamentos', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        f = request.form
        try:
            if not data_valida(f.get('date')):
                raise ErroNegocio('Informe a data do lançamento.')
            descricao = texto_obrigatorio(f.get('description'), 'a descrição')
            with conectar() as conn:
                registrar_lancamento(conn, f.get('type'), descricao, parse_money(f.get('amount')),
                                     f['date'], f.get('account_id'), f.get('category_id'),
                                     mes_valido(f.get('reference_month'), None))  # vazio = automático
        except ErroNegocio as e:
            flash(str(e), 'erro')
        return redirect(url_for('lancamentos.index'))

    with conectar() as conn:
        contas = conn.execute("SELECT id, name FROM accounts WHERE is_active = 1").fetchall()
        categorias = conn.execute("SELECT id, name FROM categories ORDER BY name").fetchall()
        lancamentos_lista = conn.execute('''
            SELECT t.id, t.description, t.amount, t.type, t.date, t.reference_month, a.name as conta, c.name as categoria
            FROM transactions t
            LEFT JOIN accounts a ON t.account_id = a.id
            LEFT JOIN categories c ON t.category_id = c.id
            ORDER BY t.date DESC, t.id DESC
        ''').fetchall()
    return render_template('lancamentos.html', contas=contas, categorias=categorias,
                           lancamentos_lista=lancamentos_lista, mes_atual=mes_atual(), nome_mes=nome_mes)


@bp.route('/apagar_lancamento/<int:id>', methods=['POST'])
def apagar(id):
    with conectar() as conn:
        excluir_lancamento(conn, id)
    return redirect(url_for('lancamentos.index'))
