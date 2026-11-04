"""Bugs encontrados na revisão de 04/11/2026: cada teste aqui falhava antes da correção."""

import pytest

from finana.db import conectar
from finana.services import cartoes, config
from finana.services.contas import registrar_lancamento
from finana.utils import ErroNegocio, agora

from .test_etapa1 import c, um  # noqa: F401  (fixture e helper)

CELULAR = {'Host': 'pc.exemplo.ts.net'}


def _desativar_conta_e_cartao():
    with conectar() as conn:
        conn.execute('UPDATE accounts SET is_active = 0 WHERE id = 1')
        conn.execute('UPDATE cards SET is_active = 0 WHERE id = 1')


def test_conta_removida_nao_recebe_lancamento_novo(c):  # noqa: F811
    _desativar_conta_e_cartao()
    with conectar() as conn, pytest.raises(ErroNegocio):
        registrar_lancamento(conn, 'despesa', 'x', 10, '2026-10-01', 1, None)
    assert um('SELECT balance FROM accounts WHERE id = 1') == 1000


def test_cartao_removido_nao_recebe_compra_nova(c):  # noqa: F811
    _desativar_conta_e_cartao()
    with conectar() as conn, pytest.raises(ErroNegocio):
        cartoes.registrar_compra(conn, 1, 'x', 10, agora(), None)


def test_cartao_com_parcela_pendente_nao_pode_ser_removido(c):  # noqa: F811
    with conectar() as conn:
        cartoes.registrar_compra(conn, 1, 'TV', 300, agora(), None, 3)
    r = c.post('/apagar_cartao/1', follow_redirects=True)
    assert 'pendente' in r.get_data(as_text=True)
    assert um('SELECT is_active FROM cards WHERE id = 1') == 1


def test_cartao_sem_pendencia_pode_ser_removido(c):  # noqa: F811
    c.post('/apagar_cartao/1')
    assert um('SELECT is_active FROM cards WHERE id = 1') == 0


@pytest.mark.parametrize(
    ('rota', 'dados', 'sql', 'esperado'),
    [
        (
            '/contas',
            {'name': 'X', 'type': '<script>', 'balance': '0'},
            "SELECT type FROM accounts WHERE name = 'X'",
            'outro',
        ),
        ('/categorias', {'name': 'X', 'type': 'qualquer'}, "SELECT type FROM categories WHERE name = 'X'", 'despesa'),
    ],
)
def test_tipo_desconhecido_vira_o_padrao(c, rota, dados, sql, esperado):  # noqa: F811
    c.post(rota, data=dados)
    assert um(sql) == esperado


def test_trocar_o_pin_desconecta_o_celular(c):  # noqa: F811
    with conectar() as conn:
        config.definir_pin(conn, '1234', '1234')
    r = c.post('/entrar?proximo=/contas', data={'pin': '1234'}, headers=CELULAR)
    assert r.status_code == 302
    assert c.get('/contas', headers=CELULAR).status_code == 200

    with conectar() as conn:
        config.definir_pin(conn, '9876', '9876')
    r = c.get('/contas', headers=CELULAR)
    assert r.status_code == 302
    assert '/entrar' in r.headers['Location']
