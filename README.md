# AnaFins - Gestão Financeira Local

O AnaFins é um aplicativo de controle financeiro pessoal feito com foco em privacidade (local-first): sem nuvem, sem integração bancária e sem cadastro. Todos os dados ficam num banco SQLite no próprio computador. É feito em Python (Flask) e abre como aplicativo de desktop com a biblioteca pywebview. Também pode ser usado pelo celular, no Wi‑Fi de casa.

## Funcionalidades

* **Lançar rápido:** registra um gasto ou uma entrada em segundos, pensado para o celular.
* **Contas e saldos:** saldo de cada conta atualizado a cada lançamento.
* **Lançamentos:** receitas e despesas avulsas, com **mês de referência** (ex: o salário que cai no fim do mês conta no relatório do mês seguinte, que é quando ele é usado).
* **Cartões de crédito:** compras parceladas, datas de fechamento e vencimento, faturas por mês e pagamento de fatura.
* **Despesas:**
  * **Fixas:** contas recorrentes (aluguel, streaming, seguro...) com baixa por conta ou cartão e opção de desfazer.
  * **A pagar (pessoas):** o que você deve a alguém, em uma ou várias vezes (ex: "3x de R$ 200 para o meu irmão").
* **Chaves Pix:** suas chaves e as contas ligadas a cada uma (dados do Registrato), com botão de copiar.
* **Orçamento:** limite de gastos por categoria no mês.
* **Relatório mensal:** entradas, saídas, faturas e balanço do mês, com botão para **exportar tudo em PDF** (resumo, saldos, faturas item a item, compras, lançamentos, categorias, despesas fixas, a pagar e próximas faturas).
* **Visão geral:** saldo total, obrigações pendentes (faturas, despesas e parcelas do mês) e quanto está realmente disponível.

## Tecnologias

* Back-end: Python 3.10+ e Flask
* Front-end: HTML5, Jinja2 e Tailwind CSS
* Banco de dados: SQLite (`financas_local.db`)
* Desktop: pywebview

## Instalação e Execução

### Pré-requisitos
Python 3.10 ou superior.

### Passo a passo

1. Clone o repositório:
   ```bash
   git clone https://github.com/ana-psg/finana-app.git
   cd finana-app
   ```
2. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```
3. Abra o app com um duplo clique em `AnaFins.bat`, ou rode `python desktop.py`.
   Para abrir no navegador, rode `python app.py` e acesse http://127.0.0.1:8000.

O banco `financas_local.db` é criado sozinho na primeira execução e **nunca vai para o Git**.

## Usar no Celular (Wi‑Fi de casa)

1. No computador, abra o AnaFins e clique em **📱 Usar no celular** (rodapé do menu) para criar um PIN.
2. Com o celular no mesmo Wi‑Fi, leia o QR code ou digite o endereço mostrado (ex: `http://192.168.0.10:8000`).
3. Entre com o PIN e use **Adicionar à tela inicial** para abrir como um app.

O computador precisa estar ligado e com o AnaFins aberto. No próprio computador o PIN não é pedido.
Na primeira vez, permita o Python em **Redes privadas** quando o Windows perguntar.

## Organização do Código

```
app.py              monta o app (banco + filtros + rotas)
desktop.py          abre o app numa janela própria (pywebview)
db.py               conexão com o SQLite, criação do banco e migrações
schema.sql          estrutura das tabelas (fonte da verdade do banco)
utils.py            dinheiro (R$), meses e leitura de formulários
services/           regras de negócio, sem nada de tela
  contas.py           saldos, lançamentos e mês de referência
  cartoes.py          compras parceladas, faturas e pagamento de fatura
  pagamentos.py       pagar por conta ou cartão (e desfazer), usado pelas despesas
  despesas_fixas.py   pagar / desfazer / excluir despesa fixa
  a_pagar.py          dívidas com pessoas e suas parcelas
  config.py           configurações (PIN do celular)
  relatorio.py        números do relatório mensal e da visão geral
  relatorio_pdf.py    monta o PDF do relatório completo (fpdf2)
routes/             uma tela por arquivo (Flask Blueprints); acesso.py = PIN do celular
templates/          HTML (Jinja2 + Tailwind); _macros.html = peças reaproveitadas
static/             logo e ícones
scripts/            setup_db.py (cria/recria o banco) e seed.py (dados de teste)
tests/              testes automáticos
backups/            cópias de segurança locais (fora do Git)
```

**Regra da casa:** a rota lê o formulário e mostra a tela; o cálculo e as mudanças no banco ficam em `services/`. Assim cada regra existe num lugar só e pode ser testada sem abrir o app.

Para criar uma tela nova: crie `routes/<area>.py` com um Blueprint chamado `bp`, adicione o nome em `routes/__init__.py` e no menu de `templates/base.html`.

## Testes

```bash
python -m unittest -v
```

Os testes usam um banco temporário e nunca tocam no `financas_local.db`.

## Privacidade

O `.gitignore` deixa fora do repositório o banco de dados, os backups e os arquivos `.zip`/`.rar`, porque eles contêm dados financeiros reais. Antes de enviar algo para o Git, confira com `git status` se nenhum desses arquivos aparece.
