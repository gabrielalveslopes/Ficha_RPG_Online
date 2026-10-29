from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin

from .models import Ficha, FichaProficiencia, ItemEncontrado, Origem, Perfil, Proficiencia, Trunfo


@admin.register(Origem, Proficiencia, Trunfo)
class CatalogoAdmin(admin.ModelAdmin):
    """Aqui o mestre ajusta origens, proficiências e trunfos quando quiser."""

    list_display = ("nome", "ativo")
    list_editable = ("ativo",)
    search_fields = ("nome", "descricao")


class FichaProficienciaInline(admin.TabularInline):
    model = FichaProficiencia
    extra = 0


@admin.register(Ficha)
class FichaAdmin(admin.ModelAdmin):
    list_display = ("nome_personagem", "jogador", "origem")
    search_fields = ("nome_personagem", "jogador__username")
    inlines = [FichaProficienciaInline]


@admin.register(ItemEncontrado)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("nome", "ficha", "quantidade", "criado_em")
    search_fields = ("nome", "ficha__nome_personagem")


class PerfilInline(admin.StackedInline):
    model = Perfil
    can_delete = False


User = get_user_model()
admin.site.unregister(User)


@admin.register(User)
class UsuarioAdmin(UserAdmin):
    inlines = [PerfilInline]

    def get_inline_instances(self, request, obj=None):
        # Na criação, o perfil (jogador) nasce automaticamente por sinal; evita duplicar.
        return super().get_inline_instances(request, obj) if obj else []
