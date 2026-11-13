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
    CAPACIDADE_MOCHILA,
    MOCHILA_MAXIMO,
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
    TrunfoFicha,
    ItemModelo,
    TRUNFOS_MAXIMO,
    eh_mestre,
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
            "qualidades", "defeitos", *RECURSO_CAMPOS, *SLOT_CAMPOS, "tipo_mochila",
        ]
        widgets = {
            **{campo: _numero(1, 10) for campo in ATRIBUTO_CAMPOS},
            **{campo: _numero(0) for campo in RECURSO_CAMPOS},
            "tipo_mochila": forms.Select(attrs={
                "data-capacidades": ",".join(f"{k}:{v}" for k, v in CAPACIDADE_MOCHILA.items())
            }),
            "foto": forms.FileInput(attrs={"accept": "image/*", "data-previa": "previa-foto"}),
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

    def clean_jogador(self):
        """Cada jogador (que não é mestre) pode ter UMA ficha. Mestres podem ter várias (NPCs)."""
        jogador = self.cleaned_data["jogador"]
        if not eh_mestre(jogador):
            outras = Ficha.objects.filter(jogador=jogador).exclude(pk=self.instance.pk)
            if outras.exists():
                raise forms.ValidationError(
                    "Este jogador já tem uma ficha. Cada jogador pode ter apenas uma."
                )
        return jogador

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
        widgets = {"item": forms.TextInput(attrs={"data-mochila-item": ""})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        estilizar(self)


class TrunfoFichaForm(forms.ModelForm):
    class Meta:
        model = TrunfoFicha
        fields = ["nome", "descricao"]
        widgets = {
            "nome": forms.TextInput(attrs={"list": "trunfos-sugeridos", "autocomplete": "off"}),
            "descricao": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        estilizar(self)


class BaseTrunfoFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        preenchidos = sum(
            1 for f in self.forms
            if getattr(f, "cleaned_data", None)
            and f.cleaned_data.get("nome") and not f.cleaned_data.get("DELETE")
        )
        if preenchidos > TRUNFOS_MAXIMO:
            raise forms.ValidationError(f"Cada personagem pode ter no máximo {TRUNFOS_MAXIMO} trunfos.")


TrunfoFormSet = forms.inlineformset_factory(
    Ficha, TrunfoFicha, form=TrunfoFichaForm, formset=BaseTrunfoFormSet,
    extra=TRUNFOS_MAXIMO, max_num=TRUNFOS_MAXIMO, validate_max=True, can_delete=True,
)

ArmaFormSet = forms.inlineformset_factory(
    Ficha, Arma, form=ArmaForm, extra=4, can_delete=True
)


class BaseMochilaFormSet(forms.BaseInlineFormSet):
    """Confere se a quantidade de itens cabe na mochila escolhida (comum 10, militar 15)."""

    capacidade = MOCHILA_MAXIMO  # a view ajusta conforme o tipo de mochila enviado

    def clean(self):
        super().clean()
        ocupados = sum(
            1 for f in self.forms
            if getattr(f, "cleaned_data", None)
            and f.cleaned_data.get("item") and not f.cleaned_data.get("DELETE")
        )
        if ocupados > self.capacidade:
            raise forms.ValidationError(
                f"A mochila escolhida comporta {self.capacidade} itens, mas há {ocupados}. "
                "Remova itens ou escolha a mochila militar."
            )


MochilaFormSet = forms.inlineformset_factory(
    Ficha, ItemMochila, form=ItemMochilaForm, formset=BaseMochilaFormSet,
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


# ------------------------------------------- Tabela de itens e envio em lote ----
class ItemModeloForm(forms.ModelForm):
    class Meta:
        model = ItemModelo
        fields = ["nome", "categoria", "descricao"]
        widgets = {"descricao": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        estilizar(self)


ItemModeloFormSet = forms.modelformset_factory(
    ItemModelo, form=ItemModeloForm, extra=5, can_delete=True
)


class EnvioItensForm(forms.Form):
    """O mestre escolhe fichas e itens (da tabela e/ou avulsos) e envia tudo de uma vez."""

    AVULSOS = 3

    fichas = forms.ModelMultipleChoiceField(
        queryset=Ficha.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        label="Enviar para (uma ou mais fichas)",
        error_messages={"required": "Escolha pelo menos uma ficha."},
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.itens = []
        self.fields["fichas"].queryset = Ficha.objects.select_related("jogador").order_by("nome_personagem")
        self.fields["fichas"].label_from_instance = (
            lambda f: f"{f.nome_personagem} (jogador: {f.jogador.get_username()})"
        )
        self.modelos = list(ItemModelo.objects.all())
        for m in self.modelos:
            self.fields[f"modelo_{m.pk}"] = forms.IntegerField(
                label=m.nome, required=False, min_value=0, max_value=999,
                widget=forms.NumberInput(attrs={"min": 0, "max": 999, "inputmode": "numeric"}),
            )
        for n in range(1, self.AVULSOS + 1):
            self.fields[f"avulso_nome_{n}"] = forms.CharField(
                label=f"Item avulso {n}", required=False, max_length=120
            )
            self.fields[f"avulso_qtd_{n}"] = forms.IntegerField(
                label=f"Quantidade do item avulso {n}", required=False, min_value=1, max_value=999,
                widget=forms.NumberInput(attrs={"min": 1, "max": 999, "inputmode": "numeric"}),
            )
        estilizar(self)

    def campos_modelos(self):
        return [(m, self[f"modelo_{m.pk}"]) for m in self.modelos]

    def campos_avulsos(self):
        return [(self[f"avulso_nome_{n}"], self[f"avulso_qtd_{n}"]) for n in range(1, self.AVULSOS + 1)]

    def clean(self):
        dados = super().clean()
        itens = []
        for m in self.modelos:
            quantidade = dados.get(f"modelo_{m.pk}")
            if quantidade:
                itens.append((m.nome, m.descricao, quantidade))
        for n in range(1, self.AVULSOS + 1):
            nome = (dados.get(f"avulso_nome_{n}") or "").strip()
            if nome:
                itens.append((nome, "", dados.get(f"avulso_qtd_{n}") or 1))
        if not itens and not self.errors:
            raise forms.ValidationError(
                "Escolha ao menos um item da tabela (quantidade maior que 0) ou digite um item avulso."
            )
        self.itens = itens
        return dados

    def enviar(self, usuario):
        """Cria os itens para cada ficha escolhida. Devolve (total de itens criados, nº de fichas)."""
        fichas = list(self.cleaned_data["fichas"])
        novos = [
            ItemEncontrado(ficha=ficha, nome=nome, descricao=descricao, quantidade=quantidade, criado_por=usuario)
            for ficha in fichas
            for nome, descricao, quantidade in self.itens
        ]
        ItemEncontrado.objects.bulk_create(novos)
        return len(novos), len(fichas)
