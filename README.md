# agente-pessoal · Meus Estudos

Aplicativo pessoal de estudos para **Administração**, **Enfermagem** e **Inglês**.

- **Etapa 1:** cadastrar, listar e excluir matérias.
- **Etapa 2 (atual):** enviar PDFs para cada matéria, ler o texto extraído **página por página** e excluir documentos.

Tudo fica salvo no seu computador.

Ainda **não** tem: IA, OCR (leitura de PDFs digitalizados), pesquisa na internet, cronogramas ou revisões.

---

## Requisitos

- **Python 3.10 ou mais novo.** Para conferir, rode `python3 --version` (no Windows, `py --version`).
- Um navegador (Chrome, Firefox, Edge…).

Não há serviços pagos, contas ou chaves de acesso.

---

## Instalação (só na primeira vez)

Abra o terminal **dentro da pasta do projeto** e rode os comandos abaixo.

### Linux / macOS

```bash
python3 -m venv .venv
```

```bash
source .venv/bin/activate
```

```bash
pip install -r requirements.txt
```

### Windows (PowerShell)

```powershell
py -m venv .venv
```

```powershell
.venv\Scripts\Activate.ps1
```

```powershell
pip install -r requirements.txt
```

> Se o PowerShell bloquear a ativação, rode uma vez
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` e tente de novo.

O que esses comandos fazem:
1. `venv` cria a pasta `.venv`, um "Python particular" deste projeto.
2. `activate` passa a usar esse Python neste terminal. O prompt mostra `(.venv)`.
3. `pip install` baixa as duas dependências: **Flask** (o servidor web) e **pypdf** (leitura de PDFs).

> **Já tinha instalado a etapa 1?** Ative o ambiente e rode `pip install -r requirements.txt`
> de novo, para instalar o pypdf. Seu banco de dados é atualizado sozinho na primeira
> execução, e as matérias já cadastradas continuam lá.

---

## Executar o aplicativo

Toda vez que for usar, ative o ambiente e inicie o servidor:

### Linux / macOS

```bash
source .venv/bin/activate
```

```bash
python app.py
```

### Windows (PowerShell)

```powershell
.venv\Scripts\Activate.ps1
```

```powershell
python app.py
```

Depois abra **http://127.0.0.1:5000** no navegador.
Para parar, volte ao terminal e aperte **Ctrl + C**.

O aplicativo só aceita conexões do seu próprio computador.

> Ao iniciar, o Flask mostra o aviso *"This is a development server"*. Para uso
> pessoal no seu próprio computador isso é normal e pode ser ignorado.

---

## Rodar os testes automáticos

Com o ambiente ativado:

```bash
python -m unittest discover -s testes -v
```

Os testes usam um banco temporário e não mexem nos seus dados. Os PDFs usados nos testes são
gerados pelo próprio código, então nenhum PDF fica guardado no repositório.

---

## Documentos PDF

Clique no nome de uma matéria para abrir a página dela. Lá você envia PDFs e vê a lista de documentos.

### Limites e validações

| Regra | Valor |
|---|---|
| Tamanho máximo por arquivo | **20 MB** |
| Número máximo de páginas | **500** |
| Extensão aceita | `.pdf` |

Arquivos recusados, com uma mensagem explicando o motivo:
- arquivos que não são PDF de verdade (por exemplo, um `.docx` renomeado para `.pdf`);
- arquivos vazios ou corrompidos;
- PDFs protegidos por senha;
- PDFs acima dos limites;
- o mesmo arquivo enviado duas vezes para a mesma matéria.

Os limites ficam no início de `documentos.py` (`LIMITE_MB` e `LIMITE_PAGINAS`).

### Como o texto é mostrado

O texto é extraído **uma vez, no envio**, e salvo **separado por página**. Ao abrir um documento:
- cada página aparece num bloco com o título "Página N";
- a barra "Ir para a página" pula direto para qualquer página;
- o link "ver no PDF ↗" abre o PDF original **naquela página**. Isso funciona nos navegadores que respeitam o `#page=N` no endereço, como o Chrome, o Edge e o Firefox.

### PDFs digitalizados (sem texto)

Alguns PDFs são só **imagens** das páginas: escaneados ou fotografados. Neles não existe texto digital para extrair.

- Se **nenhuma** página tiver texto, o aplicativo avisa que o documento **precisaria de OCR** (reconhecimento óptico de caracteres), recurso que ainda não existe aqui.
- Se só **algumas** páginas estiverem sem texto, elas aparecem marcadas.

O aplicativo **nunca inventa** o conteúdo dessas páginas. O PDF original fica guardado e pode ser aberto normalmente.

---

## Onde ficam os dados

Tudo fica dentro da pasta `dados/`, criada sozinha na primeira execução:

| Caminho | Conteúdo |
|---|---|
| `dados/estudos.db` | Banco SQLite: matérias, dados dos documentos e o texto de cada página. |
| `dados/pdfs/` | Os PDFs enviados, guardados com um nome aleatório (ex.: `3f9a…c1.pdf`). O nome original fica no banco. |

- **Backup:** feche o aplicativo e copie a pasta `dados/` **inteira**. Banco e PDFs precisam andar juntos.
- **Começar do zero:** feche o aplicativo e apague a pasta `dados/`.
- **Outro local (opcional):** defina a variável `ESTUDOS_DB` com o caminho do banco antes de rodar `python app.py`. Os PDFs vão para uma pasta `pdfs/` ao lado dele. Por exemplo:

```bash
ESTUDOS_DB=/caminho/para/meu.db python app.py
```

A pasta `dados/` e qualquer arquivo `*.pdf` estão no `.gitignore`. Assim, seus dados pessoais e seus PDFs não vão para o GitHub.

---

## Como o projeto está organizado

