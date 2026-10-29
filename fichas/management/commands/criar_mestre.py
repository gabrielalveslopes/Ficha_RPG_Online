from getpass import getpass

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from fichas.models import Papel, Perfil


class Command(BaseCommand):
    help = "Cria o usuário MESTRE (a senha é pedida de forma oculta no terminal)."

    def add_arguments(self, parser):
        parser.add_argument("usuario", help="Nome de usuário do mestre")
        parser.add_argument("--email", default="")

    def handle(self, *args, **opcoes):
        User = get_user_model()
        nome = opcoes["usuario"]
        if User.objects.filter(username=nome).exists():
            raise CommandError(f"O usuário “{nome}” já existe.")

        senha = getpass("Senha: ")
        if senha != getpass("Repita a senha: "):
            raise CommandError("As senhas não conferem.")
        try:
            validate_password(senha)
        except ValidationError as erro:
            raise CommandError(" ".join(erro.messages))

        # create_superuser também libera o painel /admin/ (catálogos e cadastro de jogadores).
        usuario = User.objects.create_superuser(nome, opcoes["email"], senha)
        perfil, _ = Perfil.objects.get_or_create(usuario=usuario)
        perfil.papel = Papel.MESTRE
        perfil.save()
        self.stdout.write(self.style.SUCCESS(f"Mestre “{nome}” criado com sucesso."))
