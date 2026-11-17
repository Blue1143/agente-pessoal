"""Testes dos documentos PDF. Execute com:  python -m unittest discover -s testes -v

Os PDFs usados aqui são GERADOS pelo próprio teste (função criar_pdf), então
nenhum arquivo PDF precisa ficar guardado no repositório.
"""

import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import banco  # noqa: E402
import documentos  # noqa: E402
from app import criar_app  # noqa: E402


def criar_pdf(paginas):
    """Monta um PDF mínimo. `paginas` é uma lista de textos;
    None cria uma página SEM texto (como um PDF digitalizado)."""
    corpo = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    }
    kids, proximo = [], 4
    for texto in paginas:
        pid, cid = proximo, proximo + 1
        proximo += 2
        kids.append(f"{pid} 0 R")
        fluxo = b""
        if texto is not None:
            partes = [b"BT /F1 12 Tf 72 720 Td 14 TL"]
            for linha in texto.split("\n"):
                linha = linha.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
                partes.append(b"(" + linha.encode("cp1252") + b") Tj T*")
            partes.append(b"ET")
            fluxo = b"\n".join(partes)
        corpo[pid] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {cid} 0 R >>"
        ).encode()
        corpo[cid] = b"<< /Length %d >>\nstream\n" % len(fluxo) + fluxo + b"\nendstream"
    corpo[2] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(paginas)} >>".encode()

    saida, posicoes = bytearray(b"%PDF-1.4\n"), {}
    for numero in range(1, proximo):
        posicoes[numero] = len(saida)
        saida += b"%d 0 obj\n" % numero + corpo[numero] + b"\nendobj\n"
    inicio_xref = len(saida)
    saida += b"xref\n0 %d\n0000000000 65535 f \n" % proximo
    for numero in range(1, proximo):
        saida += b"%010d 00000 n \n" % posicoes[numero]
    saida += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (proximo, inicio_xref)
    return bytes(saida)


