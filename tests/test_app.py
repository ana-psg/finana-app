"""
Testes do AnaFins. Usam um banco temporário, nunca o financas_local.db.

Rodar (na pasta do app):
    python -m unittest -v
"""

import os
import sys
import tempfile
import unittest

DB_TESTE = os.path.join(tempfile.gettempdir(), 'anafins_teste.db')
os.environ['ANAFINS_DB'] = DB_TESTE  # precisa vir antes de importar o app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from finana.app import app
from finana.db import conectar, init_db
from finana.utils import add_months, mes_atual, parse_money


def linhas(sql, *args):
    with conectar() as conn:
        return [tuple(r) for r in conn.execute(sql, args).fetchall()]


def um(sql, *args):
    return linhas(sql, *args)[0][0]


def executar(*comandos):
    """executar('SQL', 'SQL', ...) numa única conexão, que é fechada no fim."""
    with conectar() as conn:
        for sql in comandos:
            conn.execute(sql)


class Base(unittest.TestCase):
    def setUp(self):
        # banco limpo a cada teste: esvazia todas as tabelas e recria as categorias iniciais
        with conectar() as conn:
            tabelas = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
            for t in tabelas:
                conn.execute(f'DELETE FROM {t}')
        init_db()
        executar(
            "INSERT INTO accounts (name, type, balance, balance_date) VALUES ('Conta', 'corrente', 1000, '2026-01-01')",
            "INSERT INTO cards (name, bank, limit_total, closing_day, due_day) VALUES ('Cartão', 'Banco', 5000, 26, 2)",
            "INSERT INTO fixed_expenses (description, amount, due_day, category_id) VALUES ('Internet', 99.9, 10, 1)",
        )
        self.c = app.test_client()

    def saldo(self):
        return um('SELECT balance FROM accounts WHERE id = 1')


class TestPaginas(Base):
    def test_todas_as_paginas_abrem(self):
        for url in [
            '/',
            '/contas',
            '/pix',
            '/categorias',
            '/cartoes',
            '/faturas',
            '/faturas?mes=2026-05',
            '/faturas?mes=lixo',
            '/lancamentos',
            '/relatorio_mensal',
            '/relatorio_mensal?mes=2025-13',
            '/orcamento',
            '/despesas_fixas',
            '/despesas_fixas?mes=abc',
            '/investimentos',
        ]:
            self.assertEqual(self.c.get(url).status_code, 200, url)


class TestDinheiro(Base):
    def test_parse_money(self):
        self.assertEqual(parse_money('1.234,56'), 1234.56)
        self.assertEqual(parse_money('R$ 10,5'), 10.5)
        self.assertEqual(parse_money('abc'), 0.0)

    def test_saldo_sempre_em_centavos(self):
        for v in ['0,10', '0,20']:
            self.c.post(
                '/lancamentos',
                data=dict(type='receita', description='x', amount=v, date='2026-10-01', account_id=1, category_id=9),
            )
        self.assertEqual(self.saldo(), 1000.30)

    def test_lancamento_zero_ou_sem_data_e_recusado(self):
        self.c.post(
            '/lancamentos', data=dict(type='despesa', description='x', amount='0', date='2026-10-01', account_id=1)
        )
        self.c.post('/lancamentos', data=dict(type='despesa', description='x', amount='5', date='', account_id=1))
        self.assertEqual((um('SELECT COUNT(*) FROM transactions'), self.saldo()), (0, 1000))

    def test_apagar_lancamento_devolve_saldo(self):
        self.c.post(
            '/lancamentos', data=dict(type='despesa', description='x', amount='50', date='2026-10-01', account_id=1)
        )
        tx = um('SELECT id FROM transactions')
        self.c.post(f'/apagar_lancamento/{tx}')
        self.assertEqual(self.saldo(), 1000)


