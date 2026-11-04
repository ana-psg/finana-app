# Uma rota (Blueprint) por área do app. Para criar uma área nova:
# 1) crie routes/<area>.py com um Blueprint chamado bp
# 2) adicione o módulo em MODULOS abaixo e no menu de templates/base.html

from importlib import import_module

MODULOS = [
    'acesso',
    'rapido',
    'dashboard',
    'contas',
    'pix',
    'categorias',
    'cartoes',
    'faturas',
    'lancamentos',
    'relatorio_mensal',
    'orcamento',
    'despesas_fixas',
    'a_pagar',
    'investimentos',
]


def registrar_rotas(app):
    for nome in MODULOS:
        app.register_blueprint(import_module(f'finana.routes.{nome}').bp)