class TestDocumentos(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.caminho = Path(self.pasta.name) / "teste.db"
        self.pasta_pdfs = Path(self.pasta.name) / "pdfs"
        self.cliente = criar_app(self.caminho).test_client()
        self.materia_id = banco.adicionar_materia(self.caminho, "Bioestatística", "Enfermagem")

    def tearDown(self):
        self.pasta.cleanup()

    def enviar(self, conteudo, nome="apostila.pdf", materia_id=None):
        materia_id = materia_id or self.materia_id
        resposta = self.cliente.post(
            f"/materias/{materia_id}/documentos",
            data={"arquivo": (io.BytesIO(conteudo), nome)},
            content_type="multipart/form-data",
        )
        # O cliente de testes guarda corpos grandes num arquivo temporário; fechamos aqui.
        resposta.request.environ["wsgi.input"].close()
        return resposta

    def documentos(self, materia_id=None):
        return banco.listar_documentos(self.caminho, materia_id or self.materia_id)

    def arquivos_no_disco(self):
        return sorted(self.pasta_pdfs.glob("*")) if self.pasta_pdfs.exists() else []

    # --- Envio e extração ----------------------------------------------
    def test_envio_extrai_texto_separado_por_pagina(self):
        pdf = criar_pdf(["Introdução à média", "Mediana e moda\nsegunda linha", "Variância (s2)"])
        resposta = self.enviar(pdf, "Estatística.pdf")
        self.assertEqual(resposta.status_code, 302)

        [doc] = self.documentos()
        self.assertEqual(doc["nome_original"], "Estatística.pdf")
        self.assertEqual(doc["total_paginas"], 3)
        self.assertEqual(doc["paginas_com_texto"], 3)
        self.assertEqual(doc["tamanho_bytes"], len(pdf))

        paginas = banco.listar_paginas(self.caminho, doc["id"])
        self.assertEqual([p["numero"] for p in paginas], [1, 2, 3])
        self.assertIn("Introdução à média", paginas[0]["texto"])
        self.assertIn("Mediana e moda", paginas[1]["texto"])
        self.assertIn("segunda linha", paginas[1]["texto"])
        self.assertNotIn("Mediana", paginas[0]["texto"])  # nada vaza para outra página

        # O arquivo foi salvo com nome aleatório (não o nome enviado).
        [arquivo] = self.arquivos_no_disco()
        self.assertRegex(arquivo.name, r"^[0-9a-f]{32}\.pdf$")
        self.assertEqual(arquivo.read_bytes(), pdf)

    def test_visualizacao_mostra_numero_e_texto_de_cada_pagina(self):
        self.enviar(criar_pdf(["Primeira página aqui", "Segunda página aqui"]))
        doc_id = self.documentos()[0]["id"]
        html = self.cliente.get(f"/documentos/{doc_id}").get_data(as_text=True)
        self.assertIn('id="pagina-1"', html)
        self.assertIn("Página 2", html)
        self.assertIn("Primeira página aqui", html)
        self.assertIn("Segunda página aqui", html)
        self.assertIn("#page=2", html)  # link para abrir o PDF na página certa

    def test_lista_de_documentos_na_pagina_da_materia(self):
        self.enviar(criar_pdf(["a1"]), "Aula 1.pdf")
        self.enviar(criar_pdf(["a2"]), "Aula 2.pdf")
        html = self.cliente.get(f"/materias/{self.materia_id}").get_data(as_text=True)
        self.assertIn("Aula 1.pdf", html)
        self.assertIn("Aula 2.pdf", html)
        self.assertIn("Documentos (2)", html)
        # Documento de uma matéria não aparece em outra.
        outra = banco.adicionar_materia(self.caminho, "Leitura", "Inglês")
        html_outra = self.cliente.get(f"/materias/{outra}").get_data(as_text=True)
        self.assertNotIn("Aula 1.pdf", html_outra)
        # A página inicial mostra a contagem.
        self.assertIn("2 PDFs", self.cliente.get("/").get_data(as_text=True))

    # --- PDFs sem texto (digitalizados) --------------------------------
    def test_pdf_sem_texto_mostra_aviso_de_ocr_sem_inventar_conteudo(self):
        resposta = self.enviar(criar_pdf([None, None]))
        self.assertEqual(resposta.status_code, 302)
        self.assertIn("msg=enviado_sem_texto", resposta.location)  # não diz "texto extraído"
        [doc] = self.documentos()
        self.assertEqual(doc["paginas_com_texto"], 0)
        paginas = banco.listar_paginas(self.caminho, doc["id"])
        self.assertTrue(all(p["texto"] == "" for p in paginas))

        html = self.cliente.get(f"/documentos/{doc['id']}").get_data(as_text=True)
        self.assertIn("não tem texto extraível", html)
        self.assertIn("OCR", html)
        self.assertNotIn('class="texto-pagina"', html)

    def test_pdf_misto_marca_so_as_paginas_sem_texto(self):
        self.enviar(criar_pdf(["Página com texto", None]))
        doc = self.documentos()[0]
        self.assertEqual(doc["paginas_com_texto"], 1)
        html = self.cliente.get(f"/documentos/{doc['id']}").get_data(as_text=True)
        self.assertIn("Página com texto", html)
        self.assertIn("Sem texto extraível nesta página", html)

    # --- Validação -----------------------------------------------------
    def test_arquivos_invalidos_sao_recusados_e_nada_e_gravado(self):
        casos = {
            "sem arquivo": (b"", ""),
            "extensão errada": (criar_pdf(["x"]), "apostila.docx"),
            "arquivo vazio": (b"", "vazio.pdf"),
            "não é PDF": (b"PK\x03\x04 isto e um zip renomeado", "falso.pdf"),
            "PDF corrompido": (b"%PDF-1.4\n" + b"lixo" * 100, "quebrado.pdf"),
        }
        for descricao, (conteudo, nome) in casos.items():
            with self.subTest(descricao):
                if descricao == "sem arquivo":
                    resposta = self.cliente.post(f"/materias/{self.materia_id}/documentos", data={})
                else:
                    resposta = self.enviar(conteudo, nome)
                self.assertEqual(resposta.status_code, 400)
                self.assertIn('class="aviso erro"', resposta.get_data(as_text=True))
        self.assertEqual(self.documentos(), [])
        self.assertEqual(self.arquivos_no_disco(), [])

    def test_pdf_protegido_por_senha_e_recusado(self):
        from pypdf import PdfReader, PdfWriter

        escritor = PdfWriter(clone_from=PdfReader(io.BytesIO(criar_pdf(["segredo"]))))
        escritor.encrypt(user_password="senha-de-teste", algorithm="RC4-128")
        saida = io.BytesIO()
        escritor.write(saida)
        resposta = self.enviar(saida.getvalue())
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("protegido por senha", resposta.get_data(as_text=True))

    def test_limite_de_tamanho(self):
        # Um pouco acima de 20 MB: recusado pela validação do app.
        grande = criar_pdf(["x"]) + b"0" * documentos.LIMITE_BYTES
        resposta = self.enviar(grande)
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("limite de 20 MB", resposta.get_data(as_text=True))
        # Muito acima: recusado pelo Flask antes de ler o arquivo (413).
        enorme = b"%PDF-" + b"0" * (documentos.LIMITE_BYTES + 2 * 1024 * 1024)
        resposta = self.enviar(enorme)
        self.assertEqual(resposta.status_code, 413)
        self.assertIn("Arquivo grande demais", resposta.get_data(as_text=True))
        self.assertEqual(self.documentos(), [])

    def test_limite_de_paginas(self):
        resposta = self.enviar(criar_pdf(["p"] * (documentos.LIMITE_PAGINAS + 1)))
        self.assertEqual(resposta.status_code, 400)
        self.assertIn(f"o limite é {documentos.LIMITE_PAGINAS}", resposta.get_data(as_text=True))

    def test_mesmo_arquivo_duas_vezes_na_mesma_materia_e_recusado(self):
        pdf = criar_pdf(["igual"])
        self.enviar(pdf, "original.pdf")
        resposta = self.enviar(pdf, "copia.pdf")
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("já foi enviado", resposta.get_data(as_text=True))
        # Em outra matéria pode.
        outra = banco.adicionar_materia(self.caminho, "Reading", "Inglês")
        self.assertEqual(self.enviar(pdf, "copia.pdf", outra).status_code, 302)

    def test_nome_salvo_nao_permite_sair_da_pasta(self):
        for nome in ("../app.py", "x.pdf", "/etc/passwd"):
            with self.subTest(nome), self.assertRaises(ValueError):
                documentos.caminho_arquivo(self.pasta_pdfs, nome)

    def test_conteudo_do_pdf_e_escapado_no_html(self):
        self.enviar(criar_pdf(["<script>alert(1)</script>"]), "<b>nome</b>.pdf")
        doc_id = self.documentos()[0]["id"]
        html = self.cliente.get(f"/documentos/{doc_id}").get_data(as_text=True)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertNotIn("<b>nome</b>", html)

    # --- Arquivo original ----------------------------------------------
    def test_abrir_pdf_original(self):
        pdf = criar_pdf(["original"])
        self.enviar(pdf)
        doc_id = self.documentos()[0]["id"]
        resposta = self.cliente.get(f"/documentos/{doc_id}/arquivo")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.mimetype, "application/pdf")
        self.assertEqual(resposta.data, pdf)
        resposta.close()

    # --- Persistência --------------------------------------------------
    def test_documentos_continuam_apos_reiniciar(self):
        self.enviar(criar_pdf(["Texto persistente", "Outra página"]), "Aula.pdf")
        del self.cliente

        novo = criar_app(self.caminho).test_client()
        html = novo.get(f"/materias/{self.materia_id}").get_data(as_text=True)
        self.assertIn("Aula.pdf", html)
        doc_id = self.documentos()[0]["id"]
        html = novo.get(f"/documentos/{doc_id}").get_data(as_text=True)
        self.assertIn("Texto persistente", html)
        self.assertIn("Página 2", html)
        resposta = novo.get(f"/documentos/{doc_id}/arquivo")
        self.assertEqual(resposta.status_code, 200)
        resposta.close()

    # --- Exclusão ------------------------------------------------------
    def test_exclusao_de_documento_pede_confirmacao_e_apaga_tudo(self):
        self.enviar(criar_pdf(["a", "b"]))
        doc_id = self.documentos()[0]["id"]

        resposta = self.cliente.get(f"/documentos/{doc_id}/excluir")
        self.assertIn("Excluir documento?", resposta.get_data(as_text=True))
        self.assertEqual(len(self.documentos()), 1)  # só ver a confirmação não apaga
        self.assertEqual(len(self.arquivos_no_disco()), 1)

        resposta = self.cliente.post(f"/documentos/{doc_id}/excluir")
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(self.documentos(), [])
        self.assertEqual(banco.listar_paginas(self.caminho, doc_id), [])
        self.assertEqual(self.arquivos_no_disco(), [])
        self.assertEqual(self.cliente.get(f"/documentos/{doc_id}").status_code, 404)

    def test_excluir_materia_apaga_seus_documentos_e_arquivos(self):
        self.enviar(criar_pdf(["um"]), "1.pdf")
        self.enviar(criar_pdf(["dois"]), "2.pdf")
        doc_ids = [d["id"] for d in self.documentos()]

        confirmacao = self.cliente.get(f"/materias/{self.materia_id}/excluir").get_data(as_text=True)
        self.assertIn("2 PDFs desta matéria também serão excluídos", confirmacao)

        self.cliente.post(f"/materias/{self.materia_id}/excluir")
        self.assertEqual(self.arquivos_no_disco(), [])
        for doc_id in doc_ids:
            self.assertIsNone(banco.buscar_documento(self.caminho, doc_id))
            self.assertEqual(banco.listar_paginas(self.caminho, doc_id), [])


if __name__ == "__main__":
    unittest.main()