class TestCartao(Base):
    def compra(self, valor, parcelas=1, data='2026-10-01'):
        return self.c.post(
            '/faturas',
            data=dict(
                card_id=1, description='Compra', total_amount=valor, date=data, category_id=1, installments=parcelas
            ),
        )

    def test_parcelas_somam_o_total(self):
        self.compra('100,00', 3)
        valores = [r[0] for r in linhas('SELECT amount FROM installments ORDER BY installment_number')]
        self.assertEqual(valores, [33.33, 33.33, 33.34])

    def test_compra_cai_na_fatura_certa(self):
        self.compra('10', 1, '2026-09-25')  # antes do fechamento (26): vence 02/10
        self.compra('10', 1, '2026-09-26')  # no dia do fechamento (melhor dia de compra): vence 02/11
        self.compra('10', 1, '2026-09-27')  # depois do fechamento: vence 02/11
        meses = [r[0] for r in linhas('SELECT competence_month FROM installments ORDER BY id')]
        self.assertEqual(meses, ['2026-10', '2026-11', '2026-11'])

    def test_fechamento_dia_31_em_mes_curto(self):
        executar(
            "INSERT INTO cards (id, name, bank, limit_total, closing_day, due_day) VALUES (2, 'Fim', 'B', 1000, 31, 10)"
        )
        for data in ('2026-04-29', '2026-04-30'):  # abril fecha no dia 30: a compra do dia 30 já é da fatura seguinte
            self.c.post(
                '/faturas',
                data=dict(card_id=2, description='x', total_amount='10', date=data, category_id=1, installments=1),
            )
        self.assertEqual(
            [r[0] for r in linhas('SELECT competence_month FROM installments ORDER BY id')], ['2026-05', '2026-06']
        )

    def test_credito_negativo_permitido_zero_e_data_invalida_nao(self):
        self.compra('-76,51')
        self.compra('0')
        self.compra('10', 1, '31/12/2026')
        self.assertEqual(um('SELECT COUNT(*) FROM card_purchases'), 1)

    def test_pagar_fatura_debita_e_marca_pago(self):
        self.compra('200', 2, '2026-10-01')
        self.c.post('/pagar_fatura_cartao', data=dict(card_id=1, account_id=1, competence_month='2026-11'))
        self.assertEqual(self.saldo(), 900)
        self.assertEqual(um("SELECT COUNT(*) FROM installments WHERE status = 'PAGO'"), 1)
        self.assertEqual(um('SELECT COUNT(*) FROM card_invoices_history'), 1)

    def test_pagar_fatura_cria_lancamento_fora_do_resumo(self):
        from finana.services.relatorio import resumo_do_mes

        self.compra('200', 2, '2026-10-01')
        self.c.post('/pagar_fatura_cartao', data=dict(card_id=1, account_id=1, competence_month='2026-11'))
        self.assertEqual(
            linhas('SELECT type, amount, reference_month FROM transactions'), [('despesa', 100, '2026-11')]
        )
        self.assertIn('Fatura', um('SELECT description FROM transactions'))
        with conectar() as conn:
            self.assertEqual(resumo_do_mes(conn, '2026-11')['despesas'], 0)  # já conta pelas faturas

    def pago(self):
        return (
            self.saldo(),
            um("SELECT COUNT(*) FROM installments WHERE status = 'PAGO'"),
            um('SELECT COUNT(*) FROM card_invoices_history'),
            um('SELECT COUNT(*) FROM transactions'),
        )

    def test_desfazer_pagamento_de_fatura(self):
        self.compra('200', 2, '2026-10-01')
        self.c.post('/pagar_fatura_cartao', data=dict(card_id=1, account_id=1, competence_month='2026-11'))
        self.assertIn('Desfazer', self.c.get('/faturas?mes=2026-11').get_data(as_text=True))
        self.c.post(
            f'/faturas/pagamento/{um("SELECT id FROM card_invoices_history")}/desfazer', data=dict(mes='2026-11')
        )
        self.assertEqual(self.pago(), (1000, 0, 0, 0))

    def test_apagar_lancamento_da_fatura_volta_a_pendente(self):
        self.compra('100', 1, '2026-10-01')
        self.c.post('/pagar_fatura_cartao', data=dict(card_id=1, account_id=1, competence_month='2026-11'))
        self.compra('30', 1, '2026-10-02')  # entra depois do 1º pagamento
        self.c.post('/pagar_fatura_cartao', data=dict(card_id=1, account_id=1, competence_month='2026-11'))
        self.assertEqual(self.pago(), (870, 2, 2, 2))
        self.c.post(f'/apagar_lancamento/{um("SELECT MAX(id) FROM transactions")}')  # desfaz só o 2º
        self.assertEqual(self.pago(), (900, 1, 1, 1))
        self.assertEqual(um("SELECT amount FROM installments WHERE status = 'PENDENTE'"), 30)

    def test_pagamento_antigo_nao_e_desfeito(self):
        executar(
            'INSERT INTO card_invoices_history (id, card_id, competence_month, total_amount, paid_date, account_id) '
            "VALUES (1, 1, '2026-11', 50, '2026-11-01', 1)"
        )
        self.assertNotIn('Desfazer', self.c.get('/faturas?mes=2026-11').get_data(as_text=True))
        self.c.post('/faturas/pagamento/1/desfazer', data=dict(mes='2026-11'))
        self.assertEqual((um('SELECT COUNT(*) FROM card_invoices_history'), self.saldo()), (1, 1000))

    def test_fatura_atrasada_continua_no_painel(self):
        a, m = add_months(*map(int, mes_atual().split('-')), -2)
        executar(
            "INSERT INTO card_purchases (id, card_id, description, total_amount, date) VALUES (1, 1, 'Velha', 50, '2026-01-01')",
            'INSERT INTO installments (purchase_id, amount, installment_number, total_installments, competence_month) '
            f"VALUES (1, 50, 1, 1, '{a}-{m:02d}')",
            'DELETE FROM fixed_expenses',
        )
        self.assertIn('- R$ 50,00', self.c.get('/').get_data(as_text=True))


