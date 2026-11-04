# =============================================================
# services/cartoes.py - compras parceladas e faturas
# Mês da fatura = mês de VENCIMENTO (quando você paga).
# =============================================================

from calendar import monthrange
from datetime import date

from finana.services.contas import categoria_ou_nada, excluir_lancamento, registrar_lancamento
from finana.utils import ErroNegocio, add_months, agora, nome_mes


def competencia_da_compra(data_compra, closing_day, due_day):
    """Mês de vencimento da fatura em que a compra entra.
    Compra no dia de fechamento ou depois vai pra fatura seguinte (o dia de fechamento é o "melhor dia de compra")."""
    # fechamento dia 31 em abril fecha no dia 30 (igual a datas_fatura)
    fecha = min(closing_day, monthrange(data_compra.year, data_compra.month)[1])
    a, m = add_months(data_compra.year, data_compra.month, 1 if data_compra.day >= fecha else 0)
    if due_day <= closing_day:  # vence no mês seguinte ao fechamento
        a, m = add_months(a, m, 1)
    return f'{a}-{m:02d}'


def datas_fatura(competence, closing_day, due_day):
    """competence = mês de vencimento. Retorna (data de fechamento, data de vencimento)."""
    ano, mes = map(int, competence.split('-'))
    vence = date(ano, mes, min(due_day, monthrange(ano, mes)[1]))
    fa, fm = (ano, mes) if due_day > closing_day else add_months(ano, mes, -1)
    fecha = date(fa, fm, min(closing_day, monthrange(fa, fm)[1]))
    return fecha, vence


def registrar_compra(conn, cartao_id, descricao, valor_total, data_compra, categoria_id, parcelas=1):
    """Cria a compra e suas parcelas, cada uma na fatura certa. Retorna o id da compra.
    data_compra é um datetime; valor negativo é permitido (crédito/estorno)."""
    if valor_total == 0:
        raise ErroNegocio('Informe o valor da compra.')
    cartao = conn.execute(
        'SELECT closing_day, due_day FROM cards WHERE id = ? AND is_active = 1', (cartao_id,)
    ).fetchone()
    if not cartao:
        raise ErroNegocio('Escolha um cartão válido.')
    parcelas = max(int(parcelas), 1)

    compra_id = conn.execute(
        'INSERT INTO card_purchases (card_id, description, total_amount, date, category_id) VALUES (?, ?, ?, ?, ?)',
        (cartao_id, descricao, valor_total, data_compra.strftime('%Y-%m-%d'), categoria_ou_nada(conn, categoria_id)),
    ).lastrowid

    ano, mes = map(int, competencia_da_compra(data_compra, cartao['closing_day'], cartao['due_day']).split('-'))
    valor_parcela = round(valor_total / parcelas, 2)
    for i in range(1, parcelas + 1):
        a, m = add_months(ano, mes, i - 1)
        # a última parcela absorve a diferença do arredondamento (100 em 3x = 33,33 + 33,33 + 33,34)
        valor = valor_parcela if i < parcelas else round(valor_total - valor_parcela * (parcelas - 1), 2)
        conn.execute(
            """
            INSERT INTO installments (purchase_id, amount, installment_number, total_installments, competence_month, status)
            VALUES (?, ?, ?, ?, ?, 'PENDENTE')
        """,
            (compra_id, valor, i, parcelas, f'{a}-{m:02d}'),
        )
    return compra_id


def excluir_compra(conn, compra_id):
    """Apaga a compra e as parcelas, só se nenhuma parcela já foi paga. Retorna True se apagou."""
    if conn.execute("SELECT 1 FROM installments WHERE purchase_id = ? AND status = 'PAGO'", (compra_id,)).fetchone():
        return False
    conn.execute('DELETE FROM installments WHERE purchase_id = ?', (compra_id,))
    conn.execute('DELETE FROM card_purchases WHERE id = ?', (compra_id,))
    conn.execute(
        'UPDATE debt_installments SET paid_date = NULL, purchase_id = NULL WHERE purchase_id = ?', (compra_id,)
    )
    conn.execute('DELETE FROM fixed_expense_payments WHERE purchase_id = ?', (compra_id,))
    return True


