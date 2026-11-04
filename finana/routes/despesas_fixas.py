from flask import Blueprint, flash, redirect, render_template, request, url_for

from finana.db import conectar
from finana.services import despesas_fixas as svc
from finana.services.contas import categoria_ou_nada
from finana.utils import ErroNegocio, agora, data_valida, inteiro, mes_atual, mes_valido, parse_money, texto_obrigatorio

bp = Blueprint('despesas_fixas', __name__)


@bp.route('/despesas_fixas', methods=['GET', 'POST'])
def index():
    mes = mes_valido(request.args.get('mes'), mes_atual())

    if request.method == 'POST':
        f = request.form
        valor = parse_money(f.get('amount'))
        try:
            descricao = texto_obrigatorio(f.get('description'), 'a descrição')
            if valor <= 0:
                raise ErroNegocio('Informe um valor maior que zero.')
            with conectar() as conn:
                conn.execute(
                    'INSERT INTO fixed_expenses (description, amount, due_day, category_id) VALUES (?, ?, ?, ?)',
                    (
                        descricao,
                        valor,
                        inteiro(f.get('due_day'), 1, 1, 31),
                        categoria_ou_nada(conn, f.get('category_id')),
                    ),
                )
        except ErroNegocio as e:
            flash(str(e), 'erro')
        return redirect(url_for('despesas_fixas.index', mes=mes))

    with conectar() as conn:
        categorias = conn.execute('SELECT id, name FROM categories ORDER BY name').fetchall()
        contas = conn.execute('SELECT id, name, type, balance FROM accounts WHERE is_active = 1').fetchall()
        cartoes = conn.execute('SELECT id, name, bank FROM cards WHERE is_active = 1').fetchall()
        despesas_lista = conn.execute(
            """
            SELECT f.*, c.name as categoria, p.id as payment_id, p.paid_date as payment_date
            FROM fixed_expenses f
            LEFT JOIN categories c ON f.category_id = c.id
            LEFT JOIN fixed_expense_payments p ON f.id = p.fixed_expense_id AND p.competence_month = ?
            WHERE f.is_active = 1
            ORDER BY f.due_day ASC
        """,
            (mes,),
        ).fetchall()

    return render_template(
        'despesas_fixas.html',
        categorias=categorias,
        contas=contas,
        cartoes=cartoes,
        despesas_lista=despesas_lista,
        mes_selecionado=mes,
        data_hoje=agora().strftime('%Y-%m-%d'),
    )


@bp.route('/pagar_despesa_fixa/<int:id>', methods=['POST'])
def pagar(id):
    f = request.form
    mes = mes_valido(f.get('competence_month'), mes_atual())
    try:
        with conectar() as conn:
            svc.pagar(
                conn,
                id,
                mes,
                data_valida(f.get('paid_date')) or agora(),
                f.get('pagamento_tipo'),
                f.get('conta_id'),
                f.get('cartao_id'),
            )
    except ErroNegocio as e:
        flash(str(e), 'erro')
    return redirect(url_for('despesas_fixas.index', mes=mes))


@bp.route('/estornar_despesa_fixa/<int:id>', methods=['POST'])
def estornar(id):
    mes = mes_valido(request.form.get('competence_month'), mes_atual())
    with conectar() as conn:
        if not svc.estornar(conn, id, mes):
            flash('Pagamento desmarcado. A compra no cartão ficou na fatura porque essa fatura já foi paga.', 'erro')
    return redirect(url_for('despesas_fixas.index', mes=mes))


@bp.route('/apagar_despesa_fixa/<int:id>', methods=['POST'])
def apagar(id):
    with conectar() as conn:
        svc.excluir(conn, id)
    return redirect(url_for('despesas_fixas.index'))
