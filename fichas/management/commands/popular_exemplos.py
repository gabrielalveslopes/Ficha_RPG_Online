from django.core.management.base import BaseCommand

from fichas.models import Origem, Proficiencia, Trunfo

# ATENÇÃO: são apenas EXEMPLOS genéricos para você ver o sistema funcionando.
# Troque pelos conteúdos reais do livro no painel /admin/.
ORIGENS = ["Ex-militar [exemplo]", "Enfermeiro [exemplo]", "Mecânico [exemplo]"]
PROFICIENCIAS = ["Primeiros socorros [exemplo]", "Furtividade [exemplo]",
                 "Armas de fogo [exemplo]", "Mecânica [exemplo]"]
TRUNFOS = ["Sono leve [exemplo]", "Mãos firmes [exemplo]", "Instinto de fuga [exemplo]"]


class Command(BaseCommand):
    help = "Cadastra origens, proficiências e trunfos de EXEMPLO (pode ser executado várias vezes)."

    def handle(self, *args, **opcoes):
        for modelo, nomes in ((Origem, ORIGENS), (Proficiencia, PROFICIENCIAS), (Trunfo, TRUNFOS)):
            for nome in nomes:
                modelo.objects.get_or_create(nome=nome)
        self.stdout.write(self.style.SUCCESS("Exemplos cadastrados. Edite-os em /admin/."))