class TestDespesasFixas(Base):
    MES = '2026-10'

    def setUp(self):
        super().setUp()
        self.fid = um('SELECT id FROM fixed_expenses')

    def pagar(self, **extra):
        dados = dict(competence_month=self.MES, paid_date='2026-10-05', pagamento_tipo='conta', conta_id=1)
        dados.update(extra)
        return self.c.post(f'/pagar_despesa_fixa/{self.fid}', data=dados)

    def estornar(self):
        self.c.post(f'/estornar_despesa_fixa/{self.fid}', data=dict(competence_month=self.MES))

    def pagamentos(self):
        return um('SELECT COUNT(*) FROM fixed_expense_payments')

    def test_pagar_pela_conta_duplo_clique_e_desfazer(self):
        self.pagar()
        self.pagar()
        self.assertEqual((self.pagamentos(), self.saldo()), (1, 900.10))
        self.estornar()
        self.assertEqual((self.pagamentos(), self.saldo(), um('SELECT COUNT(*) FROM transactions')), (0, 1000, 0))

    def test_pagar_no_cartao_e_desfazer(self):
        self.pagar(pagamento_tipo='cartao', conta_id='', cartao_id=1)
        self.assertEqual(um('SELECT COUNT(*) FROM installments'), 1)
        self.estornar()
        self.assertEqual((self.pagamentos(), um('SELECT COUNT(*) FROM card_purchases')), (0, 0))

    def test_desfazer_com_fatura_ja_paga_mantem_compra(self):
        self.pagar(pagamento_tipo='cartao', conta_id='', cartao_id=1)
        executar("UPDATE installments SET status = 'PAGO'")
        self.estornar()
        self.assertEqual((self.pagamentos(), um('SELECT COUNT(*) FROM card_purchases')), (0, 1))

    def test_apagar_compra_do_pagamento_volta_a_pendente(self):
        from finana.services.cartoes import excluir_compra

        self.pagar(pagamento_tipo='cartao', conta_id='', cartao_id=1)
        compra = um('SELECT id FROM card_purchases')
        with conectar() as conn:
            excluir_compra(conn, compra)
        self.assertEqual(self.pagamentos(), 0)

    def test_sem_conta_escolhida_nao_marca_paga(self):
        self.pagar(conta_id='')
        self.pagar(pagamento_tipo='')
        self.assertEqual((self.pagamentos(), self.saldo()), (0, 1000))

    def test_apagar_lancamento_do_pagamento_volta_a_pendente(self):
        self.pagar()
        self.c.post(f'/apagar_lancamento/{um("SELECT id FROM transactions")}')
        self.assertEqual((self.pagamentos(), self.saldo()), (0, 1000))


