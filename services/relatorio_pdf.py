# =============================================================
# services/relatorio_pdf.py - monta o PDF do relatório mensal completo
# Os números vêm de services/relatorio.py; aqui é só a parte visual (fpdf2).
# =============================================================

from datetime import datetime

from fpdf import FPDF
from fpdf.fonts import FontFace

from utils import brl, nome_mes

ROSA = (219, 39, 119)
CINZA = (110, 110, 120)
CINZA_CLARO = (243, 243, 246)
VERDE = (5, 150, 105)
VERMELHO = (220, 38, 38)
ALTURA_LINHA = 7.6  # mm por linha de tabela

TIPOS_CONTA = {'corrente': 'Corrente', 'beneficio': 'Benefício', 'investimento': 'Investimento',
               'pagamento': 'Pagamento', 'outro': 'Outro'}
STATUS_FATURA = {'aberta': 'Aberta', 'fechada': 'Fechada (a pagar)', 'paga': 'Paga'}


def _txt(valor):
    """As fontes padrão do PDF só têm os caracteres latinos (latin-1): troca o que não couber."""
    s = '' if valor is None else str(valor)
    for de, para in (('—', '-'), ('–', '-'), ('•', '-'), ('“', '"'), ('”', '"'), ('‘', "'"), ('’', "'")):
        s = s.replace(de, para)
    return s.encode('latin-1', 'replace').decode('latin-1')


def _data(iso):
    """'2026-10-05' ou '2026-10-05 08:00:00' -> '05/10/2026'."""
    if not iso:
        return '-'
    try:
        return datetime.strptime(str(iso)[:10], '%Y-%m-%d').strftime('%d/%m/%Y')
    except ValueError:
        return str(iso)


def _mes_curto(competence):
    return nome_mes(competence).capitalize()


class _PDF(FPDF):
    def __init__(self, titulo):
        super().__init__(format='A4')
        self.titulo = titulo
        self.set_auto_page_break(auto=True, margin=15)
        self.set_margins(12, 14, 12)

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font('Helvetica', 'B', 8)
        self.set_text_color(*CINZA)
        self.cell(0, 5, _txt(f'AnaFins - {self.titulo}'), align='L')
        self.ln(8)

    def footer(self):
        self.set_y(-10)
        self.set_font('Helvetica', '', 8)
        self.set_text_color(*CINZA)
        self.cell(0, 5, _txt(f'Página {self.page_no()} de {{nb}}'), align='C')

    # -- peças --------------------------------------------------

    def _reservar(self, altura):
        """Vai para a próxima página se o que vem a seguir não couber nesta."""
        if self.get_y() + altura > self.h - self.b_margin:
            self.add_page()

    def secao(self, titulo, subtitulo=None, linhas=0):
        """linhas: tamanho da tabela que vem logo abaixo; tabelas pequenas não são cortadas no meio
        e o título nunca fica sozinho no pé da página."""
        self._reservar(30 + ALTURA_LINHA * min(linhas, 15))
        self.ln(3)
        self.set_font('Helvetica', 'B', 13)
        self.set_text_color(*ROSA)
        self.cell(0, 8, _txt(titulo), new_x='LMARGIN', new_y='NEXT')
        self.set_draw_color(*ROSA)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(1.5)
        if subtitulo:
            self.set_font('Helvetica', 'I', 8.5)
            self.set_text_color(*CINZA)
            self.multi_cell(0, 4.5, _txt(subtitulo), new_x='LMARGIN', new_y='NEXT')
            self.ln(1)
        self.set_text_color(0, 0, 0)

    def subsecao(self, titulo, direita=None, linhas=0):
        self._reservar(20 + ALTURA_LINHA * min(linhas, 15))
        self.ln(2)
        self.set_font('Helvetica', 'B', 10.5)
        self.set_text_color(30, 30, 40)
        largura = self.w - self.l_margin - self.r_margin
        self.cell(largura * 0.6, 6.5, _txt(titulo))
        self.set_font('Helvetica', '', 9)
        self.cell(largura * 0.4, 6.5, _txt(direita or ''), align='R', new_x='LMARGIN', new_y='NEXT')
        self.set_text_color(0, 0, 0)

    def vazio(self, texto):
        self.set_font('Helvetica', 'I', 9)
        self.set_text_color(*CINZA)
        self.cell(0, 6, _txt(texto), new_x='LMARGIN', new_y='NEXT')
        self.set_text_color(0, 0, 0)

    def tabela(self, cabecalho, linhas, larguras, alinhamentos, total=None):
        """linhas: listas de textos. total: última linha em negrito (ex: ['Total', '', 'R$ 10,00'])."""
        self.set_font('Helvetica', '', 8.5)
        self.set_draw_color(225, 225, 230)
        with self.table(col_widths=larguras, text_align=alinhamentos, line_height=5.2,
                        headings_style=FontFace(emphasis='BOLD', color=(255, 255, 255), fill_color=(55, 55, 70)),
                        cell_fill_color=CINZA_CLARO, cell_fill_mode='ROWS', borders_layout='HORIZONTAL_LINES',
                        padding=1.2, first_row_as_headings=True) as t:
            t.row([_txt(c) for c in cabecalho])
            for linha in linhas:
                t.row([_txt(c) for c in linha])
            if total:
                t.row([_txt(c) for c in total], style=FontFace(emphasis='BOLD'))
        self.ln(2)

    def quadros(self, itens):
        """Quadros de destaque lado a lado: [(rótulo, valor, cor), ...]."""
        largura = (self.w - self.l_margin - self.r_margin - 3 * (len(itens) - 1)) / len(itens)
        y = self.get_y()
        for i, (rotulo, valor, cor) in enumerate(itens):
            x = self.l_margin + i * (largura + 3)
            self.set_fill_color(*CINZA_CLARO)
            self.rect(x, y, largura, 17, style='F')
            self.set_xy(x + 3, y + 2.5)
            self.set_font('Helvetica', '', 7.5)
            self.set_text_color(*CINZA)
            self.cell(largura - 6, 4, _txt(rotulo.upper()))
            self.set_xy(x + 3, y + 8)
            self.set_font('Helvetica', 'B', 12)
            self.set_text_color(*cor)
            self.cell(largura - 6, 6, _txt(valor))
        self.set_text_color(0, 0, 0)
        self.set_xy(self.l_margin, y + 20)


