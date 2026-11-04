from flask import Blueprint, flash, redirect, render_template, request, url_for

from db import conectar
from utils import ErroNegocio, agora, data_valida, dinheiro, texto_obrigatorio

bp = Blueprint('contas', __name__)


@bp.route('/contas', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        f = request.form
        try:
            dados = (texto_obrigatorio(f.get('name'), 'o nome da conta'), f.get('type') or 'outro',
                     dinheiro(f.get('balance'), 'Saldo'), (data_valida(f.get('date')) or agora()).strftime('%Y-%m-%d'))
            with conectar() as conn:
                conn.execute('INSERT INTO accounts (name, type, balance, balance_date) VALUES (?, ?, ?, ?)', dados)
        except ErroNegocio as e:
            flash(str(e), 'erro')
        return redirect(url_for('contas.index'))

    with conectar() as conn:
        contas_lista = conn.execute("SELECT * FROM accounts WHERE is_active = 1 ORDER BY name ASC").fetchall()
    return render_template('contas.html', contas_lista=contas_lista)


@bp.route('/apagar_conta/<int:id>', methods=['POST'])
def apagar(id):
    # Desativa em vez de apagar: lançamentos e faturas pagas continuam apontando pra ela
    with conectar() as conn:
        conn.execute('UPDATE accounts SET is_active = 0 WHERE id = ?', (id,))
    return redirect(url_for('contas.index'))