class TestAPagar(Base):
    def criar(self, valor, modo, vezes, primeiro='2026-10-31'):
        self.c.post(
            '/a_pagar',
            data=dict(
                person='Irmão',
                description='Carro',
                amount=valor,
                mode=modo,
                installments=vezes,
                first_due=primeiro,
                category_id='',
            ),
        )

    def parcelas(self):
        return linhas('SELECT amount, due_date FROM debt_installments ORDER BY installment_number')

    def pagar(self, pid, **extra):
        dados = dict(paid_date='2026-10-31', pagamento_tipo='conta', conta_id=1)
        dados.update(extra)
        self.c.post(f'/a_pagar/parcela/{pid}/pagar', data=dados)

    def test_valor_total_dividido_e_vencimentos_mensais(self):
        self.criar('575,42', 'total', 3)
        self.assertEqual(self.parcelas(), [(191.81, '2026-10-31'), (191.81, '2026-11-30'), (191.8, '2026-12-31')])
        self.assertEqual(um('SELECT total_amount FROM debts'), 575.42)

    def test_valor_de_cada_parcela(self):
        self.criar('200', 'parcela', 3)
        self.assertEqual([p[0] for p in self.parcelas()], [200, 200, 200])
        self.assertEqual(um('SELECT total_amount FROM debts'), 600)

    def test_pagar_duplo_clique_desfazer(self):
        self.criar('100', 'total', 1)
        pid = um('SELECT id FROM debt_installments')
        self.pagar(pid)
        self.pagar(pid)
        self.assertEqual((self.saldo(), um('SELECT COUNT(*) FROM transactions')), (900, 1))
        self.assertIn('Pagamento Irmão: Carro', um('SELECT description FROM transactions'))
        self.c.post(f'/a_pagar/parcela/{pid}/desfazer')
        self.assertEqual((self.saldo(), um('SELECT paid_date FROM debt_installments')), (1000, None))

    def test_pagar_no_cartao_e_apagar_lancamento_volta_a_pendente(self):
        self.criar('100', 'total', 2)
        p1, p2 = [r[0] for r in linhas('SELECT id FROM debt_installments ORDER BY id')]
        self.pagar(p1, pagamento_tipo='cartao', conta_id='', cartao_id=1)
        self.assertEqual(um('SELECT COUNT(*) FROM installments'), 1)
        self.pagar(p2)
        self.c.post(f'/apagar_lancamento/{um("SELECT id FROM transactions")}')
        self.assertIsNone(um('SELECT paid_date FROM debt_installments WHERE id = ?', p2))

    def test_parcela_do_mes_entra_no_painel(self):
        executar('DELETE FROM fixed_expenses')
        self.criar('123,45', 'total', 2, f'{mes_atual()}-15')
        self.assertIn('- R$ 61,73', self.c.get('/').get_data(as_text=True))  # só a parcela do mês, não as duas

    def test_recusa_sem_pessoa_ou_valor(self):
        self.c.post('/a_pagar', data=dict(person='', amount='10', mode='total', installments=1, first_due='2026-10-01'))
        self.criar('0', 'total', 1)
        self.assertEqual(um('SELECT COUNT(*) FROM debts'), 0)

    def test_telas_e_abas(self):
        self.criar('50', 'total', 1)
        for url in ['/a_pagar', '/a_pagar?quitadas=1', '/despesas_fixas']:
            html = self.c.get(url).get_data(as_text=True)
            self.assertIn('A pagar (pessoas)', html, url)


