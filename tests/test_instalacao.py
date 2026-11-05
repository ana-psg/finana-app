"""Onde ficam os dados: programa instalado em %APPDATA%\\AnaFins, rodando pelo código na pasta do projeto."""

import os

from finana.db import pasta_dados


def test_pelo_codigo_usa_a_pasta_do_projeto():
    assert pasta_dados(False, {'APPDATA': r'C:\Users\x\AppData\Roaming'}, r'C:\projeto') == r'C:\projeto'


def test_instalado_usa_appdata():
    pasta = pasta_dados(True, {'APPDATA': r'C:\Users\x\AppData\Roaming'}, r'C:\projeto')
    assert pasta == os.path.join(r'C:\Users\x\AppData\Roaming', 'AnaFins')


def test_instalado_sem_appdata_usa_a_pasta_do_usuario():
    assert pasta_dados(True, {}, r'C:\projeto') == os.path.join(os.path.expanduser('~'), 'AnaFins')
