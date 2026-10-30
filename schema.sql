-- =============================================================
-- schema.sql — AnaFins
-- Fonte da verdade do banco: db.py executa este arquivo ao iniciar.
-- Tudo é IF NOT EXISTS, então rodar de novo nunca apaga dados.
-- Mudanças em tabelas que já existem vão em db.py (_migrar).
-- =============================================================

-- Contas (onde o dinheiro realmente está)
CREATE TABLE IF NOT EXISTS accounts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    type          TEXT    NOT NULL,
    balance       REAL    NOT NULL,
    balance_date  TEXT    NOT NULL,
    is_active     INTEGER DEFAULT 1
);

-- Cartões de crédito
CREATE TABLE IF NOT EXISTS cards (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT    NOT NULL,
    bank         TEXT    NOT NULL,
    limit_total  REAL    NOT NULL,
    closing_day  INTEGER NOT NULL,
    due_day      INTEGER NOT NULL,
    is_active    INTEGER DEFAULT 1
);

-- Categorias
CREATE TABLE IF NOT EXISTS categories (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name   TEXT    NOT NULL,
    type   TEXT    NOT NULL
);

-- Lançamentos (receitas/despesas em contas)
CREATE TABLE IF NOT EXISTS transactions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    type         TEXT    NOT NULL,
    description  TEXT    NOT NULL,
    amount       REAL    NOT NULL,
    date         TEXT    NOT NULL,
    account_id   INTEGER,
    category_id  INTEGER,
    reference_month TEXT,  -- mês do relatório (ex: salário de 25/09 conta em outubro); ver services/contas.py
    FOREIGN KEY (account_id)  REFERENCES accounts(id),
    FOREIGN KEY (category_id) REFERENCES categories(id)
);

-- Compras no cartão (compra original)
CREATE TABLE IF NOT EXISTS card_purchases (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id       INTEGER NOT NULL,
    description   TEXT    NOT NULL,
    total_amount  REAL    NOT NULL,
    date          TEXT    NOT NULL,
    category_id   INTEGER,
    FOREIGN KEY (card_id)     REFERENCES cards(id),
    FOREIGN KEY (category_id) REFERENCES categories(id)
);

-- Parcelas (cada uma cai na fatura de um mês; competence_month = mês de VENCIMENTO)
CREATE TABLE IF NOT EXISTS installments (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_id         INTEGER NOT NULL,
    amount              REAL    NOT NULL,
    installment_number  INTEGER NOT NULL,
    total_installments  INTEGER NOT NULL,
    competence_month    TEXT,
    status              TEXT    DEFAULT 'PENDENTE',
    invoice_payment_id  INTEGER,  -- pagamento de fatura (card_invoices_history) que quitou a parcela
    FOREIGN KEY (purchase_id) REFERENCES card_purchases(id)
);

-- Despesas fixas (recorrentes). is_paid/paid_date são legados: o pagamento por mês fica em fixed_expense_payments
CREATE TABLE IF NOT EXISTS fixed_expenses (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    description  TEXT    NOT NULL,
    amount       REAL    NOT NULL,
    due_day      INTEGER NOT NULL,
    category_id  INTEGER,
    is_paid      INTEGER DEFAULT 0,
    paid_date    TEXT,
    is_active    INTEGER DEFAULT 1,
    FOREIGN KEY (category_id) REFERENCES categories(id)
);

-- Pagamento de cada despesa fixa em cada mês, ligado ao lançamento (conta) ou compra (cartão) que gerou
CREATE TABLE IF NOT EXISTS fixed_expense_payments (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    fixed_expense_id  INTEGER NOT NULL,
    competence_month  TEXT    NOT NULL,
    paid_date         TEXT    NOT NULL,
    amount            REAL    NOT NULL,
    transaction_id    INTEGER,
    purchase_id       INTEGER,
    FOREIGN KEY (fixed_expense_id) REFERENCES fixed_expenses(id)
);

-- Histórico de faturas já pagas
CREATE TABLE IF NOT EXISTS card_invoices_history (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id           INTEGER NOT NULL,
    competence_month  TEXT    NOT NULL,
    total_amount      REAL    NOT NULL,
    paid_date         TEXT    NOT NULL,
    account_id        INTEGER,
    transaction_id    INTEGER,  -- lançamento que debitou a conta (para o "Desfazer"); vazio em pagamentos antigos
    FOREIGN KEY (card_id)    REFERENCES cards(id),
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

-- Orçamentos por categoria
CREATE TABLE IF NOT EXISTS budgets (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id   INTEGER UNIQUE,
    amount_limit  REAL    NOT NULL,
    FOREIGN KEY (category_id) REFERENCES categories(id)
);

-- Chaves Pix (dados do Registrato / Banco Central)
CREATE TABLE IF NOT EXISTS pix_keys (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    key             TEXT    NOT NULL,
    key_type        TEXT    NOT NULL,
    institution     TEXT    NOT NULL,
    account_type    TEXT,
    agency          TEXT,
    account_number  TEXT,
    created_at      TEXT,
    status          TEXT    DEFAULT 'Ativa'
);

-- A pagar: dívidas com pessoas (ex: empréstimo do irmão em 3x)
CREATE TABLE IF NOT EXISTS debts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    person        TEXT    NOT NULL,
    description   TEXT,
    total_amount  REAL    NOT NULL,
    category_id   INTEGER,
    created_at    TEXT    NOT NULL,
    FOREIGN KEY (category_id) REFERENCES categories(id)
);

-- Parcelas de cada dívida; paid_date preenchido = paga (ligada ao lançamento ou compra que pagou)
CREATE TABLE IF NOT EXISTS debt_installments (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    debt_id             INTEGER NOT NULL,
    installment_number  INTEGER NOT NULL,
    total_installments  INTEGER NOT NULL,
    amount              REAL    NOT NULL,
    due_date            TEXT    NOT NULL,
    paid_date           TEXT,
    transaction_id      INTEGER,
    purchase_id         INTEGER,
    FOREIGN KEY (debt_id) REFERENCES debts(id)
);

-- Configurações do app (PIN do celular, chave de sessão, ...)
CREATE TABLE IF NOT EXISTS settings (
    key    TEXT PRIMARY KEY,
    value  TEXT
);
