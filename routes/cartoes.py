from flask import Blueprint, flash, redirect, render_template, request, url_for

from db import conectar
from utils import ErroNegocio, dinheiro, inteiro, texto_obrigatorio

bp = Blueprint('cartoes', __name__)


@bp.route('/cartoes', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        f = request.form
        try:
            dados = (texto_obrigatorio(f.get('name'), 'o nome do cartão'), (f.get('bank') or '').strip(),
                     dinheiro(f.get('limit_total'), 'Limite'),
                     # dia 0 ou 40 quebraria o cálculo das datas da fatura
                     inteiro(f.get('closing_day'), 1, 1, 31), inteiro(f.get('due_day'), 10, 1, 31))
            with conectar() as conn:
                conn.execute('INSERT INTO cards (name, bank, limit_total, closing_day, due_day) VALUES (?, ?, ?, ?, ?)', dados)
        except ErroNegocio as e:
            flash(str(e), 'erro')
        return redirect(url_for('cartoes.index'))

    with conectar() as conn:
        cartoes_lista = conn.execute("SELECT * FROM cards WHERE is_active = 1").fetchall()
    return render_template('cartoes.html', cartoes_lista=cartoes_lista)


@bp.route('/apagar_cartao/<int:id>', methods=['POST'])
def apagar(id):
    # Desativa em vez de apagar: compras e parcelas continuam ligadas ao cartão
    with conectar() as conn:
        conn.execute('UPDATE cards SET is_active = 0 WHERE id = ?', (id,))
    return redirect(url_for('cartoes.index'))
