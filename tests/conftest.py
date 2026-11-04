"""Proteção dos testes: recusa rodar se o banco apontar para os dados reais."""

import os
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ['ANAFINS_DB'] = os.path.join(tempfile.mkdtemp(prefix='anafins-teste-'), 'teste.db')

from finana.db import DB_FILE

if os.path.normcase(os.path.abspath(DB_FILE)) == os.path.normcase(os.path.join(ROOT, 'financas_local.db')):
    pytest.exit('Os testes apontam para o banco real. Nada foi executado.', returncode=2)
