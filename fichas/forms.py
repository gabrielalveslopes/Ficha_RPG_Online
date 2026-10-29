from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.db.models import Q

from .models import (
    ATRIBUTO_CAMPOS,
    Ficha,
    FichaProficiencia,
    ItemEncontrado,
    Origem,
    Proficiencia,
    Trunfo,
)


def estilizar(form):
    """Aplica a classe CSS `campo` aos campos (menos caixas de marcar)."""
    for campo in form.fields.values():
        if isinstance(campo.widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
            continue
        antigas = campo.widget.attrs.get("class", "")
        campo.widget.attrs["class"] = f"{antigas} campo".strip()


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Usuário"
        self.fields["username"].widget.attrs.update(
            {"autofocus": True, "autocapitalize": "none", "autocomplete": "username"}
        )
        self.fields["password"].label = "Senha"
        estilizar(self)


def _numero():
    return forms.NumberInput(attrs={"min": 1, "max": 10, "inputmode": "numeric"})


class FichaJogadorForm(forms.ModelForm):
    """Campos que o JOGADOR pode editar na própria ficha."""

    class Meta:
        model = Ficha
        fields = ["nome_personagem", "origem", *ATRIBUTO_CAMPOS,
                  "trunfos", "qualidades", "defeitos", "inventario"]
        widgets = {
            **{campo: _numero() for campo in ATRIBUTO_CAMPOS},
            "trunfos": forms.CheckboxSelectMultiple,
            "qualidades": forms.Textarea(attrs={"rows": 4}),
            "defeitos": forms.Textarea(attrs={"rows": 4}),
            "inventario": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Só mostra opções ativas (mantendo as que a ficha já usa, mesmo se desativadas).
        origem_atual = self.instance.origem_id
        self.fields["origem"].queryset = Origem.objects.filter(
            Q(ativo=True) | Q(pk=origem_atual)
        )
        self.fields["origem"].empty_label = "— escolha uma origem —"
        trunfos_atuais = self.instance.trunfos.all() if self.instance.pk else Trunfo.objects.none()
        self.fields["trunfos"].queryset = Trunfo.objects.filter(
            Q(ativo=True) | Q(pk__in=trunfos_atuais.values("pk"))
        )
        for campo in ATRIBUTO_CAMPOS:
            self.fields[campo].widget.attrs["data-atributo"] = campo
        estilizar(self)

    def atributos(self):
        """Os sete campos de atributo, na ordem do livro (usado no template)."""
        return [self[campo] for campo in ATRIBUTO_CAMPOS]


class FichaMestreForm(FichaJogadorForm):
    """O mestre edita tudo, inclusive o jogador responsável e os valores atuais/máximos."""

    class Meta(FichaJogadorForm.Meta):
        fields = ["jogador", *FichaJogadorForm.Meta.fields,
                  "sf_atual", "sf_max_manual", "anticorpos_atual", "anticorpos_max_manual"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        usuarios = get_user_model().objects.filter(is_active=True).order_by("username")
        self.fields["jogador"].queryset = usuarios
        self.fields["jogador"].label_from_instance = lambda u: u.get_full_name() or u.get_username()
        estilizar(self)


class ProficienciaForm(forms.ModelForm):
    class Meta:
        model = FichaProficiencia
        fields = ["proficiencia", "nivel", "bonus"]
        widgets = {
            "nivel": forms.NumberInput(attrs={"min": 0, "inputmode": "numeric"}),
            "bonus": forms.NumberInput(attrs={"inputmode": "numeric"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["proficiencia"].queryset = Proficiencia.objects.filter(
            Q(ativo=True) | Q(pk=self.instance.proficiencia_id)
        )
        self.fields["proficiencia"].empty_label = "— escolha —"
        estilizar(self)


class BaseProficienciaFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        vistas = set()
        for form in self.forms:
            dados = getattr(form, "cleaned_data", None)
            if not dados or dados.get("DELETE"):
                continue
            proficiencia = dados.get("proficiencia")
            if proficiencia is None:
                continue
            if proficiencia.pk in vistas:
                raise forms.ValidationError(
                    "Você escolheu a mesma proficiência mais de uma vez. "
                    "Escolha cada proficiência uma única vez."
                )
            vistas.add(proficiencia.pk)


ProficienciaFormSet = forms.inlineformset_factory(
    Ficha,
    FichaProficiencia,
    form=ProficienciaForm,
    formset=BaseProficienciaFormSet,
    extra=3,
    can_delete=True,
)


class ItemForm(forms.ModelForm):
    class Meta:
        model = ItemEncontrado
        fields = ["ficha", "nome", "descricao", "quantidade"]
        widgets = {
            "descricao": forms.Textarea(attrs={"rows": 4}),
            "quantidade": forms.NumberInput(attrs={"min": 1, "inputmode": "numeric"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ficha"].queryset = Ficha.objects.select_related("jogador").order_by(
            "nome_personagem"
        )
        self.fields["ficha"].label = "Ficha que receberá o item"
        self.fields["ficha"].empty_label = "— escolha o personagem —"
        self.fields["ficha"].label_from_instance = (
            lambda f: f"{f.nome_personagem} (jogador: {f.jogador.get_username()})"
        )
        estilizar(self)
