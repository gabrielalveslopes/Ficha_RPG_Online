"""Testes automáticos de permissão. Rode com:  python manage.py test"""
from django.contrib.auth import get_user_model
import shutil
import tempfile
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import (
    Ficha, ItemEncontrado, ItemMochila, ItemModelo, Papel, Proficiencia, eh_mestre,
)

User = get_user_model()
SENHA = "senha-de-teste-123"
FORMSETS_VAZIOS = {
    f"{prefixo}-{campo}": valor
    for prefixo in ("arma", "mochila", "trunfo")
    for campo, valor in (("TOTAL_FORMS", "0"), ("INITIAL_FORMS", "0"),
                         ("MIN_NUM_FORMS", "0"), ("MAX_NUM_FORMS", "1000"))
}


def dados_ficha(**extra):
    base = {
        "nome_personagem": "Teste", "cor": 3, "inteligencia": 3, "percepcao": 3,
        "influencia": 3, "resistencia": 3, "tecnica": 3, "sangue_frio": 3,
        "recurso_m": 0, "recurso_w": 0, "recurso_e": 0, "recurso_t": 0,
        "recurso_d": 0, "recurso_f": 0, "recurso_r": 0, "tipo_mochila": "comum",
        **FORMSETS_VAZIOS,
    }
    base.update(extra)
    return base


class PermissoesTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.mestre = User.objects.create_user("mestre", password=SENHA)
        cls.mestre.perfil.papel = Papel.MESTRE
        cls.mestre.perfil.save()
        cls.ana = User.objects.create_user("ana", password=SENHA)
        cls.bruno = User.objects.create_user("bruno", password=SENHA)
        cls.ficha_ana = Ficha.objects.create(jogador=cls.ana, nome_personagem="Ana Sobrevivente")
        cls.ficha_bruno = Ficha.objects.create(jogador=cls.bruno, nome_personagem="Bruno Caçador")
        cls.item_ana = ItemEncontrado.objects.create(ficha=cls.ficha_ana, nome="Chave Secreta da Farmácia")

    def entrar(self, usuario):
        self.client.login(username=usuario, password=SENHA)

    # --- papéis
    def test_usuario_novo_e_jogador(self):
        self.assertFalse(eh_mestre(self.ana))
        self.assertTrue(eh_mestre(self.mestre))

    # --- anônimo
    def test_anonimo_vai_para_login(self):
        for nome, args in [("ficha_lista", []), ("ficha_detalhe", [self.ficha_ana.pk]),
                           ("item_lista", []), ("ficha_criar", [])]:
            r = self.client.get(reverse(nome, args=args))
            self.assertEqual(r.status_code, 302)
            self.assertIn("/entrar/", r["Location"])

    # --- jogador x ficha de outro
    def test_jogador_nao_ve_ficha_de_outro(self):
        self.entrar("bruno")
        self.assertEqual(self.client.get(reverse("ficha_detalhe", args=[self.ficha_ana.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("ficha_editar", args=[self.ficha_ana.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("ficha_excluir", args=[self.ficha_ana.pk])).status_code, 403)

    def test_jogador_nao_edita_ficha_de_outro_por_post(self):
        self.entrar("bruno")
        r = self.client.post(reverse("ficha_editar", args=[self.ficha_ana.pk]),
                             dados_ficha(nome_personagem="Hackeada"))
        self.assertEqual(r.status_code, 404)
        self.ficha_ana.refresh_from_db()
        self.assertEqual(self.ficha_ana.nome_personagem, "Ana Sobrevivente")

    def test_lista_do_jogador_mostra_so_a_dele(self):
        self.entrar("bruno")
        r = self.client.get(reverse("ficha_lista"))
        self.assertContains(r, "Bruno Caçador")
        self.assertNotContains(r, "Ana Sobrevivente")

    def test_jogador_edita_a_propria_ficha_mas_nao_valores_do_mestre(self):
        self.entrar("ana")
        r = self.client.post(
            reverse("ficha_editar", args=[self.ficha_ana.pk]),
            dados_ficha(nome_personagem="Ana Nova", sf_atual=99, anticorpos_atual=99,
                        jogador=self.bruno.pk),
        )
        self.assertEqual(r.status_code, 302)
        self.ficha_ana.refresh_from_db()
        self.assertEqual(self.ficha_ana.nome_personagem, "Ana Nova")
        self.assertEqual(self.ficha_ana.jogador, self.ana)  # dono não muda
        self.assertNotEqual(self.ficha_ana.sf_atual, 99)  # campo do mestre ignorado

    def test_jogador_cria_ficha_sempre_como_dono(self):
        carla = User.objects.create_user("carla", password=SENHA)  # ainda sem ficha
        self.entrar("carla")
        self.client.post(reverse("ficha_criar"), dados_ficha(nome_personagem="Nova", jogador=self.bruno.pk))
        self.assertTrue(Ficha.objects.filter(nome_personagem="Nova", jogador=carla).exists())
        self.assertFalse(Ficha.objects.filter(nome_personagem="Nova", jogador=self.bruno).exists())

    def test_jogador_so_pode_ter_uma_ficha(self):
        self.entrar("ana")  # ana já tem a "Ana Sobrevivente"
        r = self.client.get(reverse("ficha_criar"))
        self.assertRedirects(r, reverse("ficha_detalhe", args=[self.ficha_ana.pk]))
        self.client.post(reverse("ficha_criar"), dados_ficha(nome_personagem="Segunda"))
        self.assertEqual(Ficha.objects.filter(jogador=self.ana).count(), 1)
        self.assertNotContains(self.client.get(reverse("ficha_lista")), "Nova ficha")

    def test_mestre_nao_cria_segunda_ficha_para_jogador(self):
        self.entrar("mestre")
        r = self.client.post(reverse("ficha_criar"), dados_ficha(nome_personagem="Dupla", jogador=self.ana.pk))
        self.assertEqual(r.status_code, 200)  # volta ao formulário com erro
        self.assertFalse(Ficha.objects.filter(nome_personagem="Dupla").exists())

    def test_mestre_pode_criar_ficha_de_npc_no_proprio_usuario(self):
        self.entrar("mestre")
        for nome in ("Zumbi A", "Zumbi B"):
            self.client.post(reverse("ficha_criar"), dados_ficha(nome_personagem=nome, jogador=self.mestre.pk))
        self.assertEqual(Ficha.objects.filter(jogador=self.mestre).count(), 2)

    def test_capacidade_da_mochila_comum_e_militar(self):
        self.entrar("ana")
        url = reverse("ficha_editar", args=[self.ficha_ana.pk])

        def dados(tipo, qtd):
            d = dados_ficha(nome_personagem="Ana", tipo_mochila=tipo)
            d.update({"mochila-TOTAL_FORMS": str(qtd), "mochila-INITIAL_FORMS": "0"})
            for n in range(qtd):
                d[f"mochila-{n}-item"] = f"Item {n}"
            return d

        r = self.client.post(url, dados("comum", 11))
        self.assertEqual(r.status_code, 200)  # 11 não cabe na comum
        self.assertEqual(self.ficha_ana.mochila.count(), 0)
        r = self.client.post(url, dados("militar", 11))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.ficha_ana.mochila.count(), 11)

    # --- itens
    def test_jogador_nao_acessa_telas_de_itens(self):
        self.entrar("ana")
        self.assertEqual(self.client.get(reverse("item_lista")).status_code, 403)
        self.assertEqual(self.client.get(reverse("item_criar")).status_code, 403)
        self.assertEqual(self.client.get(reverse("item_editar", args=[self.item_ana.pk])).status_code, 403)
        r = self.client.post(reverse("item_excluir", args=[self.item_ana.pk]))
        self.assertEqual(r.status_code, 403)
        self.assertTrue(ItemEncontrado.objects.filter(pk=self.item_ana.pk).exists())

    def test_jogador_nao_cria_item_por_post(self):
        self.entrar("ana")
        r = self.client.post(reverse("item_criar"), {"ficha": self.ficha_ana.pk, "nome": "Ouro", "quantidade": 1})
        self.assertEqual(r.status_code, 403)
        self.assertFalse(ItemEncontrado.objects.filter(nome="Ouro").exists())

    def test_item_aparece_so_para_dono_e_mestre(self):
        self.entrar("ana")
        self.assertContains(self.client.get(reverse("ficha_detalhe", args=[self.ficha_ana.pk])), "Chave Secreta da Farmácia")
        self.client.logout()
        self.entrar("bruno")
        self.assertNotContains(self.client.get(reverse("ficha_detalhe", args=[self.ficha_bruno.pk])), "Chave Secreta")
        self.assertNotContains(self.client.get(reverse("ficha_lista")), "Chave Secreta")
        self.client.logout()
        self.entrar("mestre")
        self.assertContains(self.client.get(reverse("ficha_detalhe", args=[self.ficha_ana.pk])), "Chave Secreta da Farmácia")

    # --- mestre
    def test_mestre_ve_todas_as_fichas(self):
        self.entrar("mestre")
        r = self.client.get(reverse("ficha_lista"))
        self.assertContains(r, "Ana Sobrevivente")
        self.assertContains(r, "Bruno Caçador")

    def test_mestre_registra_e_atribui_item(self):
        self.entrar("mestre")
        r = self.client.post(reverse("item_criar"),
                             {"ficha": self.ficha_bruno.pk, "nome": "Lanterna", "descricao": "", "quantidade": 2})
        self.assertEqual(r.status_code, 302)
        item = ItemEncontrado.objects.get(nome="Lanterna")
        self.assertEqual(item.ficha, self.ficha_bruno)
        self.assertEqual(item.criado_por, self.mestre)

    def test_maximos_padrao(self):
        ficha = Ficha.objects.create(jogador=self.ana, nome_personagem="X", sangue_frio=4, resistencia=5)
        self.assertEqual((ficha.sf_max, ficha.anticorpos_max), (12, 50))
        self.assertEqual((ficha.sf_atual, ficha.anticorpos_atual), (12, 50))


def _imagem_png():
    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (1200, 1600), (120, 40, 30)).save(buf, "PNG")
    return buf.getvalue()


class FotoETestes(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._midia = tempfile.mkdtemp()
        cls._override = override_settings(MEDIA_ROOT=cls._midia)
        cls._override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._override.disable()
        shutil.rmtree(cls._midia, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.ana = User.objects.create_user("ana", password=SENHA)
        self.bruno = User.objects.create_user("bruno", password=SENHA)
        self.ficha_ana = Ficha.objects.create(jogador=self.ana, nome_personagem="Ana")

    def test_upload_reduz_e_so_o_dono_ve(self):
        self.client.login(username="ana", password=SENHA)
        r = self.client.post(
            reverse("ficha_editar", args=[self.ficha_ana.pk]),
            dados_ficha(nome_personagem="Ana",
                        foto=SimpleUploadedFile("foto.png", _imagem_png(), content_type="image/png")),
        )
        self.assertEqual(r.status_code, 302)
        self.ficha_ana.refresh_from_db()
        self.assertTrue(self.ficha_ana.foto.name.endswith(".jpg"))
        resposta = self.client.get(reverse("ficha_foto", args=[self.ficha_ana.pk]))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta["Content-Type"], "image/jpeg")
        self.client.logout()
        self.client.login(username="bruno", password=SENHA)
        self.assertEqual(self.client.get(reverse("ficha_foto", args=[self.ficha_ana.pk])).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("ficha_foto", args=[self.ficha_ana.pk])).status_code, 302)

    def test_arquivo_que_nao_e_imagem_e_recusado(self):
        self.client.login(username="ana", password=SENHA)
        r = self.client.post(
            reverse("ficha_editar", args=[self.ficha_ana.pk]),
            dados_ficha(nome_personagem="Ana",
                        foto=SimpleUploadedFile("x.png", b"isto nao e imagem", content_type="image/png")),
        )
        self.assertEqual(r.status_code, 200)  # volta ao formulário com erro
        self.ficha_ana.refresh_from_db()
        self.assertFalse(self.ficha_ana.foto)

    def test_proficiencia_com_bonus_e_removida_quando_em_branco(self):
        prof = Proficiencia.objects.create(nome="Escalar (COR)")
        self.client.login(username="ana", password=SENHA)
        url = reverse("ficha_editar", args=[self.ficha_ana.pk])
        self.client.post(url, dados_ficha(nome_personagem="Ana", **{f"prof_{prof.pk}": 2}))
        self.assertEqual(self.ficha_ana.proficiencias_escolhidas.get().bonus, 2)
        self.client.post(url, dados_ficha(nome_personagem="Ana", **{f"prof_{prof.pk}": ""}))
        self.assertFalse(self.ficha_ana.proficiencias_escolhidas.exists())


class PegarEDeixarTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ana = User.objects.create_user("ana", password=SENHA)
        cls.bruno = User.objects.create_user("bruno", password=SENHA)
        cls.mestre = User.objects.create_user("mestre", password=SENHA)
        cls.mestre.perfil.papel = Papel.MESTRE
        cls.mestre.perfil.save()
        cls.ficha = Ficha.objects.create(jogador=cls.ana, nome_personagem="Ana")
        cls.item = ItemEncontrado.objects.create(ficha=cls.ficha, nome="Lanterna", quantidade=2)

    def test_pegar_move_para_a_mochila(self):
        self.client.login(username="ana", password=SENHA)
        r = self.client.post(reverse("item_pegar", args=[self.item.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertFalse(ItemEncontrado.objects.filter(pk=self.item.pk).exists())
        self.assertEqual(self.ficha.mochila.get().item, "Lanterna (×2)")

    def test_pegar_por_get_nao_funciona(self):
        self.client.login(username="ana", password=SENHA)
        self.assertEqual(self.client.get(reverse("item_pegar", args=[self.item.pk])).status_code, 405)

    def test_outro_jogador_nao_pega_nem_deixa(self):
        self.client.login(username="bruno", password=SENHA)
        self.assertEqual(self.client.post(reverse("item_pegar", args=[self.item.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("item_deixar", args=[self.item.pk])).status_code, 404)
        self.assertTrue(ItemEncontrado.objects.filter(pk=self.item.pk).exists())
        self.assertEqual(self.ficha.mochila.count(), 0)

    def test_mochila_cheia_bloqueia(self):
        for n in range(10):  # mochila comum comporta 10
            ItemMochila.objects.create(ficha=self.ficha, item=f"Item {n}")
        self.client.login(username="ana", password=SENHA)
        self.client.post(reverse("item_pegar", args=[self.item.pk]))
        self.assertTrue(ItemEncontrado.objects.filter(pk=self.item.pk).exists())
        self.assertEqual(self.ficha.mochila.count(), 10)

    def test_mochila_militar_comporta_mais(self):
        self.ficha.tipo_mochila = "militar"
        self.ficha.save()
        for n in range(10):
            ItemMochila.objects.create(ficha=self.ficha, item=f"Item {n}")
        self.client.login(username="ana", password=SENHA)
        self.client.post(reverse("item_pegar", args=[self.item.pk]))
        self.assertEqual(self.ficha.mochila.count(), 11)

    def test_deixar_item_encontrado_marca_como_deixado(self):
        self.client.login(username="ana", password=SENHA)
        self.client.post(reverse("item_deixar", args=[self.item.pk]))
        self.item.refresh_from_db()
        self.assertTrue(self.item.deixado)

    def test_deixar_item_da_mochila_volta_para_encontrados(self):
        mochila = ItemMochila.objects.create(ficha=self.ficha, item="Faca")
        self.client.login(username="ana", password=SENHA)
        self.client.post(reverse("mochila_deixar", args=[mochila.pk]))
        self.assertFalse(ItemMochila.objects.filter(pk=mochila.pk).exists())
        self.assertTrue(ItemEncontrado.objects.filter(ficha=self.ficha, nome="Faca", deixado=True).exists())

    def test_mochila_de_outro_jogador_nao_pode_ser_mexida(self):
        mochila = ItemMochila.objects.create(ficha=self.ficha, item="Faca")
        self.client.login(username="bruno", password=SENHA)
        self.assertEqual(self.client.post(reverse("mochila_deixar", args=[mochila.pk])).status_code, 404)
        self.assertTrue(ItemMochila.objects.filter(pk=mochila.pk).exists())

    def test_mestre_pode_pegar_pelo_jogador(self):
        self.client.login(username="mestre", password=SENHA)
        self.client.post(reverse("item_pegar", args=[self.item.pk]))
        self.assertEqual(self.ficha.mochila.count(), 1)


class TrunfosEEnvioTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.mestre = User.objects.create_user("mestre", password=SENHA)
        cls.mestre.perfil.papel = Papel.MESTRE
        cls.mestre.perfil.save()
        cls.ana = User.objects.create_user("ana", password=SENHA)
        cls.bruno = User.objects.create_user("bruno", password=SENHA)
        cls.ficha_ana = Ficha.objects.create(jogador=cls.ana, nome_personagem="Ana")
        cls.ficha_bruno = Ficha.objects.create(jogador=cls.bruno, nome_personagem="Bruno")

    def _dados_trunfos(self, nomes):
        d = dados_ficha(nome_personagem="Ana")
        d.update({"trunfo-TOTAL_FORMS": str(len(nomes)), "trunfo-INITIAL_FORMS": "0"})
        for n, nome in enumerate(nomes):
            d[f"trunfo-{n}-nome"] = nome
        return d

    # --- trunfos
    def test_jogador_adiciona_ate_tres_trunfos(self):
        self.client.login(username="ana", password=SENHA)
        url = reverse("ficha_editar", args=[self.ficha_ana.pk])
        r = self.client.post(url, self._dados_trunfos(["A", "B", "C"]))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.ficha_ana.trunfos_escolhidos.count(), 3)

    def test_quarto_trunfo_e_recusado(self):
        self.client.login(username="ana", password=SENHA)
        url = reverse("ficha_editar", args=[self.ficha_ana.pk])
        r = self.client.post(url, self._dados_trunfos(["A", "B", "C", "D"]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.ficha_ana.trunfos_escolhidos.count(), 0)

    # --- envio em lote
    def test_jogador_nao_acessa_envio_nem_tabela(self):
        self.client.login(username="ana", password=SENHA)
        self.assertEqual(self.client.get(reverse("item_enviar")).status_code, 403)
        self.assertEqual(self.client.post(reverse("item_enviar"), {}).status_code, 403)
        self.assertEqual(self.client.get(reverse("item_modelos")).status_code, 403)

    def test_mestre_envia_varios_itens_para_varias_fichas(self):
        agua = ItemModelo.objects.create(nome="Água", categoria="Comida")
        faca = ItemModelo.objects.create(nome="Faca")
        self.client.login(username="mestre", password=SENHA)
        r = self.client.post(reverse("item_enviar"), {
            "fichas": [self.ficha_ana.pk, self.ficha_bruno.pk],
            f"modelo_{agua.pk}": 2, f"modelo_{faca.pk}": 0,
            "avulso_nome_1": "Rádio quebrado", "avulso_qtd_1": "",
        })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(ItemEncontrado.objects.count(), 4)  # 2 itens x 2 fichas
        self.assertEqual(ItemEncontrado.objects.get(ficha=self.ficha_ana, nome="Água").quantidade, 2)
        self.assertEqual(ItemEncontrado.objects.get(ficha=self.ficha_bruno, nome="Rádio quebrado").quantidade, 1)
        self.assertFalse(ItemEncontrado.objects.filter(nome="Faca").exists())

    def test_envio_exige_ficha_e_item(self):
        agua = ItemModelo.objects.create(nome="Água")
        self.client.login(username="mestre", password=SENHA)
        r = self.client.post(reverse("item_enviar"), {f"modelo_{agua.pk}": 1})
        self.assertEqual(r.status_code, 200)  # sem ficha escolhida
        r = self.client.post(reverse("item_enviar"), {"fichas": [self.ficha_ana.pk]})
        self.assertEqual(r.status_code, 200)  # sem nenhum item
        self.assertEqual(ItemEncontrado.objects.count(), 0)

    def test_mestre_salva_tabela_de_itens(self):
        self.client.login(username="mestre", password=SENHA)
        r = self.client.post(reverse("item_modelos"), {
            "modelo-TOTAL_FORMS": "2", "modelo-INITIAL_FORMS": "0",
            "modelo-MIN_NUM_FORMS": "0", "modelo-MAX_NUM_FORMS": "1000",
            "modelo-0-nome": "Bandagem", "modelo-0-categoria": "Remédios",
            "modelo-1-nome": "", "modelo-1-categoria": "",
        })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(ItemModelo.objects.get().nome, "Bandagem")