| Arquivo | Função |
|---|---|
| `app.py` | Servidor web. Define as **rotas** (endereços) e decide o que mostrar. |
| `banco.py` | Tudo que lê e grava no SQLite (matérias, documentos, páginas), incluindo a validação das matérias. |
| `documentos.py` | Tudo sobre PDFs: valida o arquivo, extrai o texto de cada página e guarda/apaga o arquivo em disco. Não usa banco. |
| `templates/base.html` | Moldura comum a todas as páginas (cabeçalho). |
| `templates/index.html` | Página principal: abas das áreas, formulário e lista. |
| `templates/confirmar_exclusao.html` | Pergunta "Excluir matéria?" antes de apagar e avisa quantos PDFs irão junto. |
| `templates/materia.html` | Página da matéria: envio de PDF e lista de documentos. |
| `templates/documento.html` | Texto extraído, página por página (ou o aviso de OCR). |
| `templates/confirmar_exclusao_documento.html` | Pergunta "Excluir documento?" antes de apagar. |
| `templates/erro.html` | Páginas de erro (não encontrado, arquivo grande demais). |
| `static/estilo.css` | Aparência (cores, layout, modo escuro). |
| `testes/test_materias.py` | Testes das matérias. |
| `testes/test_documentos.py` | Testes dos PDFs (geram PDFs de teste na hora). |
| `requirements.txt` | Lista de dependências (Flask e pypdf). |

### O caminho dos dados: cadastrando "Anatomia" em Enfermagem

1. **Navegador.** Você preenche o formulário de `index.html` e clica em *Cadastrar matéria*. O navegador envia um `POST /materias` com `nome=Anatomia`, `area=Enfermagem` e `descricao=...`.
2. **`app.py`, função `cadastrar()`.** Lê os campos de `request.form` e chama `banco.adicionar_materia(...)`.
3. **`banco.py`, função `adicionar_materia()`.**
   - Remove espaços extras.
   - Chama `validar_materia()`: confere se há nome, se a área é uma das três, se o tamanho está dentro do limite e se não há nome repetido na mesma área.
   - Se houver erro, lança `ValueError`. O `app.py` captura o erro e mostra a página de novo com as mensagens, mantendo o que você digitou.
   - Se estiver tudo certo, executa `INSERT INTO materias ... VALUES (?, ?, ?)` no arquivo `dados/estudos.db`.
4. **`app.py` de novo.** Responde com um *redirecionamento* para `/?area=Enfermagem&msg=adicionada`. Isso evita cadastrar a mesma matéria duas vezes se você recarregar a página.
5. **`app.py`, função `inicio()`.** Chama `banco.listar_materias(...)`, que executa um `SELECT`, e entrega a lista ao `index.html`, que monta o HTML.
6. **Navegador.** Mostra "Matéria cadastrada com sucesso." e a lista atualizada.

A exclusão segue o mesmo caminho, em dois passos:
- O botão *Excluir* faz um `GET`, que **só mostra** a página de confirmação.
- O botão *Sim, excluir* faz um `POST`, e só então o `DELETE` é executado no banco.

Como o banco é um arquivo, fechar e abrir o aplicativo não apaga nada.

### O caminho de um PDF: enviando "Apostila.pdf" para a matéria Anatomia

1. **Navegador.** Na página da matéria (`materia.html`), você escolhe o arquivo e clica em *Enviar*. O formulário usa `enctype="multipart/form-data"`, o formato que permite mandar arquivos, e faz um `POST /materias/1/documentos`.
2. **Flask.** Se o pedido passar de ~21 MB, ele é recusado antes mesmo de ser lido, e aparece a página "Arquivo grande demais".
3. **`app.py`, função `enviar_documento()`.** Lê os bytes do arquivo e chama:
   - `documentos.validar_envio()`: confere a extensão `.pdf`, se o arquivo não está vazio, o limite de 20 MB e se o conteúdo começa com `%PDF-`, a "assinatura" de todo PDF;
   - `documentos.calcular_sha256()` e `banco.buscar_documento_por_hash()`: confere se esse mesmo arquivo já foi enviado para a matéria;
   - `documentos.extrair_paginas()`: o pypdf abre o PDF, recusa os protegidos por senha e os com mais de 500 páginas, e devolve **uma lista com o texto de cada página**. Página sem texto vira `""`, nunca um texto inventado.
   - Se algo falhar, a página da matéria volta com a mensagem de erro, e nada é gravado.
4. **Gravação, em duas partes:**
   - `documentos.salvar_arquivo()` grava o PDF em `dados/pdfs/` com um **nome aleatório**. O nome que você deu nunca vira caminho no disco, o que evita problemas com nomes estranhos.
   - `banco.adicionar_documento()` grava, numa única transação, uma linha em `documentos` e uma linha em `paginas` **para cada página** (`numero` + `texto`).
   - Se a gravação no banco falhar, o arquivo é apagado, para não sobrar arquivo órfão.
5. **Redirecionamento** para `/documentos/7`. A função `ver_documento()` busca o documento e as páginas (`SELECT ... ORDER BY numero`), e o `documento.html` mostra cada página com seu número.

**Exclusão de documento:**
- *Excluir* (`GET`) só mostra a confirmação.
- *Sim, excluir* (`POST`) apaga a linha em `documentos`. As páginas vão junto, pela regra `ON DELETE CASCADE` do banco. Depois o app apaga o arquivo em `dados/pdfs/`.
- Excluir uma **matéria** apaga também todos os PDFs dela, e a página de confirmação avisa quantos são.

---

## Próximas etapas (planejadas)

- Pesquisar dentro do texto dos PDFs, com a referência de página
- OCR para PDFs digitalizados
- Pesquisar na internet
- Cronogramas e revisões
