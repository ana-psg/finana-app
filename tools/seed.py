"""
seed.py - AnaFins

Insere dados de teste no banco (contas, categorias, lançamentos, cartão).
Compatível com o schema do init_db() do db.py.

Segurança:
  - Se o banco já tem contas, NÃO insere nada (evita duplicar).
  - Se o banco não existe, cria chamando init_db() do db.py.
"""

import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # pasta do app

from finana.db import DB_FILE, init_db


def seed_database():
    if not os.path.exists(DB_FILE):
        print(f"'{DB_FILE}' nao existe. Rodando init_db() primeiro...")
        init_db()

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM accounts')
    if cursor.fetchone()[0] > 0:
        print('Banco ja tem dados. Pulando seed pra nao duplicar.')
        print('   Se quiser forcar, rode: python tools/setup_db.py --reset')
        conn.close()
        return

    print('A inserir dados de teste no banco de dados...')

    # 1. Categorias (com type)
    categorias = [
        ('Receitas', 'receita'),
        ('Moradia', 'despesa'),
        ('Transporte', 'despesa'),
        ('Pets', 'despesa'),
        ('Alimentacao', 'despesa'),
        ('Lazer', 'despesa'),
    ]
    # init_db() já cria categorias iniciais: só insere as que faltam, sem duplicar
    existentes = {nome for (nome,) in cursor.execute('SELECT name FROM categories')}
    cursor.executemany(
        'INSERT INTO categories (name, type) VALUES (?, ?)', [c for c in categorias if c[0] not in existentes]
    )

    cursor.execute('SELECT id, name FROM categories')
    cat_map = {name: cid for cid, name in cursor.fetchall()}

    # 2. Contas
    contas = [
        ('Conta Exemplo', 'corrente', 1000.00, '2026-09-25'),
        ('Poupança Exemplo', 'corrente', 500.00, '2026-09-25'),
    ]
    cursor.executemany('INSERT INTO accounts (name, type, balance, balance_date) VALUES (?, ?, ?, ?)', contas)
    cursor.execute('SELECT id, name FROM accounts')
    acc_map = {name: aid for aid, name in cursor.fetchall()}

    # 3. Lançamentos
    lancamentos = [
        ('receita', 'Salário de exemplo', 2000.00, '2026-09-05', cat_map['Receitas'], acc_map['Conta Exemplo']),
        ('despesa', 'Passagem de ônibus', 50.00, '2026-09-10', cat_map['Transporte'], acc_map['Conta Exemplo']),
        ('despesa', 'Ração', 100.00, '2026-09-15', cat_map['Pets'], acc_map['Conta Exemplo']),
    ]
    cursor.executemany(
        """
        INSERT INTO transactions (type, description, amount, date, category_id, account_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """,
        lancamentos,
    )

    # 4. Cartão
    cursor.execute(
        """
        INSERT INTO cards (name, bank, limit_total, closing_day, due_day)
        VALUES (?, ?, ?, ?, ?)
    """,
        ('Cartão Exemplo', 'Banco Exemplo', 1000.00, 3, 10),
    )

    conn.commit()
    conn.close()
    print('Dados inseridos com sucesso! Abra o AnaFins.bat.')


if __name__ == '__main__':
    seed_database()
