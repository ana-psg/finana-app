# =============================================================
# services/relatorio.py - números do relatório mensal e da visão geral
# Usado pela tela "Relatório Mensal", pelo painel e pelo PDF (services/relatorio_pdf.py).
# =============================================================

from services.cartoes import resumo_faturas
from utils import add_months

# O lançamento conta no mês de referência (ex: salário de 25/09 conta em outubro), não no mês da data.
MES_DO_LANCAMENTO = "COALESCE(t.reference_month, strftime('%Y-%m', t.date))"

# Lançamentos que só movem dinheiro para pagar fatura não são receita nem despesa nova
# (as compras já contam pelas faturas). Ex: "Pagamento Fatura Inter", "Pix P/ Fatura".
# Só "Fatura" no nome: "Cartão" escondia gastos de verdade, como "Anuidade do cartão".
EH_PAGAMENTO_DE_FATURA = ("(t.description LIKE '%Fatura%' OR t.id IN "
                          "(SELECT transaction_id FROM card_invoices_history WHERE transaction_id IS NOT NULL))")

MESES_A_FRENTE = 6  # quantas faturas futuras o PDF mostra


def resumo_do_mes(conn, mes):
    """Totais do mês: receitas, despesas (lançamentos), faturas, saídas e balanço."""
    def soma(tipo):
        return conn.execute(f'''
            SELECT COALESCE(ROUND(SUM(t.amount), 2), 0) FROM transactions t
            WHERE t.type = ? AND {MES_DO_LANCAMENTO} = ? AND NOT {EH_PAGAMENTO_DE_FATURA}
        ''', (tipo, mes)).fetchone()[0]

    receitas, despesas = soma('receita'), soma('despesa')
    faturas = conn.execute("SELECT COALESCE(ROUND(SUM(amount), 2), 0) FROM installments WHERE competence_month = ?",
                           (mes,)).fetchone()[0]
    saidas = round(faturas + despesas, 2)
    return {'receitas': receitas, 'despesas': despesas, 'faturas': faturas,
            'saidas': saidas, 'balanco': round(receitas - saidas, 2)}


def lancamentos_do_mes(conn, mes):
    return conn.execute(f'''
        SELECT t.*, c.name as categoria, a.name as conta, {EH_PAGAMENTO_DE_FATURA} as pagamento_fatura
        FROM transactions t
        LEFT JOIN categories c ON t.category_id = c.id
        LEFT JOIN accounts a ON t.account_id = a.id
        WHERE {MES_DO_LANCAMENTO} = ? ORDER BY t.date DESC, t.id DESC
    ''', (mes,)).fetchall()


def parcelas_do_mes(conn, mes):
    return conn.execute('''
        SELECT i.*, cp.description, cp.date as data_compra, cp.card_id, c.name as cartao, cat.name as categoria
        FROM installments i
        JOIN card_purchases cp ON i.purchase_id = cp.id
        JOIN cards c ON cp.card_id = c.id
        LEFT JOIN categories cat ON cp.category_id = cat.id
        WHERE i.competence_month = ? ORDER BY c.name ASC, cp.date DESC, cp.id DESC
    ''', (mes,)).fetchall()


def visao_geral(conn, mes):
    """Saldo total, obrigações pendentes (faturas, despesas fixas e "a pagar" até o mês) e o que sobra."""
    saldo = conn.execute("SELECT COALESCE(ROUND(SUM(balance), 2), 0) FROM accounts WHERE is_active = 1").fetchone()[0]
    # Faturas pendentes do mês E de meses anteriores (uma fatura atrasada não some)
    faturas = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM installments WHERE competence_month <= ? AND status = 'PENDENTE'",
        (mes,)).fetchone()[0]
    despesas_fixas = conn.execute('''
        SELECT COALESCE(SUM(amount), 0) FROM fixed_expenses
        WHERE is_active = 1 AND id NOT IN (
            SELECT fixed_expense_id FROM fixed_expense_payments WHERE competence_month = ?)
    ''', (mes,)).fetchone()[0]
    # Parcelas "a pagar" (pessoas) que vencem neste mês ou já venceram
    a_pagar = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM debt_installments WHERE paid_date IS NULL AND substr(due_date, 1, 7) <= ?",
        (mes,)).fetchone()[0]
    obrigacoes = round(faturas + despesas_fixas + a_pagar, 2)
    return {'saldo': saldo, 'faturas': round(faturas, 2), 'despesas_fixas': round(despesas_fixas, 2),
            'a_pagar': round(a_pagar, 2), 'obrigacoes': obrigacoes, 'disponivel': round(saldo - obrigacoes, 2)}


