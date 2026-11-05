# AnaFins (repo finana-app)

App desktop pessoal (Windows) da Ana: controle financeiro local, sem nuvem e sem cadastro.
Flask + pywebview + SQLite + Tailwind (CSS gerado e versionado). Usável no celular pelo Wi-Fi de casa, com PIN.

## Estrutura
- `main.py` abre o app (o `AnaFins.bat` chama ele). Pacote `finana/`: `app.py` (create_app), `desktop.py`
  (janela + servidor), `db.py` (conexão, schema.sql, migrações), `utils.py`, `net.py`, `qr.py`,
  `services/` (regras de negócio), `routes/` (um Blueprint por tela), `templates/`, `static/`.
- `tests/` (pytest; `e2e_telas.py` com Playwright) e `tools/` (setup_db, seed).

## Regras
- Idioma: código, telas e mensagens em português; tabelas e colunas do banco em inglês. Não renomear
  colunas: o banco real da Ana depende delas.
- Rotas só leem o formulário e mostram a tela; cálculo e escrita no banco ficam em `services/`.
- Erros de dado: `utils.ErroNegocio` com mensagem em português (vira `flash(..., 'erro')`).
- Banco: `schema.sql` é o formato atual. Para mudar: altere o schema E acrescente o passo em `db._migrar`
  (bancos existentes). Nunca apagar o banco. `financas_local.db` e `anafins.log` ficam em `db.PASTA_DADOS`:
  no app instalado (.exe), `%APPDATA%\AnaFins` (o banco real da Ana está lá); rodando pelo código, na raiz do projeto.
- Mantenha o .exe funcionando (`packaging/AnaFins.spec`): arquivo novo que o app lê de dentro de `finana/`
  (fora de .py) entra em `datas`.
- `conectar()` abre com BEGIN IMMEDIATE: cada pedido reserva a escrita (evita pagar duas vezes).
- Dinheiro sempre arredondado em centavos (`ROUND(..., 2)` no SQL, `round(..., 2)` no Python).
- Datas: `utils.agora()` (São Paulo, sem fuso). Mês = 'AAAA-MM'; mês da fatura = mês de VENCIMENTO.
- Conta e cartão removidos são desativados (`is_active = 0`), nunca apagados, e não recebem lançamentos novos.
- Segurança: no próprio PC (127.0.0.1) abre direto; qualquer outro aparelho pede o PIN. Trocar o PIN
  desconecta os aparelhos (`pin_versao`). Host e Origin são conferidos (net.py).
- Tailwind: usar classes da escala; depois de classe nova, `npm run css`. Cores do app ficam em
  `tailwind.config.js` (theme.extend), não em hex solto nos templates.
- Acessibilidade: botão só com ícone precisa de `aria-label`.
- Nada de dados pessoais no Git: banco, backups, logs, `tools/legado/`. O repo público começou de um
  snapshot limpo; nunca dar push do histórico local antigo (branch `historico-local`).

## Antes de terminar uma mudança
- `ruff check . && ruff format --check .`
- `python -m pytest`
- Mudou tela ou CSS: `npm run css` e `python tests/e2e_telas.py`, depois olhar as capturas em `data/telas`.

## Como rodar
- App: `python main.py`
- Instalador: `.\build.ps1` (precisa do Inno Setup 6; saída em `dist/`)
- Só no navegador: `python -m finana.app` -> http://127.0.0.1:8000