def gerar_pdf(d):
    """d = services.relatorio.relatorio_completo(...). Retorna os bytes do PDF."""
    mes, hoje = d['mes'], d['hoje']
    titulo = f'Relatório de {nome_mes(d["mes"])}'
    pdf = _PDF(titulo)
    pdf.set_title(_txt(f'AnaFins - {titulo}'))
    pdf.set_author('AnaFins')
    pdf.add_page()

    # ---- Capa / resumo ------------------------------------------
    pdf.set_font('Helvetica', 'B', 22)
    pdf.set_text_color(*ROSA)
    pdf.cell(0, 11, 'AnaFins', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', 'B', 15)
    pdf.set_text_color(30, 30, 40)
    pdf.cell(0, 8, _txt(f'Relatório completo - {_mes_curto(mes)}'), new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 9)
    pdf.set_text_color(*CINZA)
    pdf.cell(0, 6, _txt(f'Gerado em {hoje.strftime("%d/%m/%Y às %H:%M")}. Saldos e status das faturas são os desse momento.'),
             new_x='LMARGIN', new_y='NEXT')
    pdf.ln(3)

    r = d['resumo']
    pdf.secao('Resumo do mês', 'Lançamentos contam no mês de referência. Pagamentos de fatura não entram aqui, '
                               'porque as compras já contam pelas faturas.')
    pdf.quadros([('Entradas', f'+ {brl(r["receitas"])}', VERDE),
                 ('Faturas (cartão)', f'- {brl(r["faturas"])}', VERMELHO)])
    pdf.quadros([('Despesas em conta', f'- {brl(r["despesas"])}', VERMELHO),
                 ('Total de saídas', f'- {brl(r["saidas"])}', VERMELHO),
                 ('Balanço do mês', brl(r['balanco']), VERDE if r['balanco'] >= 0 else VERMELHO)])

    v = d['visao_geral']
    pdf.secao('Visão geral', linhas=7, subtitulo=f'Saldo das contas hoje e o que ainda falta pagar até {nome_mes(mes)} '
                             '(inclui pendências de meses anteriores).')
    pdf.tabela(['Item', 'Valor'], [
        ['Saldo total nas contas', brl(v['saldo'])],
        ['Faturas pendentes', f'- {brl(v["faturas"])}'],
        ['Despesas fixas não pagas no mês', f'- {brl(v["despesas_fixas"])}'],
        ['A pagar (pessoas) vencendo até o mês', f'- {brl(v["a_pagar"])}'],
        ['Total de obrigações', f'- {brl(v["obrigacoes"])}'],
    ], (70, 30), ('LEFT', 'RIGHT'), total=['Disponível de verdade', brl(v['disponivel'])])

    # ---- Contas ---------------------------------------------------
    pdf.secao('Contas e saldos atuais', linhas=len(d['contas']) + 2)
    if d['contas']:
        pdf.tabela(['Conta', 'Tipo', 'Saldo desde', 'Saldo atual'],
                   [[c['name'], TIPOS_CONTA.get(c['type'], c['type']), _data(c['balance_date']), brl(c['balance'])]
                    for c in d['contas']],
                   (45, 25, 25, 30), ('LEFT', 'LEFT', 'CENTER', 'RIGHT'),
                   total=['Total', '', '', brl(sum(c['balance'] for c in d['contas']))])
    else:
        pdf.vazio('Nenhuma conta ativa.')

    # ---- Faturas --------------------------------------------------
    pdf.secao(f'Faturas de {nome_mes(mes)}', 'Mês da fatura = mês do vencimento.', linhas=len(d['cartoes']) + 2)
    if d['cartoes']:
        pdf.tabela(['Cartão', 'Fecha', 'Vence', 'Status', 'Total', 'Falta pagar'],
                   [[c['name'], c['fecha'], c['vence'], STATUS_FATURA.get(c['status'], c['status']),
                     brl(c['total']), brl(c['pendente'])] for c in d['cartoes']],
                   (34, 20, 20, 28, 24, 24), ('LEFT', 'CENTER', 'CENTER', 'LEFT', 'RIGHT', 'RIGHT'),
                   total=['Total', '', '', '', brl(sum(c['total'] for c in d['cartoes'])),
                          brl(sum(c['pendente'] for c in d['cartoes']))])
        pdf.subsecao('Limite dos cartões', linhas=len(d['cartoes']) + 1)
        pdf.tabela(['Cartão', 'Limite total', 'Comprometido', 'Disponível'],
                   [[c['name'], brl(c['limite']), brl(c['limite_usado']), brl(c['limite_livre'])] for c in d['cartoes']],
                   (40, 30, 30, 30), ('LEFT', 'RIGHT', 'RIGHT', 'RIGHT'))
    else:
        pdf.vazio('Nenhum cartão ativo.')

    for c in d['cartoes']:
        pdf.secao(f'Fatura {c["name"]} - {nome_mes(mes)}',
                  f'{c["bank"]}. Fecha {c["fecha"]}, vence {c["vence"]}. {len(c["itens"])} itens.',
                  linhas=len(c['itens']) + 2)
        if c['itens']:
            pdf.tabela(['Compra', 'Descrição', 'Categoria', 'Parcela', 'Status', 'Valor'],
                       [[_data(p['data_compra']), p['description'], p['categoria'] or '-',
                         f'{p["installment_number"]}/{p["total_installments"]}',
                         'Pago' if p['status'] == 'PAGO' else 'Pendente', brl(p['amount'])] for p in c['itens']],
                       (19, 62, 28, 15, 18, 24), ('CENTER', 'LEFT', 'LEFT', 'CENTER', 'CENTER', 'RIGHT'),
                       total=['', 'Total da fatura', '', '', '', brl(c['total'])])
        else:
            pdf.vazio('Nenhuma compra nesta fatura.')

    # ---- Compras feitas no mês ------------------------------------------
    pdf.secao(f'Compras feitas no cartão em {nome_mes(mes)}',
              'Pela data da compra (as parcelas podem cair em faturas de outros meses).', linhas=len(d['compras']) + 2)
    if d['compras']:
        pdf.tabela(['Data', 'Cartão', 'Descrição', 'Categoria', 'Parcelas', '1ª fatura', 'Valor total'],
                   [[_data(p['date']), p['cartao'], p['description'], p['categoria'] or '-', f'{p["parcelas"]}x',
                     _mes_curto(p['primeira_fatura']) if p['primeira_fatura'] else '-', brl(p['total_amount'])]
                    for p in d['compras']],
                   (18, 22, 50, 24, 15, 27, 24), ('CENTER', 'LEFT', 'LEFT', 'LEFT', 'CENTER', 'LEFT', 'RIGHT'),
                   total=['', '', 'Total', '', '', '', brl(sum(p['total_amount'] for p in d['compras']))])
    else:
        pdf.vazio('Nenhuma compra no cartão neste mês.')

    # ---- Lançamentos ----------------------------------------------------
    def lancamentos(titulo, itens, sinal, vazio, subtitulo=None):
        pdf.secao(titulo, subtitulo, linhas=len(itens) + 2)
        if not itens:
            pdf.vazio(vazio)
            return
        pdf.tabela(['Data', 'Descrição', 'Conta', 'Categoria', 'Valor'],
                   [[_data(l['date']), l['description'], l['conta'] or '-', l['categoria'] or '-',
                     f'{sinal} {brl(l["amount"])}'] for l in itens],
                   (19, 75, 28, 28, 26), ('CENTER', 'LEFT', 'LEFT', 'LEFT', 'RIGHT'),
                   total=['', 'Total', '', '', f'{sinal} {brl(sum(l["amount"] for l in itens))}'])

    lancamentos('Entradas (receitas)', d['receitas'], '+', 'Nenhuma entrada neste mês.')
    lancamentos('Despesas pagas pela conta', d['despesas'], '-', 'Nenhuma despesa em conta neste mês.')
    lancamentos('Pagamentos de fatura e movimentações', d['pagamentos_fatura'], '-',
                'Nenhum pagamento de fatura neste mês.',
                'Dinheiro que saiu da conta para pagar cartão. Não conta como despesa nova no resumo.')

    # ---- Categorias -----------------------------------------------------
    pdf.secao('Gastos por categoria', 'Despesas em conta + parcelas das faturas do mês, com o orçamento definido.',
              linhas=len(d['gastos_por_categoria']) + 2)
    if d['gastos_por_categoria']:
        def situacao(g):
            if not g['limite']:
                return '-'
            uso = g['gasto'] / g['limite'] * 100
            return f'{uso:.0f}%' + (' (estourou)' if uso > 100 else '')
        pdf.tabela(['Categoria', 'Gasto', 'Orçamento', 'Uso'],
                   [[g['categoria'], brl(g['gasto']), brl(g['limite']) if g['limite'] else '-', situacao(g)]
                    for g in d['gastos_por_categoria']],
                   (50, 30, 30, 30), ('LEFT', 'RIGHT', 'RIGHT', 'RIGHT'),
                   total=['Total', brl(sum(g['gasto'] for g in d['gastos_por_categoria'])), '', ''])
    else:
        pdf.vazio('Nenhum gasto neste mês.')

    # ---- Despesas fixas -----------------------------------------------
    pdf.secao('Despesas fixas do mês', linhas=len(d['despesas_fixas']) + 2)
    if d['despesas_fixas']:
        pagas = [f for f in d['despesas_fixas'] if f['paid_date']]
        pdf.tabela(['Dia', 'Descrição', 'Categoria', 'Situação', 'Valor'],
                   [[str(f['due_day']), f['description'], f['categoria'] or '-',
                     f'Paga em {_data(f["paid_date"])} ({f["via"] or "-"})' if f['paid_date'] else 'Pendente',
                     brl(f['valor_pago'] if f['paid_date'] else f['amount'])] for f in d['despesas_fixas']],
                   (12, 60, 30, 50, 26), ('CENTER', 'LEFT', 'LEFT', 'LEFT', 'RIGHT'),
                   total=['', f'{len(pagas)} de {len(d["despesas_fixas"])} pagas', '', '',
                          brl(sum(f['valor_pago'] if f['paid_date'] else f['amount'] for f in d['despesas_fixas']))])
    else:
        pdf.vazio('Nenhuma despesa fixa cadastrada.')

    # ---- A pagar ----------------------------------------------------------
    pdf.secao('A pagar (pessoas)', f'Parcelas com vencimento em {nome_mes(mes)} e atrasadas. '
                                   f'Total ainda em aberto (todas as dívidas): {brl(d["a_pagar_total_aberto"])}.',
              linhas=len(d['a_pagar']) + 2)
    if d['a_pagar']:
        pdf.tabela(['Vence', 'Para', 'Descrição', 'Parcela', 'Situação', 'Valor'],
                   [[_data(p['due_date']), p['person'], p['description'] or '-',
                     f'{p["installment_number"]}/{p["total_installments"]}',
                     f'Paga em {_data(p["paid_date"])}' if p['paid_date'] else
                     ('Atrasada' if p['due_date'][:7] < mes else 'Pendente'), brl(p['amount'])] for p in d['a_pagar']],
                   (20, 30, 50, 16, 34, 26), ('CENTER', 'LEFT', 'LEFT', 'CENTER', 'LEFT', 'RIGHT'),
                   total=['', 'Total', '', '', '', brl(sum(p['amount'] for p in d['a_pagar']))])
    else:
        pdf.vazio('Nada a pagar para pessoas neste mês.')

    # ---- Próximas faturas -------------------------------------------------
    pdf.secao('Próximas faturas', 'Parcelas e compras já lançadas que vão cair nos próximos meses.',
              linhas=len(d['proximas_faturas']) + 2)
    if d['proximas_faturas']:
        meses = d['meses_futuros']
        totais = [sum(p['valores'][i] for p in d['proximas_faturas']) for i in range(len(meses))]
        pdf.tabela(['Cartão'] + [nome_mes(m_)[:3].capitalize() + '/' + m_[2:4] for m_ in meses],
                   [[p['cartao']] + [brl(x) for x in p['valores']] for p in d['proximas_faturas']],
                   [30] + [24] * len(meses), ['LEFT'] + ['RIGHT'] * len(meses),
                   total=['Total'] + [brl(x) for x in totais])
    else:
        pdf.vazio('Nenhum cartão ativo.')

    return bytes(pdf.output())
