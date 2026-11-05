# =============================================================
# db.py - AnaFins
# Conexão com o SQLite, criação do schema e migrações.
# =============================================================

import os
import sqlite3
import sys
from contextlib import contextmanager

PASTA = os.path.dirname(os.path.abspath(__file__))  # pacote finana/ (no .exe, dentro do pacote)
RAIZ = os.path.dirname(PASTA)  # pasta do projeto
NOME_APP = 'AnaFins'
INSTALADO = bool(getattr(sys, 'frozen', False))


def pasta_dados(instalado, environ, raiz):
    """Programa instalado: %APPDATA%\\AnaFins. Rodando pelo código: a pasta do projeto."""
    if not instalado:
        return raiz
    return os.path.join(environ.get('APPDATA') or os.path.expanduser('~'), NOME_APP)


PASTA_DADOS = pasta_dados(INSTALADO, os.environ, RAIZ)
# Caminho absoluto. ANAFINS_DB permite usar outro banco (testes).
DB_FILE = os.environ.get('ANAFINS_DB') or os.path.join(PASTA_DADOS, 'financas_local.db')
SCHEMA_FILE = os.path.join(PASTA, 'schema.sql')
os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)

CATEGORIAS_INICIAIS = [
    ('Alimentação', 'despesa'),
    ('Transporte', 'despesa'),
    ('Moradia', 'despesa'),
    ('Lazer', 'despesa'),
    ('Pets', 'despesa'),
    ('Saúde', 'despesa'),
    ('Outros', 'despesa'),
    ('Entretenimento', 'despesa'),
    ('Receitas', 'receita'),
]


@contextmanager
def conectar():
    """Abre uma conexão; faz commit se tudo deu certo, rollback se deu erro, e sempre fecha.

    with conectar() as conn:
        conn.execute(...)
    """
    conn = sqlite3.connect(DB_FILE, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        # Reserva a escrita já no começo: dois pedidos ao mesmo tempo (duplo clique, PC e celular)
        # não podem ler o mesmo estado e pagar a mesma conta duas vezes.
        conn.execute('BEGIN IMMEDIATE')
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Cria as tabelas que faltarem, aplica migrações e insere as categorias iniciais."""
    conn = sqlite3.connect(DB_FILE)
    try:
        with open(SCHEMA_FILE, encoding='utf-8') as f:
            conn.executescript(f.read())
        with conn:
            _migrar(conn)
            if conn.execute('SELECT COUNT(*) FROM categories').fetchone()[0] == 0:
                conn.executemany('INSERT INTO categories (name, type) VALUES (?, ?)', CATEGORIAS_INICIAIS)
    finally:
        conn.close()


def _colunas(conn, tabela):
    if not tabela.isidentifier():
        raise ValueError(f'nome de tabela inválido: {tabela!r}')
    return [r[1] for r in conn.execute(f'PRAGMA table_info({tabela})')]


def _migrar(conn):
    """Ajustes em bancos criados por versões antigas do app (em ordem de versão)."""
    # v1.1: pagamento de despesa fixa ligado ao lançamento/compra que gerou (para o "Desfazer" reverter o dinheiro)
    if 'transaction_id' not in _colunas(conn, 'fixed_expense_payments'):
        conn.execute('ALTER TABLE fixed_expense_payments ADD COLUMN transaction_id INTEGER')
        conn.execute('ALTER TABLE fixed_expense_payments ADD COLUMN purchase_id INTEGER')
        pagamentos = conn.execute("""
            SELECT p.id, p.competence_month, p.paid_date, f.description
            FROM fixed_expense_payments p JOIN fixed_expenses f ON f.id = p.fixed_expense_id
        """).fetchall()
        for pid, mes, data_pag, desc in pagamentos:
            tx = conn.execute(
                'SELECT id FROM transactions WHERE description = ? AND date = ? ORDER BY id DESC LIMIT 1',
                (f'{desc} (Mês: {mes})', data_pag),
            ).fetchone()
            cp = conn.execute(
                'SELECT id FROM card_purchases WHERE description = ? AND date = ? ORDER BY id DESC LIMIT 1',
                (f'Despesa Fixa: {desc} (Mês: {mes})', data_pag),
            ).fetchone()
            conn.execute(
                'UPDATE fixed_expense_payments SET transaction_id = ?, purchase_id = ? WHERE id = ?',
                (tx[0] if tx else None, cp[0] if cp else None, pid),
            )

    # v1.2: mês de referência dos lançamentos (o relatório usa ele, não a data)
    if 'reference_month' not in _colunas(conn, 'transactions'):
        conn.execute('ALTER TABLE transactions ADD COLUMN reference_month TEXT')
        _preencher_mes_referencia(conn)

    # v1.3: pagamento de fatura vira lançamento e pode ser desfeito (colunas novas ficam vazias nos registros antigos)
    if 'transaction_id' not in _colunas(conn, 'card_invoices_history'):
        conn.execute('ALTER TABLE card_invoices_history ADD COLUMN transaction_id INTEGER')
    if 'invoice_payment_id' not in _colunas(conn, 'installments'):
        conn.execute('ALTER TABLE installments ADD COLUMN invoice_payment_id INTEGER')


def _preencher_mes_referencia(conn):
    """Aplica as regras de services/contas.py aos lançamentos que já existiam."""
    from finana.services.contas import DIA_VIRADA_RECEITA

    # padrão: mês da data; receitas a partir do dia de virada (salário) contam no mês seguinte
    conn.execute(f"""
        UPDATE transactions SET reference_month = CASE
            WHEN type = 'receita' AND CAST(strftime('%d', date) AS INTEGER) >= {DIA_VIRADA_RECEITA}
                THEN strftime('%Y-%m', date, 'start of month', '+1 month')
            ELSE strftime('%Y-%m', date) END
    """)
    # pagamento de despesa fixa conta no mês da despesa
    conn.execute("""
        UPDATE transactions SET reference_month = (
            SELECT p.competence_month FROM fixed_expense_payments p WHERE p.transaction_id = transactions.id)
        WHERE id IN (SELECT transaction_id FROM fixed_expense_payments WHERE transaction_id IS NOT NULL)
    """)
    # parcela "a pagar" conta no mês do vencimento
    conn.execute("""
        UPDATE transactions SET reference_month = (
            SELECT substr(i.due_date, 1, 7) FROM debt_installments i WHERE i.transaction_id = transactions.id)
        WHERE id IN (SELECT transaction_id FROM debt_installments WHERE transaction_id IS NOT NULL)
    """)
