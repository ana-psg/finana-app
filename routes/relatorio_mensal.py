from flask import Blueprint, Response, render_template, request

from db import conectar
from services import relatorio
from services.relatorio_pdf import gerar_pdf
from utils import agora, mes_atual, mes_valido

bp = Blueprint('relatorio_mensal', __name__)


@bp.route('/relatorio_mensal')
def index():
    mes = mes_valido(request.args.get('mes'), mes_atual())
    with conectar() as conn:
        r = relatorio.resumo_do_mes(conn, mes)
        lancamentos_mes = relatorio.lancamentos_do_mes(conn, mes)
        faturas_mes = relatorio.parcelas_do_mes(conn, mes)

    return render_template('relatorio_mensal.html',
                           mes_selecionado=mes,
                           total_receitas=r['receitas'],
                           total_despesas_lancamentos=r['despesas'],
                           total_faturas=r['faturas'],
                           total_saidas=r['saidas'],
                           saldo_liquido_mes=r['balanco'],
                           lancamentos_mes=lancamentos_mes,
                           faturas_mes=faturas_mes)


@bp.route('/relatorio_mensal/pdf')
def exportar_pdf():
    mes = mes_valido(request.args.get('mes'), mes_atual())
    with conectar() as conn:
        dados = relatorio.relatorio_completo(conn, mes, agora())
    return Response(gerar_pdf(dados), mimetype='application/pdf', headers={
        'Content-Disposition': f'attachment; filename="AnaFins_relatorio_{mes}.pdf"'})
