from flask import Blueprint, redirect, render_template, request, url_for

from db import conectar

bp = Blueprint('pix', __name__)


@bp.route('/pix', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        f = request.form
        with conectar() as conn:
            conn.execute('''
                INSERT INTO pix_keys (key, key_type, institution, account_type, agency, account_number, created_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (f['key'].strip(), f['key_type'], f['institution'].strip(), f.get('account_type'),
                  f.get('agency', '').strip(), f.get('account_number', '').strip(), f.get('created_at'),
                  f.get('status', 'Ativa')))
        return redirect(url_for('pix.index'))

    with conectar() as conn:
        chaves = conn.execute("SELECT * FROM pix_keys ORDER BY institution ASC").fetchall()
    return render_template('pix.html', chaves=chaves)


@bp.route('/apagar_pix/<int:id>', methods=['POST'])
def apagar(id):
    with conectar() as conn:
        conn.execute('DELETE FROM pix_keys WHERE id = ?', (id,))
    return redirect(url_for('pix.index'))
