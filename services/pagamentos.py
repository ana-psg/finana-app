# =============================================================
# services/pagamentos.py - pagar algo por conta ou cartão (e desfazer)
# Usado por despesas fixas e pela aba "A pagar".
# =============================================================

from services.cartoes import excluir_compra, registrar_compra
from services.contas import excluir_lancamento, registrar_lancamento
from utils import ErroNegocio


def pagar_via(conn, descricao, valor, data_pagamento, via, conta_id=None, cartao_id=None, categoria_id=None,
              mes_referencia=None):
    """Debita a conta (via='conta') ou lança no cartão (via='cartao').
    data_pagamento é um datetime; mes_referencia é o mês em que o pagamento conta no relatório.
    Retorna (transaction_id, purchase_id): um dos dois é None."""
    if via == 'conta':
        if not conta_id:
            raise ErroNegocio('Escolha a conta usada no pagamento.')
        return registrar_lancamento(conn, 'despesa', descricao, valor, data_pagamento.strftime('%Y-%m-%d'),
                                    conta_id, categoria_id, mes_referencia), None
    if via == 'cartao':
        if not cartao_id:
            raise ErroNegocio('Escolha o cartão usado no pagamento.')
        return None, registrar_compra(conn, cartao_id, descricao, valor, data_pagamento, categoria_id)
    raise ErroNegocio('Escolha se o pagamento foi por conta ou cartão.')


def desfazer(conn, transaction_id, purchase_id):
    """Devolve o dinheiro à conta ou tira a compra do cartão.
    Retorna False se a compra já estava numa fatura paga (aí ela fica onde está)."""
    if transaction_id:
        excluir_lancamento(conn, transaction_id)
    if purchase_id:
        return excluir_compra(conn, purchase_id)
    return True
