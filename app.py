"""Servidor web do aplicativo de estudos.

Cada função decorada com @app.get / @app.post é uma "rota": ela responde
quando o navegador acessa aquele endereço. As rotas não falam com o SQLite
diretamente (isso é com banco.py) nem leem PDFs (isso é com documentos.py).

Para executar:  python app.py   e abra http://127.0.0.1:5000
"""

import os
from pathlib import Path

from flask import Flask, abort, redirect, render_template, request, send_file, url_for

import banco
import documentos

# Mensagens exibidas depois de uma ação (vêm na URL como ?msg=...).
MENSAGENS = {
    "adicionada": "Matéria cadastrada com sucesso.",
    "excluida": "Matéria excluída.",
    "enviado": "PDF enviado e texto extraído.",
    "enviado_sem_texto": "PDF enviado, mas nenhum texto pôde ser extraído.",
    "documento_excluido": "Documento excluído.",
}


def formatar_tamanho(num_bytes):
    """1536 -> '1,5 KB' (formato brasileiro, com vírgula)."""
    for unidade in ("bytes", "KB", "MB"):
        if num_bytes < 1024 or unidade == "MB":
            texto = f"{num_bytes:.0f}" if unidade == "bytes" else f"{num_bytes:.1f}"
            return f"{texto.replace('.', ',')} {unidade}"
        num_bytes /= 1024