class TestMesDeReferencia(Base):
    def lancar(self, tipo, valor, data, ref=''):
        self.c.post(
            '/lancamentos',
            data=dict(
                type=tipo, description='x', amount=valor, date=data, account_id=1, category_id=9, reference_month=ref
            ),
        )
        return um('SELECT reference_month FROM transactions ORDER BY id DESC LIMIT 1')

    def test_regra_automatica(self):
        self.assertEqual(self.lancar('receita', '7000', '2026-09-25'), '2026-10')  # salário antecipado
        self.assertEqual(self.lancar('receita', '7000', '2026-12-27'), '2027-01')  # vira o ano
        self.assertEqual(self.lancar('receita', '100', '2026-09-16'), '2026-09')
        self.assertEqual(self.lancar('despesa', '50', '2026-09-28'), '2026-09')  # despesa fica no mês da data

    def test_escolha_manual_vence_a_regra(self):
        self.assertEqual(self.lancar('receita', '7000', '2026-09-25', '2026-09'), '2026-09')

    def test_despesa_fixa_e_a_pagar_contam_no_mes_delas(self):
        fid = um('SELECT id FROM fixed_expenses')
        self.c.post(
            f'/pagar_despesa_fixa/{fid}',
            data=dict(competence_month='2026-10', paid_date='2026-09-30', pagamento_tipo='conta', conta_id=1),
        )
        self.assertEqual(um('SELECT reference_month FROM transactions'), '2026-10')
        self.c.post(
            '/a_pagar', data=dict(person='Irmão', amount='100', mode='total', installments=1, first_due='2026-11-25')
        )
        self.c.post(
            f'/a_pagar/parcela/{um("SELECT id FROM debt_installments")}/pagar',
            data=dict(paid_date='2026-10-28', pagamento_tipo='conta', conta_id=1),
        )
        self.assertEqual(um('SELECT reference_month FROM transactions ORDER BY id DESC LIMIT 1'), '2026-11')

    def test_relatorio_usa_mes_de_referencia(self):
        self.lancar('receita', '7000', '2026-09-25')
        set_ = self.c.get('/relatorio_mensal?mes=2026-09').get_data(as_text=True)
        out = self.c.get('/relatorio_mensal?mes=2026-10').get_data(as_text=True)
        self.assertNotIn('+ R$ 7.000,00', set_)
        self.assertIn('+ R$ 7.000,00', out)
        self.assertIn('conta em outubro/2026', self.c.get('/lancamentos').get_data(as_text=True))

    def test_migracao_de_banco_antigo(self):
        from finana.db import _preencher_mes_referencia

        executar(
            "INSERT INTO transactions (type, description, amount, date, account_id) VALUES ('receita', 'Salário', 7000, '2026-09-25', 1)",
            "INSERT INTO transactions (type, description, amount, date, account_id) VALUES ('despesa', 'Carro (Mês: 2026-10)', 1000.00, '2026-09-30', 1)",
            'INSERT INTO fixed_expense_payments (fixed_expense_id, competence_month, paid_date, amount, transaction_id) '
            "VALUES (1, '2026-10', '2026-09-30', 1000.00, 2)",
        )
        with conectar() as conn:
            _preencher_mes_referencia(conn)
        self.assertEqual(
            [r[0] for r in linhas('SELECT reference_month FROM transactions ORDER BY id')], ['2026-10', '2026-10']
        )

    def test_migracao_v13_so_adiciona_colunas_vazias(self):
        import sqlite3

        from finana import db

        caminho = os.path.join(tempfile.gettempdir(), 'anafins_v12.db')
        if os.path.exists(caminho):
            os.remove(caminho)
        antigo = sqlite3.connect(caminho)
        antigo.executescript("""
            CREATE TABLE card_invoices_history (id INTEGER PRIMARY KEY, card_id INTEGER, competence_month TEXT,
                total_amount REAL, paid_date TEXT, account_id INTEGER);
            CREATE TABLE installments (id INTEGER PRIMARY KEY, purchase_id INTEGER, amount REAL, installment_number INTEGER,
                total_installments INTEGER, competence_month TEXT, status TEXT DEFAULT 'PENDENTE');
            INSERT INTO card_invoices_history VALUES (1, 1, '2026-09', 50, '2026-09-02', 1);
            INSERT INTO installments VALUES (1, 1, 50, 1, 1, '2026-09', 'PAGO');
        """)
        antigo.commit()
        antigo.close()
        original, db.DB_FILE = db.DB_FILE, caminho
        try:
            init_db()
        finally:
            db.DB_FILE = original
        novo = sqlite3.connect(caminho)
        self.assertEqual(
            novo.execute('SELECT * FROM card_invoices_history').fetchall(),
            [(1, 1, '2026-09', 50, '2026-09-02', 1, None)],
        )
        self.assertEqual(
            novo.execute('SELECT * FROM installments').fetchall(), [(1, 1, 50, 1, 1, '2026-09', 'PAGO', None)]
        )
        novo.close()
        os.remove(caminho)


