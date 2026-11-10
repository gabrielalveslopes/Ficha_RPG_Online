import uuid
from io import BytesIO

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from django.db.models import Q

from .models import (
    ATRIBUTO_CAMPOS,
    RECURSO_CAMPOS,
    SLOT_CAMPOS,
    Arma,
    Ficha,
    FichaProficiencia,
    ItemEncontrado,
    ItemMochila,
    Origem,
    Proficiencia,
    Trunfo,
)

FOTO_TAMANHO_MAXIMO = 8 * 1024 * 1024  # 8 MB enviados; a foto salva é reduzida


def estilizar(form):
    """Aplica a classe CSS `campo` aos campos (menos caixas de marcar)."""
    for campo in form.fields.values():
        if isinstance(campo.widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
            continue
        antigas = campo.widget.attrs.get("class", "")
        campo.widget.attrs["class"] = f"{antigas} campo".strip()


def processar_foto(arquivo):
    """Valida e reduz a foto: JPEG de até 900 px, sem metadados (EXIF/GPS), com nome aleatório."""
    from PIL import Image, ImageOps

    if arquivo.size > FOTO_TAMANHO_MAXIMO:
        raise forms.ValidationError("A foto é grande demais. O limite é 8 MB.")
    try:
        arquivo.seek(0)
        imagem = Image.open(arquivo)
        imagem.load()
        imagem = ImageOps.exif_transpose(imagem)
        if imagem.mode in ("RGBA", "LA", "P"):
            imagem = imagem.convert("RGBA")
            fundo = Image.new("RGB", imagem.size, (255, 255, 255))
            fundo.paste(imagem, mask=imagem.split()[-1])
            imagem = fundo
        else:
            imagem = imagem.convert("RGB")
        imagem.thumbnail((900, 900))
        saida = BytesIO()
        imagem.save(saida, "JPEG", quality=85, optimize=True)
    except Exception:
        raise forms.ValidationError("Não foi possível ler a imagem. Envie um arquivo JPG, PNG ou WebP.")
    return ContentFile(saida.getvalue(), name=f"{uuid.uuid4().hex}.jpg")


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Usuário"
        self.fields["username"].widget.attrs.update(
            {"autofocus": True, "autocapitalize": "none", "autocomplete": "username"}
        )
        self.fields["password"].label = "Senha"
        estilizar(self)


def _numero(minimo=0, maximo=None):
    attrs = {"min": minimo, "inputmode": "numeric"}
    if maximo is not None:
        attrs["max"] = maximo
    return forms.NumberInput(attrs=attrs)


class FichaJogadorForm(forms.ModelForm):
    """Campos que o JOGADOR pode editar na própria ficha."""

    remover_foto = forms.BooleanField(label="Remover a foto atual", required=False)

    class Meta:
        model = Ficha
        fields = [
            "nome_personagem", "origem", "foto", *ATRIBUTO_CAMPOS,
            "trunfos", "qualidades", "defeitos", *RECURSO_CAMPOS, *SLOT_CAMPOS,
        ]
        widgets = {
            **{campo: _numero(1, 10) for campo in ATRIBUTO_CAMPOS},
            **{campo: _numero(0) for campo in RECURSO_CAMPOS},
            "foto": forms.FileInput(attrs={"accept": "image/*", "data-previa": "previa-foto"}),
            "trunfos": forms.CheckboxSelectMultiple,
            "qualidades": forms.Textarea(attrs={"rows": 6}),
            "defeitos": forms.Textarea(attrs={"rows": 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._foto_antiga = self.instance.foto.name if (self.instance.pk and self.instance.foto) else ""

        # Só mostra opções ativas (mantendo as que a ficha já usa, mesmo se desativadas).
        self.fields["origem"].queryset = Origem.objects.filter(
            Q(ativo=True) | Q(pk=self.instance.origem_id)
        )
        self.fields["origem"].empty_label = "— escolha uma origem —"
        trunfos_atuais = self.instance.trunfos.all() if self.instance.pk else Trunfo.objects.none()
        self.fields["trunfos"].queryset = Trunfo.objects.filter(
            Q(ativo=True) | Q(pk__in=trunfos_atuais.values("pk"))
        )
        for campo in ATRIBUTO_CAMPOS:
            self.fields[campo].widget.attrs["data-atributo"] = campo

        # Uma caixa de bônus por proficiência do catálogo. Em branco = não possui.
        bonus_atuais = {}
        if self.instance.pk:
            bonus_atuais = dict(
                self.instance.proficiencias_escolhidas.values_list("proficiencia_id", "bonus")
            )
        self.proficiencias = list(
            Proficiencia.objects.filter(Q(ativo=True) | Q(pk__in=list(bonus_atuais)))
        )
        for prof in self.proficiencias:
            self.fields[f"prof_{prof.pk}"] = forms.IntegerField(
                label=prof.nome, required=False, initial=bonus_atuais.get(prof.pk),
                widget=forms.NumberInput(attrs={"inputmode": "numeric"}),
            )
        estilizar(self)

    # ---- grupos de campos para o template
    def atributos(self):
        return [self[campo] for campo in ATRIBUTO_CAMPOS]

    def recursos(self):
        return [self[campo] for campo in RECURSO_CAMPOS]

    def slots(self):
        return [self[campo] for campo in SLOT_CAMPOS]

    def campos_proficiencias(self):
        return [self[f"prof_{prof.pk}"] for prof in self.proficiencias]

    # ---- foto
    def clean_foto(self):
        foto = self.cleaned_data.get("foto")
        if isinstance(foto, UploadedFile):  # arquivo novo enviado agora
            return processar_foto(foto)
        return foto

    def clean(self):
        dados = super().clean()
        enviou_nova = isinstance(dados.get("foto"), ContentFile)
        if dados.get("remover_foto") and not enviou_nova:
            dados["foto"] = False  # False = limpar o campo
        return dados

    def descartar_foto_antiga(self, ficha):
        """Apaga do disco a foto que foi trocada ou removida."""
        atual = ficha.foto.name if ficha.foto else ""
        if self._foto_antiga and self._foto_antiga != atual:
            ficha.foto.storage.delete(self._foto_antiga)

    # ---- proficiências
    def salvar_proficiencias(self, ficha):
        for prof in self.proficiencias:
            bonus = self.cleaned_data.get(f"prof_{prof.pk}")
            if bonus is None:
                FichaProficiencia.objects.filter(ficha=ficha, proficiencia=prof).delete()
            else:
                FichaProficiencia.objects.update_or_create(
                    ficha=ficha, proficiencia=prof, defaults={"bonus": bonus}
                )


class FichaMestreForm(FichaJogadorForm):
    """O mestre edita tudo, inclusive o jogador responsável e os valores de estado."""

    class Meta(FichaJogadorForm.Meta):
        fields = [
            "jogador", *FichaJogadorForm.Meta.fields,
            "pv", "defesa", "mov", "fadiga",
            "sf_atual", "sf_max_manual", "anticorpos_atual", "anticorpos_max_manual",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        usuarios = get_user_model().objects.filter(is_active=True).order_by("username")
        self.fields["jogador"].queryset = usuarios
        self.fields["jogador"].label_from_instance = lambda u: u.get_full_name() or u.get_username()
        estilizar(self)


class ArmaForm(forms.ModelForm):
    class Meta:
        model = Arma
        fields = ["nome", "ataque", "dano", "municao", "alcance_obs"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        estilizar(self)


class ItemMochilaForm(forms.ModelForm):
    class Meta:
        model = ItemMochila
        fields = ["item", "slot"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        estilizar(self)


ArmaFormSet = forms.inlineformset_factory(
    Ficha, Arma, form=ArmaForm, extra=4, can_delete=True
)
MOCHILA_MAXIMO = 15
MochilaFormSet = forms.inlineformset_factory(
    Ficha, ItemMochila, form=ItemMochilaForm,
    extra=MOCHILA_MAXIMO, max_num=MOCHILA_MAXIMO, validate_max=True, can_delete=True,
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
