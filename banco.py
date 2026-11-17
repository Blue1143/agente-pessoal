"""Camada de dados: todo o acesso ao SQLite fica neste arquivo.

O resto do aplicativo nunca escreve SQL diretamente; ele chama as funções
daqui (adicionar_materia, listar_materias, ...). Assim, se um dia o
armazenamento mudar, só este arquivo precisa ser alterado.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

# As três áreas de estudo. A ordem aqui é a ordem em que aparecem na tela.
AREAS = ("Administração", "Enfermagem", "Inglês")

LIMITE_NOME = 100
LIMITE_DESCRICAO = 500

# Local padrão do banco: <pasta do projeto>/dados/estudos.db
PASTA_PROJETO = Path(__file__).resolve().parent
CAMINHO_PADRAO = PASTA_PROJETO / "dados" / "estudos.db"


@contextmanager
def abrir(caminho):
    """Abre uma conexão, confirma (commit) se tudo der certo e sempre fecha."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    conexao = sqlite3.connect(caminho)
    conexao.row_factory = sqlite3.Row  # permite ler colunas pelo nome: linha["nome"]
    # Liga as "chaves estrangeiras": apagar um documento apaga suas páginas,
    # e apagar uma matéria apaga seus documentos (ON DELETE CASCADE).
    conexao.execute("PRAGMA foreign_keys = ON")
    try:
        yield conexao
        conexao.commit()
    except Exception:
        conexao.rollback()
        raise
    finally:
        conexao.close()


def inicializar(caminho):
    """Cria a tabela de matérias, caso ainda não exista."""
    lista_areas = ", ".join(f"'{area}'" for area in AREAS)
    with abrir(caminho) as conexao:
        conexao.execute(
            f"""
            CREATE TABLE IF NOT EXISTS materias (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                nome       TEXT NOT NULL CHECK (length(trim(nome)) > 0),
                area       TEXT NOT NULL CHECK (area IN ({lista_areas})),
                descricao  TEXT NOT NULL DEFAULT '',
                criada_em  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
            """
        )
        # Etapa 2: PDFs. "IF NOT EXISTS" faz isso funcionar também em bancos
        # criados na etapa 1: as tabelas novas são acrescentadas sem perder nada.
        conexao.executescript(
            """
            CREATE TABLE IF NOT EXISTS documentos (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                materia_id         INTEGER NOT NULL REFERENCES materias(id) ON DELETE CASCADE,
                nome_original      TEXT NOT NULL,          -- nome que você deu ao arquivo
                arquivo            TEXT NOT NULL UNIQUE,   -- nome salvo em dados/pdfs/
                tamanho_bytes      INTEGER NOT NULL,
                sha256             TEXT NOT NULL,          -- "impressão digital" do arquivo
                total_paginas      INTEGER NOT NULL,
                paginas_com_texto  INTEGER NOT NULL,
                enviado_em         TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_documentos_materia ON documentos(materia_id);

            -- Uma linha por página: é isso que preserva a separação por página.
            CREATE TABLE IF NOT EXISTS paginas (
                documento_id  INTEGER NOT NULL REFERENCES documentos(id) ON DELETE CASCADE,
                numero        INTEGER NOT NULL CHECK (numero >= 1),
                texto         TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (documento_id, numero)
            );
            """
        )


def validar_materia(caminho, nome, area, descricao):
    """Devolve uma lista de mensagens de erro (lista vazia = dados válidos)."""
    erros = []
    if not nome:
        erros.append("Informe o nome da matéria.")
    elif len(nome) > LIMITE_NOME:
        erros.append(f"O nome pode ter no máximo {LIMITE_NOME} caracteres.")
    if area not in AREAS:
        erros.append("Escolha uma área válida.")
    if len(descricao) > LIMITE_DESCRICAO:
        erros.append(f"A descrição pode ter no máximo {LIMITE_DESCRICAO} caracteres.")

    # Evita duas matérias com o mesmo nome na mesma área ("Inglês I" e "inglês i").
    if nome and area in AREAS:
        for materia in listar_materias(caminho, area):
            if materia["nome"].casefold() == nome.casefold():
                erros.append(f"Já existe a matéria “{materia['nome']}” em {area}.")
                break
    return erros


def adicionar_materia(caminho, nome, area, descricao=""):
    """Valida e grava uma nova matéria. Devolve o id criado.

    Lança ValueError com a lista de erros se os dados forem inválidos.
    """
    nome = (nome or "").strip()
    area = (area or "").strip()
    descricao = (descricao or "").strip()

    erros = validar_materia(caminho, nome, area, descricao)
    if erros:
        raise ValueError(erros)

    with abrir(caminho) as conexao:
        # Os "?" são preenchidos pelo SQLite com segurança (evita injeção de SQL).
        cursor = conexao.execute(
            "INSERT INTO materias (nome, area, descricao) VALUES (?, ?, ?)",
            (nome, area, descricao),
        )
        return cursor.lastrowid


# Colunas lidas de uma matéria, incluindo quantos PDFs ela tem.
_COLUNAS_MATERIA = """
    id, nome, area, descricao, criada_em,
    (SELECT COUNT(*) FROM documentos d WHERE d.materia_id = materias.id) AS total_documentos
"""