class TestCelular(Base):
    """Acesso de outro aparelho da rede (ex: celular 192.168.0.50) exige PIN; o computador não."""

    def setUp(self):
        super().setUp()
        from finana.routes import acesso

        acesso._falhas.clear()
        self.cel = app.test_client()
        self.cel.environ_base['REMOTE_ADDR'] = '192.168.0.50'

    def definir_pin(self, pin='1234'):
        return self.c.post('/celular', data=dict(pin=pin, confirmacao=pin))

    def test_celular_sem_login_vai_para_entrar(self):
        for url in ['/', '/rapido', '/lancamentos', '/despesas_fixas']:
            r = self.cel.get(url)
            self.assertEqual(r.status_code, 302, url)
            self.assertIn('/entrar', r.headers['Location'])
        self.assertEqual(self.c.get('/').status_code, 200)  # no computador abre direto

    def test_sem_pin_definido_nao_entra(self):
        html = self.cel.get('/entrar').get_data(as_text=True)
        self.assertIn('ainda não foi liberado', html)
        self.cel.post('/entrar', data=dict(pin='0000'))
        self.assertEqual(self.cel.get('/').status_code, 302)

    def test_pin_errado_e_certo(self):
        self.definir_pin()
        self.assertIn('PIN incorreto', self.cel.post('/entrar', data=dict(pin='9999')).get_data(as_text=True))
        r = self.cel.post('/entrar?proximo=/lancamentos', data=dict(pin='1234'))
        self.assertTrue(r.headers['Location'].endswith('/lancamentos'))
        self.assertEqual(self.cel.get('/').status_code, 200)
        self.cel.get('/sair')
        self.assertEqual(self.cel.get('/').status_code, 302)

    def test_bloqueia_apos_5_erros(self):
        self.definir_pin()
        for _ in range(5):
            self.cel.post('/entrar', data=dict(pin='0000'))
        html = self.cel.post('/entrar', data=dict(pin='1234')).get_data(as_text=True)
        self.assertIn('Muitas tentativas', html)
        self.assertEqual(self.cel.get('/').status_code, 302)

    def test_nao_redireciona_para_outro_site(self):
        self.definir_pin()
        r = self.cel.post('/entrar?proximo=//site-malicioso.com', data=dict(pin='1234'))
        self.assertTrue(r.headers['Location'].endswith('/rapido'))
        r = self.cel.post('/entrar?proximo=/\\site-malicioso.com', data=dict(pin='1234'))
        self.assertTrue(r.headers['Location'].endswith('/rapido'))
        r = self.cel.post('/entrar?proximo=/lancamentos', data=dict(pin='1234'))
        self.assertTrue(r.headers['Location'].endswith('/lancamentos'))

    def test_pin_invalido_e_config_so_no_computador(self):
        self.definir_pin('12')
        self.definir_pin('abcd')
        self.assertEqual(um("SELECT COUNT(*) FROM settings WHERE key = 'pin_hash'"), 0)
        self.assertEqual(self.cel.get('/celular').status_code, 302)  # nem logado: vai pro PIN
        self.definir_pin()
        self.cel.post('/entrar', data=dict(pin='1234'))
        self.assertEqual(self.cel.get('/celular').status_code, 403)  # logado no celular: proibido
        self.assertIn('http://', self.c.get('/celular').get_data(as_text=True))

    def test_manifest_e_layout_de_celular(self):
        self.assertEqual(self.cel.get('/manifest.webmanifest').get_json()['name'], 'AnaFins')
        self.assertIn('name="viewport"', self.c.get('/').get_data(as_text=True))


