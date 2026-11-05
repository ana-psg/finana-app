# Receita do executável. Pasta (onedir) e sem UPX: os dois reduzem alarmes falsos de antivírus.
# Gerar: python -m PyInstaller packaging/AnaFins.spec --noconfirm --distpath dist --workpath build
import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = os.path.dirname(SPECPATH)

a = Analysis(
    [os.path.join(ROOT, 'main.py')],
    pathex=[ROOT],
    # Só telas, estilos e o schema: nenhum dado pessoal (banco, backups, logs) entra no pacote
    datas=[
        (os.path.join(ROOT, 'finana', 'templates'), 'finana/templates'),
        (os.path.join(ROOT, 'finana', 'static'), 'finana/static'),
        (os.path.join(ROOT, 'finana', 'schema.sql'), 'finana'),
        *collect_data_files('tzdata'),
        *collect_data_files('fpdf'),
    ],
    # As telas são carregadas pelo nome (routes/__init__.py, import_module): o PyInstaller não as enxerga sozinho
    hiddenimports=[*collect_submodules('finana.routes'), *collect_submodules('finana.services')],
    excludes=['tkinter', 'pytest', 'playwright', 'ruff'],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AnaFins',
    console=False,
    upx=False,
    icon=os.path.join(ROOT, 'icon.ico'),
    version=os.path.join(SPECPATH, 'version_info.txt'),
)
coll = COLLECT(exe, a.binaries, a.datas, name='AnaFins', upx=False)
