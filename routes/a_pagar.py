from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for

from db import conectar
from services import a_pagar as svc
from utils import ErroNegocio, brl, data_valida, inteiro, parse_money

bp = Blueprint('a_pagar', __name__)


@bp.route('/a_pagar', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        f = request.form
        try:
            vencimento = data_valida(f.get('first_due'))
            if not vencimento:
                raise ErroNegocio('Informe a data do 1º pagamento.')
            with conectar() as conn:
                svc.criar(conn, f.get('person', '').strip(), f.get('description', '').strip(),
                          parse_money(f.get('amount')), f.get('mode'), inteiro(f.get('installments'), 1, 1, 120),
                          vencimento, f.get('category_id') or None)
        except ErroNegocio as e:
            flash(str(e), 'erro')
        return redirect(url_for('a_pagar.index'))

    mostrar_quitadas = request.args.get('quitadas') == '1'
    with conectar() as conn:
        categorias = conn.execute("SELECT id, name FROM categories ORDER BY name").fetchall()
        contas = conn.execute("SELECT id, name FROM accounts WHERE is_active = 1").fetchall()
        cartoes = conn.execute("SELECT id, name FROM cards WHERE is_active = 1").fetchall()
        dividas = []
        for d in conn.execute("SELECT * FROM debts ORDER BY created_at DESC, id DESC").fetchall():
            parcelas = conn.execute("SELECT * FROM debt_installments WHERE debt_id = ? ORDER BY installment_number",
                                    (d['id'],)).fetchall()
            pago = round(sum(p['amount'] for p in parcelas if p['paid_date']), 2)
            quitada = all(p['paid_date'] for p in parcelas)
            if quitada and not mostrar_quitadas:
                continue
            dividas.append({'d': d, 'parcelas': parcelas, 'pago': pago, 'falta': round(d['total_amount'] - pago, 2),
                            'pagas': sum(1 for p in parcelas if p['paid_date']), 'quitada': quitada})
        total_aberto = conn.execute("SELECT COALESCE(ROUND(SUM(amount), 2), 0) FROM debt_installments WHERE paid_date IS NULL"
                                    ).fetchone()[0]

    hoje = datetime.now().strftime('%Y-%m-%d')
    return render_template('a_pagar.html', dividas=dividas, categorias=categorias, contas=contas, cartoes=cartoes,
                           total_aberto=total_aberto, data_hoje=hoje, mostrar_quitadas=mostrar_quitadas)


@bp.route('/a_pagar/parcela/<int:id>/pagar', methods=['POST'])
def pagar(id):
    f = request.form
    try:
        with conectar() as conn:
            svc.pagar_parcela(conn, id, data_valida(f.get('paid_date')) or datetime.now(),
                              f.get('pagamento_tipo'), f.get('conta_id'), f.get('cartao_id'))
            valor = conn.execute('SELECT amount FROM debt_installments WHERE id = ?', (id,)).fetchone()[0]
        flash(f'Parcela paga: {brl(valor)}.', 'ok')
    except ErroNegocio as e:
        flash(str(e), 'erro')
    return redirect(url_for('a_pagar.index'))


@bp.route('/a_pagar/parcela/<int:id>/desfazer', methods=['POST'])
def estornar(id):
    with conectar() as conn:
        if not svc.estornar_parcela(conn, id):
            flash('Pagamento desmarcado. A compra no cartão ficou na fatura porque essa fatura já foi paga.', 'erro')
    return redirect(url_for('a_pagar.index'))


@bp.route('/a_pagar/<int:id>/apagar', methods=['POST'])
def apagar(id):
    with conectar() as conn:
        svc.excluir(conn, id)
    return redirect(url_for('a_pagar.index'))
