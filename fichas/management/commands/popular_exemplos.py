from django.core.management.base import BaseCommand

from fichas.models import Origem, Proficiencia, Trunfo

# As 48 proficiências universais da ficha "A Queda de Corvus City", na ordem da folha.
PROFICIENCIAS = [
    # Coluna 1
    "Pistolas e Revólveres (TEC)", "Lâminas Curtas (COR/TEC)", "Briga / Desarmado (COR)",
    "Armas Silenciosas (TEC)", "Rifles & Carabinas (TEC)", "Espingardas / Shotguns (COR)",
    "Contundentes & Duas Mãos (COR)", "Armas Pesadas (COR)", "Escalar (COR)",
    "Corrida de Fuga (RES)", "Natação & Mergulho (COR)", "Saltar (COR)",
    "Mover-se em Silêncio (TEC)", "Ocultar-se (TEC)", "Arrombamento (TEC)",
    "Punga / Mãos Leves (TEC)",
    # Coluna 2
    "Observação Visual (PER)", "Escuta (PER)", "Investigação Forense (PER)",
    "Faro & Intuição (PER)", "Forrageamento Urbano (PER)", "Rastreamento (PER)",
    "Navegação & Orientação (INT)", "Segurança de Acampamento (INT)",
    "Mecânica Automotiva (TEC)", "Eletrônica & Fiação (TEC)", "Armaria (TEC)",
    "Fortificação & Carpintaria (TEC)", "Primeiros Socorros (TEC)",
    "Cirurgia de Trauma (INT)", "Farmacologia (INT)", "Diagnóstico / Clínica (INT)",
    # Coluna 3
    "Virologia & Soro Z (INT)", "Química Aplicada (INT)", "Botânica & Micologia (INT)",
    "Conhecimento Oculto do Velho Mundo (INT)", "Persuasão (SOC)", "Intimidação (COR/SOC)",
    "Enganação / Lábia (SOC)", "Barganha & Avaliação (SOC)", "Dedução Lógica (INT)",
    "Criptografia (INT)", "Firmeza Mental (SF / RES)", "Memória & Conhecimento Geral (INT)",
    "Direção Defensiva / Carros (TEC)", "Pilotagem Especial (TEC)",
    "Telecomunicações & Rádio (TEC)", "Sistemas & Computação (INT)",
]

# Origens e trunfos reais não estão na ficha: estes são EXEMPLOS. Troque no painel /admin/.
ORIGENS = ["Ex-militar [exemplo]", "Enfermeiro [exemplo]", "Mecânico [exemplo]"]
TRUNFOS = ["Sono leve [exemplo]", "Mãos firmes [exemplo]", "Instinto de fuga [exemplo]"]


class Command(BaseCommand):
    help = "Cadastra as 48 proficiências da ficha e origens/trunfos de EXEMPLO (pode rodar várias vezes)."

    def handle(self, *args, **opcoes):
        # Remove proficiências de exemplo antigas que nenhuma ficha usa.
        Proficiencia.objects.filter(nome__endswith="[exemplo]", fichaproficiencia__isnull=True).delete()
        for posicao, nome in enumerate(PROFICIENCIAS, start=1):
            Proficiencia.objects.update_or_create(nome=nome, defaults={"ordem": posicao})
        for modelo, nomes in ((Origem, ORIGENS), (Trunfo, TRUNFOS)):
            for nome in nomes:
                modelo.objects.get_or_create(nome=nome)
        self.stdout.write(self.style.SUCCESS("Proficiências da ficha cadastradas. Edite origens e trunfos em /admin/."))
