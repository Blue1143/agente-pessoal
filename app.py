"""Servidor web do aplicativo de estudos.

Cada função decorada com @app.get / @app.post é uma "rota": ela responde
quando o navegador acessa aquele endereço. As rotas não falam com o SQLite
diretamente; elas chamam as funções de banco.py.

Para executar:  python app.py   e abra http://127.0.0.1:5000
"""

import os

from flask import Flask, abort, redirect, render_template, request, url_for

import banco

# Mensagens exibidas depois de uma ação (vêm na URL como ?msg=...).
MENSAGENS = {
    "adicionada": "Matéria cadastrada com sucesso.",
    "excluida": "Matéria excluída.",
}


def criar_app(caminho_banco=None):
    """Monta o aplicativo. Os testes passam um banco temporário aqui."""
    app = Flask(__name__)
    # Ordem de escolha do arquivo do banco: parâmetro > variável ESTUDOS_DB > padrão.
    caminho = caminho_banco or os.environ.get("ESTUDOS_DB") or banco.CAMINHO_PADRAO
    app.config["CAMINHO_BANCO"] = caminho
    banco.inicializar(caminho)

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
            mensagem=MENSAGENS.get(request.args.get("msg", "")),
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

    @app.get("/materias/<int:materia_id>/excluir")
    def confirmar_exclusao(materia_id):
        # Só MOSTRA a confirmação; nada é apagado aqui.
        materia = banco.buscar_materia(caminho, materia_id)
        if materia is None:
            abort(404)
        return render_template("confirmar_exclusao.html", materia=materia)

    @app.post("/materias/<int:materia_id>/excluir")
    def excluir(materia_id):
        # Chega aqui apenas quando o usuário clica em "Sim, excluir".
        materia = banco.buscar_materia(caminho, materia_id)
        if materia is None:
            abort(404)
        banco.excluir_materia(caminho, materia_id)
        return redirect(url_for("inicio", area=materia["area"], msg="excluida"))

    @app.errorhandler(404)
    def nao_encontrado(_erro):
        return render_template("nao_encontrado.html"), 404

    return app


if __name__ == "__main__":
    # host 127.0.0.1 = acessível só neste computador.
    criar_app().run(host="127.0.0.1", port=5000)
