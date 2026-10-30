# =============================================================
# services/contas.py - saldos e lançamentos em conta
# =============================================================

from datetime import datetime

from utils import ErroNegocio, add_months

# Receita que entra a partir deste dia conta no relatório do mês seguinte (o salário do dia 27,
# que às vezes cai antes por causa de fim de semana, paga as contas do mês seguinte).
DIA_VIRADA_RECEITA = 25


def mes_referencia_padrao(tipo, data):
    """Mês do relatório para um lançamento comum. data = 'AAAA-MM-DD'."""
    d = datetime.strptime(data, '%Y-%m-%d')
    if tipo == 'receita' and d.day >= DIA_VIRADA_RECEITA:
        a, m = add_months(d.year, d.month, 1)
        return f"{a}-{m:02d}"
    return data[:7]


def movimentar_saldo(conn, conta_id, delta):
    """Soma delta ao saldo, sempre arredondando em centavos (evita 219,82999...)."""
    conn.execute('UPDATE accounts SET balance = ROUND(balance + ?, 2) WHERE id = ?', (delta, conta_id))


def registrar_lancamento(conn, tipo, descricao, valor, data, conta_id, categoria_id, mes_referencia=None):
    """Cria o lançamento e atualiza o saldo da conta. Retorna o id do lançamento.
    mes_referencia: mês em que ele conta no relatório; vazio = regra padrão (mes_referencia_padrao)."""
    if tipo not in ('receita', 'despesa'):
        raise ErroNegocio('Tipo de lançamento inválido.')
    if valor <= 0:
        raise ErroNegocio('Informe um valor maior que zero.')
    if not conn.execute('SELECT 1 FROM accounts WHERE id = ?', (conta_id,)).fetchone():
        raise ErroNegocio('Escolha uma conta válida.')

    cur = conn.execute('''
        INSERT INTO transactions (type, description, amount, date, account_id, category_id, reference_month)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (tipo, descricao, valor, data, conta_id, categoria_id, mes_referencia or mes_referencia_padrao(tipo, data)))
    movimentar_saldo(conn, conta_id, valor if tipo == 'receita' else -valor)
    return cur.lastrowid


def excluir_lancamento(conn, lancamento_id):
    """Apaga o lançamento e desfaz o efeito no saldo.
    Se ele pagava uma despesa fixa, uma parcela "a pagar" ou uma fatura, ela volta a ficar pendente."""
    tx = conn.execute('SELECT amount, type, account_id FROM transactions WHERE id = ?', (lancamento_id,)).fetchone()
    if not tx:
        return
    movimentar_saldo(conn, tx['account_id'], -tx['amount'] if tx['type'] == 'receita' else tx['amount'])
    conn.execute('DELETE FROM fixed_expense_payments WHERE transaction_id = ?', (lancamento_id,))
    conn.execute('''
        UPDATE installments SET status = 'PENDENTE', invoice_payment_id = NULL
        WHERE invoice_payment_id IN (SELECT id FROM card_invoices_history WHERE transaction_id = ?)
    ''', (lancamento_id,))
    conn.execute('DELETE FROM card_invoices_history WHERE transaction_id = ?', (lancamento_id,))
    conn.execute('UPDATE debt_installments SET paid_date = NULL, transaction_id = NULL WHERE transaction_id = ?',
                 (lancamento_id,))
    conn.execute('DELETE FROM transactions WHERE id = ?', (lancamento_id,))