def relatorio_completo(conn, mes, hoje):
    """Tudo do mês para o PDF. hoje é um datetime (saldos e status das faturas são os de hoje)."""
    parcelas = parcelas_do_mes(conn, mes)

    cartoes = []
    for r in resumo_faturas(conn, mes, hoje):
        itens = [p for p in parcelas if p['card_id'] == r['id']]
        card = conn.execute('SELECT * FROM cards WHERE id = ?', (r['id'],)).fetchone()
        em_aberto = conn.execute('''
            SELECT COALESCE(ROUND(SUM(i.amount), 2), 0) FROM installments i
            JOIN card_purchases cp ON i.purchase_id = cp.id WHERE cp.card_id = ? AND i.status = 'PENDENTE'
        ''', (r['id'],)).fetchone()[0]
        cartoes.append({**r, 'bank': card['bank'], 'itens': itens,
                        'total': round(sum(p['amount'] for p in itens), 2),
                        'pendente': round(sum(p['amount'] for p in itens if p['status'] == 'PENDENTE'), 2),
                        'limite': card['limit_total'], 'limite_usado': em_aberto,
                        'limite_livre': round(card['limit_total'] - em_aberto, 2)})

    compras = conn.execute('''
        SELECT cp.*, c.name as cartao, cat.name as categoria,
               COUNT(i.id) as parcelas, MIN(i.competence_month) as primeira_fatura
        FROM card_purchases cp
        JOIN cards c ON cp.card_id = c.id
        LEFT JOIN categories cat ON cp.category_id = cat.id
        LEFT JOIN installments i ON i.purchase_id = cp.id
        WHERE strftime('%Y-%m', cp.date) = ?
        GROUP BY cp.id ORDER BY cp.date ASC, cp.id ASC
    ''', (mes,)).fetchall()

    lancamentos = lancamentos_do_mes(conn, mes)

    gastos_por_categoria = conn.execute(f'''
        SELECT COALESCE(c.name, 'Sem categoria') as categoria, ROUND(SUM(valor), 2) as gasto, b.amount_limit as limite
        FROM (
            SELECT t.category_id, t.amount as valor FROM transactions t
            WHERE t.type = 'despesa' AND {MES_DO_LANCAMENTO} = :mes AND NOT {EH_PAGAMENTO_DE_FATURA}
            UNION ALL
            SELECT cp.category_id, i.amount FROM installments i
            JOIN card_purchases cp ON i.purchase_id = cp.id WHERE i.competence_month = :mes
        ) g
        LEFT JOIN categories c ON c.id = g.category_id
        LEFT JOIN budgets b ON b.category_id = g.category_id
        GROUP BY g.category_id ORDER BY gasto DESC
    ''', {'mes': mes}).fetchall()

    despesas_fixas = conn.execute('''
        SELECT f.description, f.amount, f.due_day, c.name as categoria, p.paid_date, p.amount as valor_pago,
               CASE WHEN p.transaction_id IS NOT NULL THEN 'Conta'
                    WHEN p.purchase_id IS NOT NULL THEN 'Cartão' END as via
        FROM fixed_expenses f
        LEFT JOIN categories c ON f.category_id = c.id
        LEFT JOIN fixed_expense_payments p ON f.id = p.fixed_expense_id AND p.competence_month = ?
        WHERE f.is_active = 1 ORDER BY f.due_day ASC
    ''', (mes,)).fetchall()

    a_pagar = conn.execute('''
        SELECT i.*, d.person, d.description FROM debt_installments i JOIN debts d ON d.id = i.debt_id
        WHERE substr(i.due_date, 1, 7) = ? OR (i.paid_date IS NULL AND substr(i.due_date, 1, 7) < ?)
        ORDER BY i.due_date ASC, d.person
    ''', (mes, mes)).fetchall()
    a_pagar_total_aberto = conn.execute(
        "SELECT COALESCE(ROUND(SUM(amount), 2), 0) FROM debt_installments WHERE paid_date IS NULL").fetchone()[0]

    ano, m = map(int, mes.split('-'))
    meses_futuros = [f"{a}-{mm:02d}" for a, mm in (add_months(ano, m, n) for n in range(1, MESES_A_FRENTE + 1))]
    proximas_faturas = []
    for c in conn.execute("SELECT id, name FROM cards WHERE is_active = 1 ORDER BY name").fetchall():
        valores = [conn.execute('''
            SELECT COALESCE(ROUND(SUM(i.amount), 2), 0) FROM installments i
            JOIN card_purchases cp ON i.purchase_id = cp.id WHERE cp.card_id = ? AND i.competence_month = ?
        ''', (c['id'], fm)).fetchone()[0] for fm in meses_futuros]
        proximas_faturas.append({'cartao': c['name'], 'valores': valores})

    contas = conn.execute(
        "SELECT name, type, balance, balance_date FROM accounts WHERE is_active = 1 ORDER BY balance DESC, name").fetchall()

    return {
        'mes': mes, 'hoje': hoje,
        'resumo': resumo_do_mes(conn, mes),
        'visao_geral': visao_geral(conn, mes),
        'contas': contas,
        'cartoes': cartoes,
        'compras': compras,
        'receitas': [l for l in lancamentos if l['type'] == 'receita' and not l['pagamento_fatura']],
        'despesas': [l for l in lancamentos if l['type'] == 'despesa' and not l['pagamento_fatura']],
        'pagamentos_fatura': [l for l in lancamentos if l['pagamento_fatura']],
        'gastos_por_categoria': gastos_por_categoria,
        'despesas_fixas': despesas_fixas,
        'a_pagar': a_pagar,
        'a_pagar_total_aberto': a_pagar_total_aberto,
        'meses_futuros': meses_futuros,
        'proximas_faturas': proximas_faturas,
    }
