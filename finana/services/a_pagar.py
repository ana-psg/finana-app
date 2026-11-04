# =============================================================
# services/a_pagar.py - dívidas com pessoas (ex: "pagar 3x de R$ 200 pro meu irmão")
# Cada dívida tem parcelas com vencimento; cada parcela é paga por conta ou cartão.
# =============================================================

from calendar import monthrange
from datetime import date

from finana.services.contas import categoria_ou_nada
from finana.services.pagamentos import desfazer, pagar_via
from finana.utils import ErroNegocio, add_months, agora


def criar(conn, pessoa, descricao, valor, modo, parcelas, primeiro_vencimento, categoria_id=None):
    """Cria a dívida e suas parcelas mensais.
    modo='total': valor é o total, dividido nas parcelas (a última absorve os centavos).
    modo='parcela': valor é o de cada parcela.
    primeiro_vencimento é um datetime. Retorna o id da dívida."""
    if not pessoa:
        raise ErroNegocio('Informe para quem é o pagamento.')
    if valor <= 0:
        raise ErroNegocio('Informe um valor maior que zero.')
    parcelas = max(int(parcelas), 1)

    if modo == 'parcela':
        valores = [valor] * parcelas
    else:
        base = round(valor / parcelas, 2)
        valores = [base] * (parcelas - 1) + [round(valor - base * (parcelas - 1), 2)]

    divida_id = conn.execute(
        """
        INSERT INTO debts (person, description, total_amount, category_id, created_at)
        VALUES (?, ?, ?, ?, ?)
    """,
        (
            pessoa,
            descricao,
            round(sum(valores), 2),
            categoria_ou_nada(conn, categoria_id),
            agora().strftime('%Y-%m-%d'),
        ),
    ).lastrowid

    dia = primeiro_vencimento.day
    for i, v in enumerate(valores):
        a, m = add_months(primeiro_vencimento.year, primeiro_vencimento.month, i)
        vence = date(a, m, min(dia, monthrange(a, m)[1]))  # dia 31 vira 30/28 nos meses curtos
        conn.execute(
            """
            INSERT INTO debt_installments (debt_id, installment_number, total_installments, amount, due_date)
            VALUES (?, ?, ?, ?, ?)
        """,
            (divida_id, i + 1, parcelas, v, vence.isoformat()),
        )
    return divida_id


def pagar_parcela(conn, parcela_id, data_pagamento, via, conta_id=None, cartao_id=None):
    p = conn.execute(
        """
        SELECT i.*, d.person, d.description, d.category_id FROM debt_installments i
        JOIN debts d ON d.id = i.debt_id WHERE i.id = ?
    """,
        (parcela_id,),
    ).fetchone()
    if not p:
        raise ErroNegocio('Parcela não encontrada.')
    if p['paid_date']:
        raise ErroNegocio('Essa parcela já está paga.')

    descricao = f'Pagamento {p["person"]}'
    if p['description']:
        descricao += f': {p["description"]}'
    if p['total_installments'] > 1:
        descricao += f' ({p["installment_number"]}/{p["total_installments"]})'

    transacao_id, compra_id = pagar_via(
        conn,
        descricao,
        p['amount'],
        data_pagamento,
        via,
        conta_id,
        cartao_id,
        p['category_id'],
        mes_referencia=p['due_date'][:7],
    )
    conn.execute(
        'UPDATE debt_installments SET paid_date = ?, transaction_id = ?, purchase_id = ? WHERE id = ?',
        (data_pagamento.strftime('%Y-%m-%d'), transacao_id, compra_id, parcela_id),
    )


def estornar_parcela(conn, parcela_id):
    """Desfaz o pagamento da parcela. Retorna False se ela foi paga no cartão e a fatura já foi paga."""
    p = conn.execute('SELECT * FROM debt_installments WHERE id = ?', (parcela_id,)).fetchone()
    if not p or not p['paid_date']:
        return True
    tudo_revertido = desfazer(conn, p['transaction_id'], p['purchase_id'])
    conn.execute(
        'UPDATE debt_installments SET paid_date = NULL, transaction_id = NULL, purchase_id = NULL WHERE id = ?',
        (parcela_id,),
    )
    return tudo_revertido


def excluir(conn, divida_id):
    """Remove a dívida. Pagamentos já feitos continuam nos lançamentos (o dinheiro saiu de verdade)."""
    conn.execute('DELETE FROM debt_installments WHERE debt_id = ?', (divida_id,))
    conn.execute('DELETE FROM debts WHERE id = ?', (divida_id,))