def _total(conn, cartao_id, mes, so_pendente):
    filtro = "AND i.status = 'PENDENTE'" if so_pendente else ''
    return conn.execute(
        f"""
        SELECT COALESCE(ROUND(SUM(i.amount), 2), 0) FROM installments i
        JOIN card_purchases cp ON i.purchase_id = cp.id
        WHERE cp.card_id = ? AND i.competence_month = ? {filtro}
    """,
        (cartao_id, mes),
    ).fetchone()[0]


def resumo_faturas(conn, mes, hoje):
    """Um resumo por cartão ativo da fatura do mês: datas, status (aberta/fechada/paga) e valor."""
    resumo = []
    for c in conn.execute('SELECT id, name, closing_day, due_day FROM cards WHERE is_active = 1').fetchall():
        fecha, vence = datas_fatura(mes, c['closing_day'], c['due_day'])
        atual = competencia_da_compra(hoje, c['closing_day'], c['due_day'])
        pendente = _total(conn, c['id'], mes, so_pendente=True)
        total = _total(conn, c['id'], mes, so_pendente=False)

        if fecha > hoje.date():
            status, valor = 'aberta', pendente  # ainda não fechou: mostra o que falta pagar
        elif total == 0 or pendente == 0:
            status, valor = 'paga', total  # fechou e não deve nada: mostra o total gasto
        else:
            status, valor = 'fechada', pendente  # fechou e ainda deve

        resumo.append(
            {
                'id': c['id'],
                'name': c['name'],
                'fatura_label': nome_mes(mes),
                'fecha': fecha.strftime('%d/%m/%Y'),
                'vence': vence.strftime('%d/%m/%Y'),
                'status': status,
                'eh_atual': mes == atual,
                'atual_label': nome_mes(atual),
                'total_pendente': valor,
            }
        )
    return resumo


def pagar_fatura(conn, cartao_id, conta_id, mes):
    """Marca as parcelas pendentes do mês como pagas, debita a conta com um lançamento e guarda no histórico.
    Retorna o valor pago (0 se não havia nada pendente)."""
    cartao = conn.execute('SELECT name FROM cards WHERE id = ?', (cartao_id,)).fetchone()
    if not cartao:
        raise ErroNegocio('Escolha um cartão válido.')
    if not conn.execute('SELECT 1 FROM accounts WHERE id = ? AND is_active = 1', (conta_id,)).fetchone():
        raise ErroNegocio('Escolha uma conta válida.')
    valor = _total(conn, cartao_id, mes, so_pendente=True)
    if valor <= 0:
        return 0
    momento = agora()
    # o lançamento explica a saída do saldo; o relatório não conta como despesa nova (ver services/relatorio.py)
    transacao_id = registrar_lancamento(
        conn,
        'despesa',
        f'Pagamento Fatura {cartao["name"]} ({nome_mes(mes)})',
        valor,
        momento.strftime('%Y-%m-%d'),
        conta_id,
        None,
        mes_referencia=mes,
    )
    pagamento_id = conn.execute(
        """
        INSERT INTO card_invoices_history (card_id, competence_month, total_amount, paid_date, account_id, transaction_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """,
        (cartao_id, mes, valor, momento.strftime('%Y-%m-%d %H:%M:%S'), conta_id, transacao_id),
    ).lastrowid
    conn.execute(
        """
        UPDATE installments SET status = 'PAGO', invoice_payment_id = ?
        WHERE status = 'PENDENTE' AND competence_month = ?
          AND purchase_id IN (SELECT id FROM card_purchases WHERE card_id = ?)
    """,
        (pagamento_id, mes, cartao_id),
    )
    return valor


def desfazer_pagamento_fatura(conn, pagamento_id):
    """Volta as parcelas para pendente e devolve o dinheiro à conta.
    Pagamentos feitos antes da v1.3 não guardam o lançamento: retorna False e não mexe em nada."""
    pagamento = conn.execute(
        'SELECT transaction_id FROM card_invoices_history WHERE id = ?', (pagamento_id,)
    ).fetchone()
    if not pagamento or not pagamento['transaction_id']:
        return False
    excluir_lancamento(conn, pagamento['transaction_id'])  # desfaz parcelas, histórico e saldo
    return True
