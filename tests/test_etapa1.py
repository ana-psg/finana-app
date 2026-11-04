"""Bugs corrigidos na refatoração v2: cada teste aqui falhava antes da correção."""

import os
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from finana.app import app
from finana.db import conectar, init_db
from finana.services import a_pagar, cartoes, despesas_fixas
from finana.utils import ErroNegocio, agora, data_valida, mes_valido, parse_money

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = {'Origin': 'https://site-malicioso.example', 'Sec-Fetch-Site': 'cross-site'}


@pytest.fixture
def c():
    with conectar() as conn:
        for (t,) in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall():
            conn.execute(f'DELETE FROM {t}')
    init_db()
    with conectar() as conn:
        conn.execute(
            "INSERT INTO accounts (id, name, type, balance, balance_date) VALUES (1, 'Conta', 'corrente', 1000, '2026-01-01')"
        )
        conn.execute(
            "INSERT INTO cards (id, name, bank, limit_total, closing_day, due_day) VALUES (1, 'Cartão', 'B', 5000, 26, 2)"
        )
        conn.execute("INSERT INTO pix_keys (id, key, key_type, institution) VALUES (1, 'k', 'email', 'i')")
    app.config['PROPAGATE_EXCEPTIONS'] = False
    return app.test_client()


def um(sql, *args):
    with conectar() as conn:
        return conn.execute(sql, args).fetchone()[0]


# ---------- dinheiro ----------
@pytest.mark.parametrize(
    ('texto', 'esperado'),
    [
        ('1.500', 1500.0),
        ('1.234', 1234.0),
        ('12.000', 12000.0),
        ('1.234.567', 1234567.0),  # ponto de milhar
        ('1.234,56', 1234.56),
        ('1234,56', 1234.56),
        ('1,5', 1.5),
        ('10,50', 10.5),
        ('1,234.56', 1234.56),
        ('1234.56', 1234.56),
        ('1.5', 1.5),
        ('R$ 1.500,00', 1500.0),
        ('-5', -5.0),
        ('-1.500,25', -1500.25),
    ],
)
def test_valores_validos(texto, esperado):
    assert parse_money(texto) == esperado


@pytest.mark.parametrize(
    'texto',
    [
        'nan',
        'inf',
        '-inf',
        'Infinity',
        '1e5',
        '1e400',
        'abc',
        '1,234',
        '1.2345',
        '1,2,3',
        '1.23.45',
        '9' * 40,
        '1.234,5,6',
    ],
)
def test_valores_invalidos_viram_zero(texto):
    assert parse_money(texto) == 0.0


def test_saldo_invalido_e_recusado_e_nao_cria_conta(c):
    r = c.post(
        '/contas',
        data={'name': 'Nova', 'type': 'corrente', 'balance': 'abc', 'date': '2026-10-01'},
        follow_redirects=True,
    )
    assert 'Saldo' in r.get_data(as_text=True)
    assert um("SELECT COUNT(*) FROM accounts WHERE name = 'Nova'") == 0


def test_saldo_zero_continua_valendo(c):
    c.post('/contas', data={'name': 'Nova', 'type': 'corrente', 'balance': '0,00', 'date': '2026-10-01'})
    assert um("SELECT balance FROM accounts WHERE name = 'Nova'") == 0


def test_valor_infinito_nao_estraga_o_saldo(c):
    c.post(
        '/lancamentos',
        data={'type': 'despesa', 'description': 'x', 'amount': 'inf', 'date': '2026-10-01', 'account_id': 1},
    )
    assert um('SELECT balance FROM accounts WHERE id = 1') == 1000
    assert um('SELECT COUNT(*) FROM transactions') == 0


@pytest.mark.parametrize(
    ('rota', 'dados'),
    [
        ('/cartoes', {'name': 'x', 'bank': 'b', 'limit_total': 'abc', 'closing_day': '1', 'due_day': '2'}),
        ('/orcamento', {'category_id': '1', 'amount_limit': 'abc'}),
        ('/orcamento', {'category_id': '1', 'amount_limit': '0'}),
    ],
)
def test_limite_invalido_e_recusado(c, rota, dados):
    antes = um('SELECT COUNT(*) FROM cards') + um('SELECT COUNT(*) FROM budgets')
    assert c.post(rota, data=dados).status_code == 302
    assert um('SELECT COUNT(*) FROM cards') + um('SELECT COUNT(*) FROM budgets') == antes


