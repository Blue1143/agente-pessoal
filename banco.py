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


def listar_materias(caminho, area=None):
    """Lista as matérias, de todas as áreas ou só de uma."""
    sql = "SELECT id, nome, area, descricao, criada_em FROM materias"
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
            "SELECT id, nome, area, descricao, criada_em FROM materias WHERE id = ?",
            (materia_id,),
        ).fetchone()
    return dict(linha) if linha else None


def excluir_materia(caminho, materia_id):
    """Apaga a matéria. Devolve True se algo foi apagado."""
    with abrir(caminho) as conexao:
        cursor = conexao.execute("DELETE FROM materias WHERE id = ?", (materia_id,))
        return cursor.rowcount > 0
