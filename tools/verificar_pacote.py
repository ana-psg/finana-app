"""Confere que nenhum dado pessoal entrou no pacote; o build para se encontrar algum.

Uso: python tools/verificar_pacote.py dist/AnaFins

Os textos procurados vêm de quem está gerando o build (usuário do Windows e e-mail do git),
para que este arquivo não precise guardar nenhum dado pessoal.
"""

import os
import re
import shutil
import subprocess
import sys
import types

NOME_PROIBIDO = re.compile(r'(\.db|\.db-wal|\.db-shm|\.db\.bak|\.log|\.zip|\.rar|\.env)$', re.IGNORECASE)
NOME_LIBERADO = {'base_library.zip'}  # biblioteca padrão do Python, que o PyInstaller sempre põe no pacote
TEXTO_MINIMO = 6  # textos curtos demais dariam alarme falso em arquivos binários


def _saida_do_comando(*args):
    if not shutil.which(args[0]):
        return ''
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=15, check=False).stdout.strip()
    except OSError:
        return ''


def textos_pessoais():
    pasta_usuario = os.path.expanduser('~')
    email = _saida_do_comando('git', 'config', 'user.email')
    achados = [pasta_usuario, pasta_usuario.replace('\\', '/'), email, email.split('@')[0]]
    return sorted({t for t in achados if len(t) >= TEXTO_MINIMO})


def nomes_proibidos(raiz):
    return [
        os.path.join(pasta, nome)
        for pasta, _, arquivos in os.walk(raiz)
        for nome in arquivos
        if NOME_PROIBIDO.search(nome) and nome.lower() not in NOME_LIBERADO
    ]


def textos_do_codigo(codigo):
    """Os textos de um módulo compilado: constantes (também das funções internas) e o nome do arquivo."""
    partes = [codigo.co_filename.encode('utf-8', 'replace')]
    for const in codigo.co_consts:
        if isinstance(const, str):
            partes.append(const.encode('utf-8', 'replace'))
        elif isinstance(const, bytes):
            partes.append(const)
        elif isinstance(const, types.CodeType):
            partes.append(textos_do_codigo(const))
    return b'\n'.join(partes)


def _modulos_embutidos(caminho):
    """Os módulos Python ficam comprimidos dentro do executável: abre para conferir também."""
    from PyInstaller.archive.readers import CArchiveReader

    saida = []
    arquivo = CArchiveReader(caminho)
    for nome in arquivo.toc:
        if nome.endswith('.pyz'):
            modulos = arquivo.open_embedded_archive(nome)
            for modulo in modulos.toc:
                codigo = modulos.extract(modulo)
                if isinstance(codigo, types.CodeType):  # None = pacote sem código
                    saida.append((f'{nome}:{modulo}', textos_do_codigo(codigo)))
    return saida


def conteudos_proibidos(raiz, textos):
    procurados = [(t, t.encode('utf-8').lower()) for t in textos]
    saida = []
    for pasta, _, arquivos in os.walk(raiz):
        for nome in arquivos:
            caminho = os.path.join(pasta, nome)
            with open(caminho, 'rb') as f:
                dados = f.read().lower()
            saida += [f'{caminho}: {t}' for t, p in procurados if p in dados]
            if nome.lower().endswith('.exe'):
                modulos = _modulos_embutidos(caminho)
                if not modulos:
                    saida.append(f'{caminho}: não consegui abrir os módulos para conferir')
                for rotulo, texto in modulos:
                    saida += [f'{rotulo}: {t}' for t, p in procurados if p in texto.lower()]
    return saida


def main():
    raiz = sys.argv[1]
    problemas = nomes_proibidos(raiz) + conteudos_proibidos(raiz, textos_pessoais())
    for problema in problemas:
        print('DADO PESSOAL NO PACOTE:', problema)
    if problemas:
        return 1
    print('Pacote limpo: nenhum dado pessoal encontrado.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
