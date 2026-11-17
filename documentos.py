"""Tudo sobre arquivos PDF: validar, extrair texto e guardar em disco.

Este módulo NÃO fala com o banco de dados nem com o navegador. Ele recebe os
bytes de um arquivo e devolve o texto de cada página (ou um erro explicando
por que o arquivo foi recusado). Quem junta as peças é o app.py.
"""

import hashlib
import io
import logging
import os
import re
import uuid
from pathlib import Path

from pypdf import PdfReader

# ---------------------------------------------------------------------------
# Limites (documentados no README)
# ---------------------------------------------------------------------------
LIMITE_MB = 20
LIMITE_BYTES = LIMITE_MB * 1024 * 1024
LIMITE_PAGINAS = 500
LIMITE_NOME_ARQUIVO = 150

# O pypdf avisa no terminal sobre pequenos defeitos em PDFs; não precisamos disso.
logging.getLogger("pypdf").setLevel(logging.ERROR)

# Os arquivos são salvos com um nome aleatório: 32 letras/números + ".pdf".
# Nunca usamos o nome enviado pelo usuário como caminho no disco.
_PADRAO_NOME_SALVO = re.compile(r"^[0-9a-f]{32}\.pdf$")


class PdfInvalido(Exception):
    """Erro com uma mensagem amigável, pronta para mostrar na tela."""


# ---------------------------------------------------------------------------
# Validação e extração
# ---------------------------------------------------------------------------
def nome_para_exibir(nome_enviado):
    """Limpa o nome do arquivo enviado (só para mostrar na tela)."""
    # Alguns navegadores mandam o caminho inteiro (ex.: C:\fakepath\apostila.pdf).
    nome = re.split(r"[\\/]", nome_enviado or "")[-1].strip()
    nome = "".join(c for c in nome if c.isprintable())
    if len(nome) > LIMITE_NOME_ARQUIVO:
        nome = nome[: LIMITE_NOME_ARQUIVO - 4] + ".pdf"
    return nome or "documento.pdf"


def validar_envio(nome_enviado, conteudo):
    """Confere nome, tamanho e assinatura do arquivo antes de tentar abri-lo."""
    if not nome_enviado:
        raise PdfInvalido("Escolha um arquivo PDF para enviar.")
    if not nome_enviado.lower().endswith(".pdf"):
        raise PdfInvalido("Apenas arquivos .pdf são aceitos.")
    if len(conteudo) == 0:
        raise PdfInvalido("O arquivo está vazio.")
    if len(conteudo) > LIMITE_BYTES:
        raise PdfInvalido(f"O arquivo passa do limite de {LIMITE_MB} MB.")
    # Todo PDF começa com "%PDF-" (às vezes depois de alguns bytes iniciais).
    # Isso evita aceitar, por exemplo, um .docx renomeado para .pdf.
    if b"%PDF-" not in conteudo[:1024]:
        raise PdfInvalido("O arquivo não é um PDF válido (o conteúdo não é de PDF).")


def _limpar_texto(texto):
    texto = (texto or "").replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    linhas = [linha.rstrip() for linha in texto.split("\n")]
    return "\n".join(linhas).strip()


def pagina_tem_texto(texto):
    """Considera que há texto se existir pelo menos uma letra ou número."""
    return any(c.isalnum() for c in texto)


def extrair_paginas(conteudo):
    """Abre o PDF e devolve uma lista com o texto de cada página.

    lista[0] = texto da página 1, lista[1] = página 2, ...
    Uma página sem texto extraível vira "" (string vazia) — nada é inventado.
    """
    try:
        leitor = PdfReader(io.BytesIO(conteudo))
        if leitor.is_encrypted:
            # Alguns PDFs são "criptografados" sem senha de abertura; tentamos senha vazia.
            try:
                aberto = leitor.decrypt("")
            except Exception:
                aberto = 0
            if not aberto:
                raise PdfInvalido(
                    "Este PDF é protegido por senha. Remova a proteção e envie novamente."
                )
        total = len(leitor.pages)
    except PdfInvalido:
        raise
    except Exception:
        raise PdfInvalido("Não foi possível abrir este PDF. O arquivo pode estar corrompido.")

    if total == 0:
        raise PdfInvalido("O PDF não tem nenhuma página.")
    if total > LIMITE_PAGINAS:
        raise PdfInvalido(f"O PDF tem {total} páginas; o limite é {LIMITE_PAGINAS}.")

    textos = []
    for pagina in leitor.pages:
        try:
            texto = _limpar_texto(pagina.extract_text())
        except Exception:
            texto = ""  # uma página problemática não derruba o documento inteiro
        textos.append(texto if pagina_tem_texto(texto) else "")
    return textos


def calcular_sha256(conteudo):
    """Uma "impressão digital" do arquivo: arquivos idênticos têm o mesmo valor."""
    return hashlib.sha256(conteudo).hexdigest()


# ---------------------------------------------------------------------------
# Arquivos em disco
# ---------------------------------------------------------------------------
def caminho_arquivo(pasta, nome_salvo):
    """Caminho completo de um arquivo salvo, recusando nomes fora do padrão."""
    if not _PADRAO_NOME_SALVO.match(nome_salvo or ""):
        raise ValueError(f"Nome de arquivo inesperado: {nome_salvo!r}")
    return Path(pasta) / nome_salvo


def salvar_arquivo(pasta, conteudo):
    """Grava os bytes com um nome aleatório e devolve esse nome."""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    nome_salvo = uuid.uuid4().hex + ".pdf"
    destino = caminho_arquivo(pasta, nome_salvo)
    temporario = destino.with_suffix(".parcial")
    temporario.write_bytes(conteudo)
    os.replace(temporario, destino)  # só aparece com o nome final quando está completo
    return nome_salvo


def apagar_arquivo(pasta, nome_salvo):
    """Remove o arquivo do disco (sem erro se ele já não existir)."""
    caminho_arquivo(pasta, nome_salvo).unlink(missing_ok=True)