class TestLancarRapido(Base):
    def lancar(self, **dados):
        base = dict(
            tipo='despesa', valor='50,00', descricao='Mercado', destino='conta:1', categoria='1', data='2026-10-02'
        )
        base.update(dados)
        return self.c.post('/rapido', data=base, follow_redirects=True).get_data(as_text=True)

    def test_despesa_e_receita_na_conta(self):
        self.assertIn('lançada', self.lancar())
        self.lancar(tipo='receita', valor='20')
        self.assertEqual(self.saldo(), 970)

    def test_compra_parcelada_no_cartao(self):
        self.assertIn('em 3x', self.lancar(destino='cartao:1', valor='90', parcelas='3'))
        self.assertEqual(um('SELECT COUNT(*) FROM installments'), 3)
        self.assertEqual(self.saldo(), 1000)

    def test_recusas(self):
        self.assertIn('só dá para lançar despesa', self.lancar(tipo='receita', destino='cartao:1'))
        self.assertIn('Escolha a conta ou o cartão', self.lancar(destino=''))
        self.lancar(valor='0')
        self.assertEqual((um('SELECT COUNT(*) FROM transactions'), um('SELECT COUNT(*) FROM card_purchases')), (0, 0))

    def test_tela_mostra_ultimos(self):
        self.lancar(descricao='Padaria')
        self.assertIn('Padaria', self.c.get('/rapido').get_data(as_text=True))


class TestCadastros(Base):
    def test_categoria_em_uso_nao_e_apagada(self):
        resp = self.c.post('/apagar_categoria/1', follow_redirects=True)  # usada pela despesa fixa
        self.assertIn('em uso', resp.get_data(as_text=True))
        self.assertEqual(um('SELECT COUNT(*) FROM categories WHERE id = 1'), 1)
        self.c.post('/apagar_categoria/2')  # sem uso
        self.assertEqual(um('SELECT COUNT(*) FROM categories WHERE id = 2'), 0)

    def test_categoria_usada_em_a_pagar_nao_e_apagada(self):
        self.c.post(
            '/a_pagar',
            data=dict(
                person='Irmão', amount='100', mode='total', installments=1, first_due='2026-11-25', category_id=3
            ),
        )
        self.c.post('/apagar_categoria/3')
        self.assertEqual(um('SELECT COUNT(*) FROM categories WHERE id = 3'), 1)

    def test_orcamento_nao_conta_pagamento_de_fatura(self):
        executar('INSERT INTO budgets (category_id, amount_limit) VALUES (7, 500)')
        for desc in ('Pagamento Fatura Inter', 'Anuidade do cartão'):
            self.c.post(
                '/lancamentos',
                data=dict(
                    type='despesa', description=desc, amount='40', date=f'{mes_atual()}-05', account_id=1, category_id=7
                ),
            )
        self.assertIn('Gasto: R$ 40,00', self.c.get('/orcamento').get_data(as_text=True))

    def test_apagar_conta_e_cartao_so_desativa(self):
        self.c.post('/apagar_conta/1')
        self.c.post('/apagar_cartao/1')
        self.assertEqual(
            (um('SELECT is_active FROM accounts WHERE id = 1'), um('SELECT is_active FROM cards WHERE id = 1')), (0, 0)
        )

    def test_cartao_com_dia_invalido_e_limitado(self):
        self.c.post('/cartoes', data=dict(name='X', bank='Y', limit_total='100', closing_day='40', due_day='abc'))
        self.assertEqual(linhas("SELECT closing_day, due_day FROM cards WHERE name = 'X'")[0], (31, 10))

    def test_chave_pix(self):
        self.c.post('/pix', data=dict(key='a@b.com', key_type='E-mail', institution='Banco'))
        self.assertIn('a@b.com', self.c.get('/pix').get_data(as_text=True))


