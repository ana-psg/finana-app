from flask import Blueprint, flash, redirect, render_template, request, url_for

from finana.db import conectar
from finana.utils import ErroNegocio, texto_obrigatorio

bp = Blueprint('pix', __name__)


@bp.route('/pix', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        f = request.form
        try:
            chave = texto_obrigatorio(f.get('key'), 'a chave Pix')
            instituicao = texto_obrigatorio(f.get('institution'), 'a instituição')
            with conectar() as conn:
                conn.execute(
                    """
                    INSERT INTO pix_keys (key, key_type, institution, account_type, agency, account_number, created_at, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        chave,
                        f.get('key_type') or 'outra',
                        instituicao,
                        f.get('account_type'),
                        f.get('agency', '').strip(),
                        f.get('account_number', '').strip(),
                        f.get('created_at'),
                        f.get('status', 'Ativa'),
                    ),
                )
        except ErroNegocio as e:
            flash(str(e), 'erro')
        return redirect(url_for('pix.index'))

    with conectar() as conn:
        chaves = conn.execute('SELECT * FROM pix_keys ORDER BY institution ASC').fetchall()
    return render_template('pix.html', chaves=chaves)


@bp.route('/apagar_pix/<int:id>', methods=['POST'])
def apagar(id):
    with conectar() as conn:
        conn.execute('DELETE FROM pix_keys WHERE id = ?', (id,))
    return redirect(url_for('pix.index'))