# ---------- textos obrigatórios ----------
@pytest.mark.parametrize(
    ('rota', 'dados', 'tabela'),
    [
        ('/contas', {'name': '  ', 'type': 'corrente', 'balance': '1', 'date': '2026-10-01'}, 'accounts'),
        ('/cartoes', {'name': ' ', 'bank': 'b', 'limit_total': '1', 'closing_day': '1', 'due_day': '2'}, 'cards'),
        ('/categorias', {'name': ' ', 'type': 'despesa'}, 'categories'),
        (
            '/lancamentos',
            {'type': 'despesa', 'description': ' ', 'amount': '1', 'date': '2026-10-01', 'account_id': 1},
            'transactions',
        ),
        (
            '/faturas',
            {'description': ' ', 'total_amount': '1', 'date': '2026-10-01', 'card_id': 1, 'installments': '1'},
            'card_purchases',
        ),
        ('/despesas_fixas', {'description': ' ', 'amount': '1', 'due_day': '1'}, 'fixed_expenses'),
        ('/pix', {'key': ' ', 'key_type': 'email', 'institution': 'i'}, 'pix_keys'),
    ],
)
def test_nome_vazio_e_recusado(c, rota, dados, tabela):
    antes = um(f'SELECT COUNT(*) FROM {tabela}')
    assert c.post(rota, data=dados).status_code == 302
    assert um(f'SELECT COUNT(*) FROM {tabela}') == antes


def test_campo_faltando_nao_da_erro(c):
    assert c.post('/contas', data={}).status_code == 302


# ---------- categoria ----------
@pytest.mark.parametrize('valor', ['', '9999', 'abc'])
def test_categoria_vazia_ou_inexistente_vira_sem_categoria(c, valor):
    c.post(
        '/lancamentos',
        data={
            'type': 'despesa',
            'description': 'x',
            'amount': '1',
            'date': '2026-10-01',
            'account_id': 1,
            'category_id': valor,
        },
    )
    c.post(
        '/faturas',
        data={
            'description': 'x',
            'total_amount': '1',
            'date': '2026-10-01',
            'card_id': 1,
            'category_id': valor,
            'installments': '1',
        },
    )
    c.post('/despesas_fixas', data={'description': 'x', 'amount': '1', 'due_day': '1', 'category_id': valor})
    for tabela in ('transactions', 'card_purchases', 'fixed_expenses'):
        assert um(f'SELECT COUNT(*) FROM {tabela} WHERE category_id IS NOT NULL') == 0


def test_orcamento_precisa_de_categoria_de_verdade(c):
    for valor in ('', '9999'):
        c.post('/orcamento', data={'category_id': valor, 'amount_limit': '10'})
    assert um('SELECT COUNT(*) FROM budgets') == 0


# ---------- datas ----------
@pytest.mark.parametrize('mes', ['0000-05', '1999-12', '2101-01', '9999-12'])
def test_mes_absurdo_usa_o_padrao(c, mes):
    assert mes_valido(mes, 'padrao') == 'padrao'
    assert c.get(f'/faturas?mes={mes}').status_code == 200
    assert c.get(f'/relatorio_mensal/pdf?mes={mes}').status_code == 200


@pytest.mark.parametrize('data', ['0001-01-01', '9999-12-31', '2026-02-30', 'abc', '', None])
def test_data_absurda_e_invalida(data):
    assert data_valida(data) is None


def test_data_absurda_nao_entra(c):
    c.post(
        '/faturas',
        data={'description': 'x', 'total_amount': '1', 'date': '9999-12-31', 'card_id': 1, 'installments': '99'},
    )
    assert um('SELECT COUNT(*) FROM card_purchases') == 0


def test_hora_e_sempre_a_de_sao_paulo():
    sp = datetime.now(timezone(timedelta(hours=-3))).replace(tzinfo=None)
    assert abs((agora() - sp).total_seconds()) < 60


def test_pagamento_de_fatura_usa_a_data_de_sao_paulo(c):
    """Às 23h em São Paulo, um PC em outro fuso já está no dia seguinte."""
    with conectar() as conn:
        cartoes.registrar_compra(conn, 1, 'x', 100, datetime(2026, 10, 1), None)
        mes = conn.execute('SELECT competence_month FROM installments').fetchone()[0]
    with mock.patch('finana.services.cartoes.agora', return_value=datetime(2026, 10, 30, 23, 0)), conectar() as conn:
        cartoes.pagar_fatura(conn, 1, 1, mes)
    assert um('SELECT date FROM transactions') == '2026-10-30'
    assert um('SELECT paid_date FROM card_invoices_history').startswith('2026-10-30')


def test_divida_usa_a_data_de_sao_paulo(c):
    with mock.patch('finana.services.a_pagar.agora', return_value=datetime(2026, 10, 30, 23, 0)), conectar() as conn:
        a_pagar.criar(conn, 'P', '', 10, 'total', 1, datetime(2026, 11, 1))
    assert um('SELECT created_at FROM debts') == '2026-10-30'