def criar_app(caminho_banco=None, pasta_pdfs=None):
    """Monta o aplicativo. Os testes passam um banco temporário aqui."""
    app = Flask(__name__)
    # Ordem de escolha do arquivo do banco: parâmetro > variável ESTUDOS_DB > padrão.
    caminho = Path(caminho_banco or os.environ.get("ESTUDOS_DB") or banco.CAMINHO_PADRAO)
    # Os PDFs ficam numa pasta "pdfs" ao lado do banco (padrão: dados/pdfs/).
    pasta = Path(pasta_pdfs or caminho.parent / "pdfs")
    app.config["CAMINHO_BANCO"] = caminho
    app.config["PASTA_PDFS"] = pasta
    # Limite do pedido inteiro: o PDF + uma folga para o resto do formulário.
    # Acima disso o Flask recusa antes mesmo de ler o arquivo (erro 413).
    app.config["MAX_CONTENT_LENGTH"] = documentos.LIMITE_BYTES + 1024 * 1024
    banco.inicializar(caminho)
    app.jinja_env.filters["tamanho"] = formatar_tamanho

    def mensagem_da_url():
        return MENSAGENS.get(request.args.get("msg", ""))

    # ------------------------------------------------------------------
    # Matérias (etapa 1)
    # ------------------------------------------------------------------
    def pagina_inicial(area=None, erros=None, formulario=None, status=200):
        """Desenha a página principal (lista + formulário)."""
        html = render_template(
            "index.html",
            areas=banco.AREAS,
            area_atual=area,
            materias=banco.listar_materias(caminho, area),
            contagem=banco.contar_por_area(caminho),
            erros=erros or [],
            formulario=formulario or {"nome": "", "area": area or "", "descricao": ""},
            mensagem=mensagem_da_url(),
            limite_nome=banco.LIMITE_NOME,
            limite_descricao=banco.LIMITE_DESCRICAO,
        )
        return html, status

    @app.get("/")
    def inicio():
        area = request.args.get("area")
        if area not in banco.AREAS:
            area = None  # sem filtro: mostra todas as áreas
        return pagina_inicial(area)

    @app.post("/materias")
    def cadastrar():
        formulario = {
            "nome": request.form.get("nome", ""),
            "area": request.form.get("area", ""),
            "descricao": request.form.get("descricao", ""),
        }
        try:
            banco.adicionar_materia(caminho, **formulario)
        except ValueError as erro:
            # Dados inválidos: mostra a página de novo, com os erros e o que foi digitado.
            area = formulario["area"] if formulario["area"] in banco.AREAS else None
            return pagina_inicial(area, erros=erro.args[0], formulario=formulario, status=400)
        # Deu certo: redireciona (evita cadastrar de novo se a página for recarregada).
        return redirect(url_for("inicio", area=formulario["area"].strip(), msg="adicionada"))

    def materia_ou_404(materia_id):
        materia = banco.buscar_materia(caminho, materia_id)
        if materia is None:
            abort(404)
        return materia

    @app.get("/materias/<int:materia_id>/excluir")
    def confirmar_exclusao(materia_id):
        # Só MOSTRA a confirmação; nada é apagado aqui.
        return render_template("confirmar_exclusao.html", materia=materia_ou_404(materia_id))

    @app.post("/materias/<int:materia_id>/excluir")
    def excluir(materia_id):
        # Chega aqui apenas quando o usuário clica em "Sim, excluir".
        materia = materia_ou_404(materia_id)
        arquivos = banco.arquivos_da_materia(caminho, materia_id)
        banco.excluir_materia(caminho, materia_id)  # a cascata apaga documentos e páginas
        for nome_salvo in arquivos:
            documentos.apagar_arquivo(pasta, nome_salvo)
        return redirect(url_for("inicio", area=materia["area"], msg="excluida"))

    # ------------------------------------------------------------------
    # Documentos PDF (etapa 2)
    # ------------------------------------------------------------------
    def pagina_materia(materia, erro=None, status=200):
        html = render_template(
            "materia.html",
            materia=materia,
            documentos=banco.listar_documentos(caminho, materia["id"]),
            erro=erro,
            mensagem=mensagem_da_url(),
            limite_mb=documentos.LIMITE_MB,
            limite_paginas=documentos.LIMITE_PAGINAS,
        )
        return html, status

    @app.get("/materias/<int:materia_id>")
    def ver_materia(materia_id):
        return pagina_materia(materia_ou_404(materia_id))

    @app.post("/materias/<int:materia_id>/documentos")
    def enviar_documento(materia_id):
        materia = materia_ou_404(materia_id)
        enviado = request.files.get("arquivo")
        nome_enviado = enviado.filename if enviado else ""
        conteudo = b""
        if enviado:
            conteudo = enviado.read()
            enviado.close()  # libera o arquivo temporário criado pelo Flask

        try:
            documentos.validar_envio(nome_enviado, conteudo)
            sha256 = documentos.calcular_sha256(conteudo)
            repetido = banco.buscar_documento_por_hash(caminho, materia_id, sha256)
            if repetido:
                raise documentos.PdfInvalido(
                    f"Este arquivo já foi enviado para esta matéria como “{repetido['nome_original']}”."
                )
            paginas = documentos.extrair_paginas(conteudo)
        except documentos.PdfInvalido as erro:
            return pagina_materia(materia, erro=str(erro), status=400)

        # 1) grava o arquivo no disco; 2) grava os dados no banco.
        # Se o passo 2 falhar, desfaz o passo 1 para não deixar arquivo órfão.
        nome_salvo = documentos.salvar_arquivo(pasta, conteudo)
        try:
            documento_id = banco.adicionar_documento(
                caminho, materia_id, documentos.nome_para_exibir(nome_enviado),
                nome_salvo, len(conteudo), sha256, paginas,
            )
        except Exception:
            documentos.apagar_arquivo(pasta, nome_salvo)
            raise
        tem_texto = any(paginas)
        return redirect(url_for("ver_documento", documento_id=documento_id,
                                msg="enviado" if tem_texto else "enviado_sem_texto"))

    def documento_ou_404(documento_id):
        documento = banco.buscar_documento(caminho, documento_id)
        if documento is None:
            abort(404)
        return documento

    @app.get("/documentos/<int:documento_id>")
    def ver_documento(documento_id):
        documento = documento_ou_404(documento_id)
        return render_template(
            "documento.html",
            documento=documento,
            paginas=banco.listar_paginas(caminho, documento_id),
            mensagem=mensagem_da_url(),
        )

    @app.get("/documentos/<int:documento_id>/arquivo")
    def abrir_arquivo(documento_id):
        """Entrega o PDF original para o navegador abrir (ex.: .../arquivo#page=3)."""
        documento = documento_ou_404(documento_id)
        arquivo = documentos.caminho_arquivo(pasta, documento["arquivo"])
        if not arquivo.exists():
            abort(404)
        return send_file(arquivo, mimetype="application/pdf",
                         download_name=documento["nome_original"])

    @app.get("/documentos/<int:documento_id>/excluir")
    def confirmar_exclusao_documento(documento_id):
        return render_template("confirmar_exclusao_documento.html",
                               documento=documento_ou_404(documento_id))

    @app.post("/documentos/<int:documento_id>/excluir")
    def excluir_documento(documento_id):
        documento = documento_ou_404(documento_id)
        banco.excluir_documento(caminho, documento_id)  # apaga também as páginas
        documentos.apagar_arquivo(pasta, documento["arquivo"])
        return redirect(url_for("ver_materia", materia_id=documento["materia_id"],
                                msg="documento_excluido"))

    # ------------------------------------------------------------------
    # Páginas de erro
    # ------------------------------------------------------------------
    @app.errorhandler(404)
    def nao_encontrado(_erro):
        return render_template(
            "erro.html", titulo="Página não encontrada",
            texto="O item pode já ter sido excluído.",
        ), 404

    @app.errorhandler(413)
    def grande_demais(_erro):
        materia_id = (request.view_args or {}).get("materia_id")
        return render_template(
            "erro.html", titulo="Arquivo grande demais",
            texto=f"O limite para cada PDF é de {documentos.LIMITE_MB} MB.",
            voltar=url_for("ver_materia", materia_id=materia_id) if materia_id else None,
        ), 413

    return app


if __name__ == "__main__":
    # host 127.0.0.1 = acessível só neste computador.
    criar_app().run(host="127.0.0.1", port=5000)
