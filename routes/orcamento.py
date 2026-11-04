from flask import Blueprint, flash, redirect, render_template, request, url_for

from db import conectar
from services.contas import categoria_ou_nada
from services.relatorio import EH_PAGAMENTO_DE_FATURA, MES_DO_LANCAMENTO
from utils import ErroNegocio, dinheiro, mes_atual

bp = Blueprint('orcamento', __name__)


@bp.route('/orcamento', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        try:
            limite = dinheiro(request.form.get('amount_limit'), 'Limite')
            if limite <= 0:
                raise ErroNegocio('Informe um limite maior que zero.')
            with conectar() as conn:
                categoria = categoria_ou_nada(conn, request.form.get('category_id'))
                if categoria is None:
                    raise ErroNegocio('Escolha uma categoria.')
                conn.execute('INSERT OR REPLACE INTO budgets (category_id, amount_limit) VALUES (?, ?)', (categoria, limite))
        except ErroNegocio as e:
            flash(str(e), 'erro')
        return redirect(url_for('orcamento.index'))

    # Gasto do MÊS ATUAL: lançamentos do mês + parcelas de cartão que caem na fatura do mês
    # (mesma regra do relatório: pagamento de fatura não conta de novo)
    mes = mes_atual()
    with conectar() as conn:
        categorias = conn.execute("SELECT id, name FROM categories ORDER BY name").fetchall()
        orcamentos_lista = conn.execute(f'''
            SELECT b.id, c.name as categoria, b.amount_limit,
                (COALESCE((SELECT SUM(t.amount) FROM transactions t
                           WHERE t.category_id = c.id AND t.type = 'despesa'
                             AND {MES_DO_LANCAMENTO} = :mes AND NOT {EH_PAGAMENTO_DE_FATURA}), 0) +
                 COALESCE((SELECT SUM(i.amount) FROM installments i
                           JOIN card_purchases cp ON i.purchase_id = cp.id
                           WHERE cp.category_id = c.id AND i.competence_month = :mes), 0)) as gasto
            FROM budgets b
            JOIN categories c ON b.category_id = c.id
            ORDER BY b.amount_limit DESC
        ''', {'mes': mes}).fetchall()
    return render_template('orcamento.html', categorias=categorias, orcamentos_lista=orcamentos_lista)


@bp.route('/apagar_orcamento/<int:id>', methods=['POST'])
def apagar(id):
    with conectar() as conn:
        conn.execute('DELETE FROM budgets WHERE id = ?', (id,))
    return redirect(url_for('orcamento.index'))
