# agente-pessoal · Meus Estudos

Aplicativo pessoal de estudos para **Administração**, **Enfermagem** e **Inglês**.

**Etapa 1 (atual):** cadastrar, listar e excluir matérias. Os dados ficam salvos no seu computador.

Ainda **não** tem: IA, leitura de PDFs, pesquisa na internet, cronogramas ou revisões. Isso vem nas próximas etapas.

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
3. `pip install` baixa o Flask, a única dependência.

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

Os testes usam um banco temporário e não mexem nos seus dados.

---

## Onde ficam os dados

Ficam no arquivo `dados/estudos.db`, um banco SQLite criado sozinho na primeira execução.

- **Backup:** feche o aplicativo e copie esse arquivo.
- **Começar do zero:** feche o aplicativo e apague esse arquivo.
- **Outro local (opcional):** defina a variável `ESTUDOS_DB` com o caminho desejado antes de rodar `python app.py`. Por exemplo:

```bash
ESTUDOS_DB=/caminho/para/meu.db python app.py
```

A pasta `dados/` está no `.gitignore`. Assim, se você usar Git, seus dados pessoais não vão para o repositório.

---

## Como o projeto está organizado

| Arquivo | Função |
|---|---|
| `app.py` | Servidor web. Define as **rotas** (endereços) e decide o que mostrar. |
| `banco.py` | Tudo que lê e grava no SQLite, incluindo a validação dos dados. |
| `templates/base.html` | Moldura comum a todas as páginas (cabeçalho). |
| `templates/index.html` | Página principal: abas das áreas, formulário e lista. |
| `templates/confirmar_exclusao.html` | Pergunta "Excluir matéria?" antes de apagar. |
| `templates/nao_encontrado.html` | Página de erro 404. |
| `static/estilo.css` | Aparência (cores, layout, modo escuro). |
| `testes/test_materias.py` | Testes automáticos. |
| `requirements.txt` | Lista de dependências (só Flask). |

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

---

## Próximas etapas (planejadas)

- Consultar PDFs com referência de página
- Pesquisar na internet
- Cronogramas e revisões
