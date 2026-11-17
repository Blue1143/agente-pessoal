"""Testes automáticos. Execute com:  python -m unittest discover -s testes -v

Cada teste usa um banco temporário, então seus dados reais nunca são tocados.
"""

import sys
import tempfile
import unittest
from pathlib import Path

# Permite importar app.py e banco.py que estão na pasta acima.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import banco  # noqa: E402
from app import criar_app  # noqa: E402


class TestMaterias(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.caminho = Path(self.pasta.name) / "teste.db"
        self.cliente = criar_app(self.caminho).test_client()

    def tearDown(self):
        self.pasta.cleanup()

    def cadastrar(self, nome, area, descricao=""):
        return self.cliente.post("/materias", data={"nome": nome, "area": area, "descricao": descricao})

    # --- Cadastro -------------------------------------------------------
    def test_cadastro_grava_e_redireciona(self):
        resposta = self.cadastrar("Anatomia", "Enfermagem", "Sistemas do corpo")
        self.assertEqual(resposta.status_code, 302)
        materias = banco.listar_materias(self.caminho)
        self.assertEqual(len(materias), 1)
        self.assertEqual(materias[0]["nome"], "Anatomia")
        self.assertEqual(materias[0]["area"], "Enfermagem")
        self.assertEqual(materias[0]["descricao"], "Sistemas do corpo")

    def test_descricao_e_opcional(self):
        self.assertEqual(self.cadastrar("Gramática", "Inglês").status_code, 302)
        self.assertEqual(banco.listar_materias(self.caminho)[0]["descricao"], "")

    def test_cadastro_invalido_mostra_erros_e_nao_grava(self):
        casos = [("", "Enfermagem"), ("Química", "Química"), ("x" * 101, "Inglês")]
        for nome, area in casos:
            with self.subTest(nome=nome[:10], area=area):
                resposta = self.cadastrar(nome, area)
                self.assertEqual(resposta.status_code, 400)
        self.assertEqual(banco.listar_materias(self.caminho), [])

    def test_nome_duplicado_na_mesma_area_e_recusado(self):
        self.cadastrar("Marketing", "Administração")
        resposta = self.cadastrar("  marketing ", "Administração")
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("Já existe", resposta.get_data(as_text=True))
        # Mesmo nome em outra área é permitido.
        self.assertEqual(self.cadastrar("Marketing", "Inglês").status_code, 302)

    # --- Listagem -------------------------------------------------------
    def test_listagem_mostra_todas_e_filtra_por_area(self):
        self.cadastrar("Contabilidade", "Administração")
        self.cadastrar("Farmacologia", "Enfermagem")
        self.cadastrar("Listening", "Inglês")

        todas = self.cliente.get("/").get_data(as_text=True)
        for nome in ("Contabilidade", "Farmacologia", "Listening"):
            self.assertIn(nome, todas)

        enfermagem = self.cliente.get("/?area=Enfermagem").get_data(as_text=True)
        self.assertIn("Farmacologia", enfermagem)
        self.assertNotIn("Contabilidade", enfermagem)
        self.assertNotIn("Listening", enfermagem)

    def test_conteudo_digitado_e_escapado(self):
        self.cadastrar("<script>alert(1)</script>", "Inglês")
        html = self.cliente.get("/").get_data(as_text=True)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)

    # --- Exclusão -------------------------------------------------------
    def test_exclusao_pede_confirmacao_antes(self):
        self.cadastrar("Ética", "Enfermagem")
        materia_id = banco.listar_materias(self.caminho)[0]["id"]

        # Abrir a página de confirmação NÃO apaga nada.
        resposta = self.cliente.get(f"/materias/{materia_id}/excluir")
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("Excluir matéria?", resposta.get_data(as_text=True))
        self.assertEqual(len(banco.listar_materias(self.caminho)), 1)

        # Confirmar (POST) apaga.
        resposta = self.cliente.post(f"/materias/{materia_id}/excluir")
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(banco.listar_materias(self.caminho), [])

    def test_excluir_inexistente_da_404(self):
        self.assertEqual(self.cliente.get("/materias/999/excluir").status_code, 404)
        self.assertEqual(self.cliente.post("/materias/999/excluir").status_code, 404)

    # --- Persistência ---------------------------------------------------
    def test_dados_continuam_apos_reiniciar(self):
        self.cadastrar("Inglês Instrumental", "Inglês", "Leitura de textos técnicos")
        del self.cliente  # "fecha" o aplicativo

        novo_cliente = criar_app(self.caminho).test_client()  # "abre" de novo
        html = novo_cliente.get("/").get_data(as_text=True)
        self.assertIn("Inglês Instrumental", html)
        self.assertIn("Leitura de textos técnicos", html)


if __name__ == "__main__":
    unittest.main()
