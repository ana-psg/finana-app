# =============================================================
# app.py - AnaFins
# Monta o app Flask: banco, filtros do Jinja e rotas.
#
# Organização:
#   db.py        conexão SQLite, schema e migrações
#   utils.py     dinheiro, meses e leitura de formulários
#   services/    regras de negócio (contas, cartões/faturas, despesas fixas)
#   routes/      uma tela por arquivo (Blueprints)
#   templates/   HTML
# =============================================================

from datetime import timedelta

from flask import Flask

from finana.db import conectar, init_db
from finana.routes import registrar_rotas
from finana.services.config import chave_secreta
from finana.utils import register_jinja_filters


def create_app():
    app = Flask(__name__)
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    init_db()
    with conectar() as conn:
        app.secret_key = chave_secreta(conn)  # sessões (login do celular) e avisos na tela
    app.config.update(
        SESSION_COOKIE_NAME='anafins_session',  # cookies valem para o endereço em qualquer porta
        SESSION_COOKIE_SAMESITE='Lax',  # outro site não consegue enviar formulários em seu nome
        SESSION_COOKIE_HTTPONLY=True,
        PERMANENT_SESSION_LIFETIME=timedelta(days=90),  # o celular fica logado por 90 dias
    )
    register_jinja_filters(app)
    registrar_rotas(app)

    @app.errorhandler(OverflowError)
    def numero_grande_demais(_e):
        return 'Número fora do intervalo aceito.', 400

    return app


app = create_app()


if __name__ == '__main__':
    # 0.0.0.0 = aceita o celular no Wi-Fi de casa (fora do computador, pede o PIN)
    app.run(host='0.0.0.0', port=8000)
