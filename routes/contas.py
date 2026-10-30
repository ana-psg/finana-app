from flask import Blueprint, redirect, render_template, request, url_for

from db import conectar
from utils import parse_money

bp = Blueprint('contas', __name__)


@bp.route('/contas', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        with conectar() as conn:
            conn.execute('INSERT INTO accounts (name, type, balance, balance_date) VALUES (?, ?, ?, ?)',
                         (request.form['name'].strip(), request.form['type'],
                          parse_money(request.form.get('balance')), request.form.get('date', '')))
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
