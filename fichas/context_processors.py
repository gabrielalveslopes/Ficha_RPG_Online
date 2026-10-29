from django.conf import settings

from .models import eh_mestre


def papel(request):
    """Deixa `eh_mestre` e `nome_do_jogo` disponíveis em todos os templates."""
    return {
        "eh_mestre": eh_mestre(getattr(request, "user", None)),
        "nome_do_jogo": settings.NOME_DO_JOGO,
    }