# ---------- dois pedidos ao mesmo tempo (duplo clique, PC e celular) ----------
def _ao_mesmo_tempo(funcao):
    erros = []

    def rodar():
        try:
            with conectar() as conn:
                funcao(conn)
        except ErroNegocio as e:
            erros.append(e)

    threads = [threading.Thread(target=rodar) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return erros


def test_pagar_a_mesma_fatura_duas_vezes_nao_debita_duas_vezes(c):
    with conectar() as conn:
        cartoes.registrar_compra(conn, 1, 'x', 100, datetime(2026, 10, 1), None)
        mes = conn.execute('SELECT competence_month FROM installments').fetchone()[0]
    total = cartoes._total

    def lento(*a, **k):
        v = total(*a, **k)
        time.sleep(0.3)
        return v

    with mock.patch.object(cartoes, '_total', lento):
        _ao_mesmo_tempo(lambda conn: cartoes.pagar_fatura(conn, 1, 1, mes))
    assert um('SELECT balance FROM accounts WHERE id = 1') == 900
    assert um('SELECT COUNT(*) FROM transactions') == 1


def test_pagar_a_mesma_despesa_duas_vezes_nao_debita_duas_vezes(c):
    with conectar() as conn:
        conn.execute("INSERT INTO fixed_expenses (id, description, amount, due_day) VALUES (1, 'Luz', 50, 5)")
    original = despesas_fixas.pagamento_do_mes

    def lento(*a, **k):
        v = original(*a, **k)
        time.sleep(0.3)
        return v

    with mock.patch.object(despesas_fixas, 'pagamento_do_mes', lento):
        erros = _ao_mesmo_tempo(
            lambda conn: despesas_fixas.pagar(conn, 1, '2026-10', datetime(2026, 10, 1), 'conta', 1)
        )
    assert um('SELECT balance FROM accounts WHERE id = 1') == 950
    assert um('SELECT COUNT(*) FROM fixed_expense_payments') == 1
    assert len(erros) == 1


# ---------- segurança ----------
def test_outro_site_nao_consegue_apagar_nada(c):
    assert c.post('/apagar_pix/1', headers=SITE).status_code == 403
    assert um('SELECT COUNT(*) FROM pix_keys') == 1


def test_origem_de_outro_site_sem_cabecalho_fetch_tambem_e_bloqueada(c):
    assert c.post('/apagar_pix/1', headers={'Origin': 'https://site-malicioso.example'}).status_code == 403


def test_endereco_de_outro_site_e_bloqueado(c):
    assert c.get('/', headers={'Host': 'site-malicioso.example'}).status_code == 403


def test_o_proprio_app_continua_funcionando(c):
    r = c.post(
        '/apagar_pix/1',
        headers={'Host': '127.0.0.1:8000', 'Origin': 'http://127.0.0.1:8000', 'Sec-Fetch-Site': 'same-origin'},
    )
    assert r.status_code == 302
    assert um('SELECT COUNT(*) FROM pix_keys') == 0


@pytest.mark.parametrize(
    'cabecalhos',
    [
        {'Host': 'pc.exemplo.ts.net'},
        {'Tailscale-User-Login': 'a@b.c'},
        {'X-Forwarded-For': '100.1.2.3'},
        {'X-Forwarded-Host': 'pc.exemplo.ts.net'},
    ],
)
def test_pedido_pelo_tailscale_pede_pin_mesmo_vindo_de_127(c, cabecalhos):
    r = c.get('/contas', headers=cabecalhos)
    assert r.status_code == 302
    assert '/entrar' in r.headers['Location']


def test_pedido_pelo_tailscale_nao_abre_a_tela_de_pin_do_computador(c):
    assert c.get('/celular', headers={'Host': 'pc.exemplo.ts.net'}).status_code in (302, 403)


def test_cookie_de_sessao_tem_nome_proprio_do_app():
    # O cookie vale para o endereço inteiro, em qualquer porta: com o nome padrão, um app derruba o login do outro
    assert app.config['SESSION_COOKIE_NAME'] == 'anafins_session'


# ---------- erros ----------
def test_numero_gigante_na_rota_nao_da_erro_500(c):
    assert c.post('/apagar_lancamento/' + '9' * 30).status_code == 400


# ---------- funciona sem internet ----------
def test_telas_nao_dependem_de_internet():
    for nome in os.listdir(os.path.join(ROOT, 'finana', 'templates')):
        with open(os.path.join(ROOT, 'finana', 'templates', nome), encoding='utf-8') as f:
            texto = f.read()
        assert not re.search(r'<(script|link)[^>]+(src|href)="https?://', texto), nome


def test_estilos_locais_existem_e_tem_as_classes_usadas():
    with open(os.path.join(ROOT, 'finana', 'static', 'tailwind.css'), encoding='utf-8') as f:
        css = f.read()
    for classe in ('-translate-x-full', 'bg-marca', 'bg-cartao', 'lg\\:hidden'):
        assert classe in css


def test_tela_do_celular_mostra_qr_sem_biblioteca_de_fora(c):
    with mock.patch('finana.routes.acesso.ip_na_rede', return_value='192.168.0.10'):
        assert '<svg' in c.get('/celular').get_data(as_text=True)


# ---------- abrir duas vezes ----------
def test_desktop_nao_mata_processos():
    with open(os.path.join(ROOT, 'finana', 'desktop.py'), encoding='utf-8') as f:
        texto = f.read()
    assert 'taskkill' not in texto
    assert 'shell=True' not in texto


def test_rota_de_ping_identifica_o_app(c):
    assert c.get('/ping').get_json() == {'app': 'AnaFins'}


def test_de_fora_nao_da_para_mexer_na_janela(c):
    assert c.post('/janela/mostrar', headers={'Host': 'pc.exemplo.ts.net'}).status_code in (302, 403)