class TestRelatorioPDF(Base):
    def setUp(self):
        super().setUp()
        self.c.post(
            '/lancamentos',
            data=dict(
                type='receita', description='Salário', amount='3000', date='2026-10-05', account_id=1, category_id=9
            ),
        )
        self.c.post(
            '/lancamentos',
            data=dict(
                type='despesa',
                description='Padaria — café',
                amount='12,50',
                date='2026-10-06',
                account_id=1,
                category_id=1,
            ),
        )
        self.c.post(
            '/lancamentos',
            data=dict(
                type='despesa',
                description='Pagamento Fatura',
                amount='100',
                date='2026-10-02',
                account_id=1,
                category_id=7,
            ),
        )
        self.c.post(
            '/faturas',
            data=dict(
                card_id=1, description='Compra 😀', total_amount='300', date='2026-09-10', category_id=4, installments=3
            ),
        )

    def test_baixa_pdf_de_qualquer_mes(self):
        for mes in ('2026-10', '2025-01', 'lixo'):
            r = self.c.get(f'/relatorio_mensal/pdf?mes={mes}')
            self.assertEqual(r.status_code, 200, mes)
            self.assertEqual(r.mimetype, 'application/pdf')
            self.assertTrue(r.data.startswith(b'%PDF'))
        self.assertIn(
            'AnaFins_relatorio_2026-10.pdf',
            self.c.get('/relatorio_mensal/pdf?mes=2026-10').headers['Content-Disposition'],
        )
        self.assertIn(
            '/relatorio_mensal/pdf?mes=2026-10', self.c.get('/relatorio_mensal?mes=2026-10').get_data(as_text=True)
        )

    def test_numeros_batem_com_a_tela(self):
        from datetime import datetime

        from finana.services.relatorio import relatorio_completo

        with conectar() as conn:
            d = relatorio_completo(conn, '2026-10', datetime(2026, 10, 6))
        r = d['resumo']
        self.assertEqual((r['receitas'], r['despesas'], r['faturas']), (3000, 12.5, 100))
        self.assertEqual(round(sum(g['gasto'] for g in d['gastos_por_categoria']), 2), r['saidas'])
        self.assertEqual([x['description'] for x in d['pagamentos_fatura']], ['Pagamento Fatura'])
        self.assertEqual(d['cartoes'][0]['total'], 100)
        self.assertEqual(d['cartoes'][0]['limite_livre'], 4700)
        self.assertEqual(d['proximas_faturas'][0]['valores'][:3], [100, 100, 0])
        self.assertEqual([f['description'] for f in d['despesas_fixas']], ['Internet'])

    def test_gasto_com_cartao_no_nome_conta_no_relatorio(self):
        from finana.services.relatorio import resumo_do_mes

        self.c.post(
            '/lancamentos',
            data=dict(
                type='despesa',
                description='Anuidade do Cartão',
                amount='20',
                date='2026-10-07',
                account_id=1,
                category_id=7,
            ),
        )
        with conectar() as conn:
            self.assertEqual(resumo_do_mes(conn, '2026-10')['despesas'], 32.5)


if __name__ == '__main__':
    unittest.main()