def listar_materias(caminho, area=None):
    """Lista as matérias, de todas as áreas ou só de uma."""
    sql = f"SELECT {_COLUNAS_MATERIA} FROM materias"
    parametros = ()
    if area:
        sql += " WHERE area = ?"
        parametros = (area,)
    with abrir(caminho) as conexao:
        linhas = conexao.execute(sql, parametros).fetchall()
    materias = [dict(linha) for linha in linhas]
    # Ordena em Python para tratar acentos e maiúsculas/minúsculas de forma natural.
    materias.sort(key=lambda m: (AREAS.index(m["area"]), m["nome"].casefold()))
    return materias


def contar_por_area(caminho):
    """Devolve {"Administração": 2, "Enfermagem": 0, "Inglês": 1}."""
    contagem = {area: 0 for area in AREAS}
    with abrir(caminho) as conexao:
        for linha in conexao.execute("SELECT area, COUNT(*) AS total FROM materias GROUP BY area"):
            contagem[linha["area"]] = linha["total"]
    return contagem


def buscar_materia(caminho, materia_id):
    """Devolve a matéria com esse id, ou None se não existir."""
    with abrir(caminho) as conexao:
        linha = conexao.execute(
            f"SELECT {_COLUNAS_MATERIA} FROM materias WHERE id = ?",
            (materia_id,),
        ).fetchone()
    return dict(linha) if linha else None


def excluir_materia(caminho, materia_id):
    """Apaga a matéria. Devolve True se algo foi apagado."""
    with abrir(caminho) as conexao:
        cursor = conexao.execute("DELETE FROM materias WHERE id = ?", (materia_id,))
        return cursor.rowcount > 0


# ======================================================================
# Documentos (PDFs) — etapa 2
# ======================================================================

def adicionar_documento(caminho, materia_id, nome_original, arquivo, tamanho_bytes, sha256, paginas):
    """Grava o documento e o texto de cada página numa única transação.

    `paginas` é uma lista de textos: paginas[0] é a página 1, e assim por diante.
    Se algo falhar no meio, nada fica gravado pela metade.
    """
    paginas_com_texto = sum(1 for texto in paginas if texto.strip())
    with abrir(caminho) as conexao:
        cursor = conexao.execute(
            """
            INSERT INTO documentos
                (materia_id, nome_original, arquivo, tamanho_bytes, sha256,
                 total_paginas, paginas_com_texto)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (materia_id, nome_original, arquivo, tamanho_bytes, sha256,
             len(paginas), paginas_com_texto),
        )
        documento_id = cursor.lastrowid
        conexao.executemany(
            "INSERT INTO paginas (documento_id, numero, texto) VALUES (?, ?, ?)",
            [(documento_id, numero, texto) for numero, texto in enumerate(paginas, start=1)],
        )
        return documento_id


_COLUNAS_DOCUMENTO = """
    d.id, d.materia_id, d.nome_original, d.arquivo, d.tamanho_bytes, d.sha256,
    d.total_paginas, d.paginas_com_texto, d.enviado_em,
    m.nome AS materia_nome, m.area AS materia_area
"""


def listar_documentos(caminho, materia_id):
    """Documentos de uma matéria, do mais recente para o mais antigo."""
    with abrir(caminho) as conexao:
        linhas = conexao.execute(
            f"""
            SELECT {_COLUNAS_DOCUMENTO}
            FROM documentos d JOIN materias m ON m.id = d.materia_id
            WHERE d.materia_id = ?
            ORDER BY d.enviado_em DESC, d.id DESC
            """,
            (materia_id,),
        ).fetchall()
    return [dict(linha) for linha in linhas]


def buscar_documento(caminho, documento_id):
    """Devolve o documento (com nome e área da matéria) ou None."""
    with abrir(caminho) as conexao:
        linha = conexao.execute(
            f"""
            SELECT {_COLUNAS_DOCUMENTO}
            FROM documentos d JOIN materias m ON m.id = d.materia_id
            WHERE d.id = ?
            """,
            (documento_id,),
        ).fetchone()
    return dict(linha) if linha else None


def buscar_documento_por_hash(caminho, materia_id, sha256):
    """Procura o mesmo arquivo já enviado para esta matéria (evita duplicatas)."""
    with abrir(caminho) as conexao:
        linha = conexao.execute(
            "SELECT id, nome_original FROM documentos WHERE materia_id = ? AND sha256 = ?",
            (materia_id, sha256),
        ).fetchone()
    return dict(linha) if linha else None


def listar_paginas(caminho, documento_id):
    """Lista [{"numero": 1, "texto": "..."}, ...] em ordem de página."""
    with abrir(caminho) as conexao:
        linhas = conexao.execute(
            "SELECT numero, texto FROM paginas WHERE documento_id = ? ORDER BY numero",
            (documento_id,),
        ).fetchall()
    return [dict(linha) for linha in linhas]


def arquivos_da_materia(caminho, materia_id):
    """Nomes dos arquivos em disco que pertencem a uma matéria."""
    with abrir(caminho) as conexao:
        linhas = conexao.execute(
            "SELECT arquivo FROM documentos WHERE materia_id = ?", (materia_id,)
        ).fetchall()
    return [linha["arquivo"] for linha in linhas]


def excluir_documento(caminho, documento_id):
    """Apaga o documento e (pela cascata) suas páginas. Devolve True se apagou."""
    with abrir(caminho) as conexao:
        cursor = conexao.execute("DELETE FROM documentos WHERE id = ?", (documento_id,))
        return cursor.rowcount > 0
