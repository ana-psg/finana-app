from flask import Blueprint, flash, redirect, render_template, request, url_for

from finana.db import conectar
from finana.services import cartoes as svc
from finana.utils import (
    ErroNegocio,
    add_months,
    agora,
    brl,
    data_valida,
    inteiro,
    mes_valido,
    parse_money,
    texto_obrigatorio,
)

bp = Blueprint('faturas', __name__)


def _mes_padrao():
    """Por padrão mostra a fatura do mês que vem."""
    hoje = agora()
    a, m = add_months(hoje.year, hoje.month, 1)
    return f'{a}-{m:02d}'


@bp.route('/faturas', methods=['GET', 'POST'])
def index():
    mes = mes_valido(request.args.get('mes'), _mes_padrao())

    if request.method == 'POST':
        f = request.form
        try:
            data_compra = data_valida(f.get('date'))
            if not data_compra:
                raise ErroNegocio('Informe a data da compra.')
            descricao = texto_obrigatorio(f.get('description'), 'a descrição')
            with conectar() as conn:
                svc.registrar_compra(
                    conn,
                    f.get('card_id'),
                    descricao,
                    parse_money(f.get('total_amount')),
                    data_compra,
                    f.get('category_id'),
                    inteiro(f.get('installments'), 1, 1, 99),
                )
        except ErroNegocio as e:
            flash(str(e), 'erro')
        return redirect(url_for('faturas.index', mes=mes))

    with conectar() as conn:
        cartoes = conn.execute('SELECT id, name FROM cards WHERE is_active = 1').fetchall()
        contas = conn.execute('SELECT id, name FROM accounts WHERE is_active = 1').fetchall()
        categorias = conn.execute('SELECT id, name FROM categories ORDER BY name').fetchall()
        itens_fatura = conn.execute(
            """
            SELECT i.id, cp.description, i.amount, i.installment_number, i.total_installments,
                   c.name as cartao, c.id as cartao_id, i.status
            FROM installments i
            JOIN card_purchases cp ON i.purchase_id = cp.id
            JOIN cards c ON cp.card_id = c.id
            WHERE i.competence_month = ?
            ORDER BY c.name ASC, cp.date DESC
        """,
            (mes,),
        ).fetchall()
        historico = conn.execute("""
            SELECT h.*, c.name as cartao, a.name as conta
            FROM card_invoices_history h
            JOIN cards c ON h.card_id = c.id
            LEFT JOIN accounts a ON h.account_id = a.id
            ORDER BY h.competence_month DESC
        """).fetchall()
        cartoes_info = svc.resumo_faturas(conn, mes, agora())

    return render_template(
        'faturas.html',
        cartoes_info=cartoes_info,
        cartoes=cartoes,
        contas=contas,
        categorias=categorias,
        itens_fatura=itens_fatura,
        mes_selecionado=mes,
        historico=historico,
    )


@bp.route('/pagar_fatura_cartao', methods=['POST'])
def pagar():
    mes = mes_valido(request.form.get('competence_month'), _mes_padrao())
    try:
        with conectar() as conn:
            valor = svc.pagar_fatura(conn, request.form.get('card_id'), request.form.get('account_id'), mes)
        flash(
            f'Fatura paga: {brl(valor)}.' if valor else 'Não há nada pendente nessa fatura.', 'ok' if valor else 'erro'
        )
    except ErroNegocio as e:
        flash(str(e), 'erro')
    return redirect(url_for('faturas.index', mes=mes))


@bp.route('/faturas/pagamento/<int:id>/desfazer', methods=['POST'])
def desfazer(id):
    mes = mes_valido(request.form.get('mes'), _mes_padrao())
    with conectar() as conn:
        if svc.desfazer_pagamento_fatura(conn, id):
            flash('Pagamento desfeito: a fatura voltou a ficar pendente e o valor voltou para a conta.', 'ok')
        else:
            flash('Esse pagamento é de uma versão antiga do app e não pode ser desfeito por aqui.', 'erro')
    return redirect(url_for('faturas.index', mes=mes))
