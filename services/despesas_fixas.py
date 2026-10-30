# =============================================================
# services/despesas_fixas.py - pagar, desfazer e excluir despesas fixas
# =============================================================

from services.pagamentos import desfazer, pagar_via
from utils import ErroNegocio


def pagamento_do_mes(conn, despesa_id, mes):
    return conn.execute('SELECT * FROM fixed_expense_payments WHERE fixed_expense_id = ? AND competence_month = ?',
                        (despesa_id, mes)).fetchone()


def pagar(conn, despesa_id, mes, data_pagamento, via, conta_id=None, cartao_id=None):
    """Dá baixa na despesa do mês pela conta ou pelo cartão. data_pagamento é um datetime."""
    despesa = conn.execute('SELECT * FROM fixed_expenses WHERE id = ?', (despesa_id,)).fetchone()
    if not despesa:
        raise ErroNegocio('Despesa não encontrada.')
    if pagamento_do_mes(conn, despesa_id, mes):
        raise ErroNegocio(f"{despesa['description']} já está paga neste mês.")

    descricao = (f"{despesa['description']} (Mês: {mes})" if via == 'conta'
                 else f"Despesa Fixa: {despesa['description']} (Mês: {mes})")
    transacao_id, compra_id = pagar_via(conn, descricao, despesa['amount'], data_pagamento, via,
                                        conta_id, cartao_id, despesa['category_id'], mes_referencia=mes)
    conn.execute('''
        INSERT INTO fixed_expense_payments (fixed_expense_id, competence_month, paid_date, amount, transaction_id, purchase_id)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (despesa_id, mes, data_pagamento.strftime('%Y-%m-%d'), despesa['amount'], transacao_id, compra_id))


def estornar(conn, despesa_id, mes):
    """Desfaz o pagamento do mês. Retorna False se a compra já estava numa fatura paga
    (aí ela fica no cartão, só o pagamento é desmarcado)."""
    pagamento = pagamento_do_mes(conn, despesa_id, mes)
    if not pagamento:
        return True
    tudo_revertido = desfazer(conn, pagamento['transaction_id'], pagamento['purchase_id'])
    conn.execute('DELETE FROM fixed_expense_payments WHERE id = ?', (pagamento['id'],))
    return tudo_revertido


def excluir(conn, despesa_id):
    """Remove a despesa fixa. Lançamentos e compras já feitos continuam (o dinheiro saiu de verdade)."""
    conn.execute('DELETE FROM fixed_expense_payments WHERE fixed_expense_id = ?', (despesa_id,))
    conn.execute('DELETE FROM fixed_expenses WHERE id = ?', (despesa_id,))
