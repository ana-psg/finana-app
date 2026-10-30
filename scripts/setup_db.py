"""
setup_db.py - AnaFins

Recria/verifica o banco de dados chamando o init_db() do db.py.
A fonte da verdade do schema é SEMPRE o schema.sql (aplicado pelo init_db() do db.py) — este script só
existe pra você poder rodar 'python scripts/setup_db.py' manualmente.

Uso:
    python scripts/setup_db.py          -> só garante que o banco existe (não apaga nada)
    python scripts/setup_db.py --reset  -> APAGA o .db e recria do zero (pede confirmação)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # pasta do app

from db import DB_FILE, init_db  # noqa: E402


def reset_database():
    if os.path.exists(DB_FILE):
        resposta = input(f"AVISO: Isso vai APAGAR '{DB_FILE}' e recriar do zero. Continuar? (s/N): ").strip().lower()
        if resposta != 's':
            print("Cancelado. Nada foi apagado.")
            return
        os.remove(DB_FILE)
        print(f"'{DB_FILE}' removido.")

    init_db()
    print(f"Banco '{DB_FILE}' criado com sucesso.")


def ensure_database():
    init_db()
    print(f"Banco '{DB_FILE}' verificado/criado. Nada foi apagado.")


if __name__ == '__main__':
    if '--reset' in sys.argv:
        reset_database()
    else:
        ensure_database()