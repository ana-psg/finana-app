from flask import Blueprint, render_template

bp = Blueprint('investimentos', __name__)


@bp.route('/investimentos')
def index():
    return render_template('investimentos.html')
