from flask import Blueprint, flash, redirect, render_template, request, url_for

from db import conectar
from utils import ErroNegocio, texto_obrigatorio

bp = Blueprint('categorias', __name__)


@bp.route('/categorias', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        try:
            nome = texto_obrigatorio(request.form.get('name'), 'o nome da categoria', 60)
            with conectar() as conn:
                conn.execute('INSERT INTO categories (name, type) VALUES (?, ?)',
                             (nome, request.form.get('type') or 'despesa'))
        except ErroNegocio as e:
            flash(str(e), 'erro')
        return redirect(url_for('categorias.index'))

    with conectar() as conn:
        categorias_lista = conn.execute("SELECT * FROM categories ORDER BY name ASC").fetchall()
    return render_template('categorias.html', categorias_lista=categorias_lista)


@bp.route('/apagar_categoria/<int:id>', methods=['POST'])
def apagar(id):
    with conectar() as conn:
        em_uso = conn.execute('''
            SELECT (SELECT COUNT(*) FROM transactions   WHERE category_id = :id)
                 + (SELECT COUNT(*) FROM card_purchases WHERE category_id = :id)
                 + (SELECT COUNT(*) FROM fixed_expenses WHERE category_id = :id)
                 + (SELECT COUNT(*) FROM budgets        WHERE category_id = :id)
                 + (SELECT COUNT(*) FROM debts          WHERE category_id = :id)
        ''', {'id': id}).fetchone()[0]
        if em_uso:
            flash(f'Essa categoria está em uso em {em_uso} registro(s) e não pode ser apagada.', 'erro')
        else:
            conn.execute('DELETE FROM categories WHERE id = ?', (id,))
    return redirect(url_for('categorias.index'))
