"""Modelos de dados.

Resumo:
- Perfil: guarda o papel (mestre ou jogador) de cada usuário.
- Origem, Proficiencia, Trunfo: catálogos que o mestre edita pelo painel /admin/.
- Ficha: o personagem. FichaProficiencia liga a ficha às proficiências (com nível e bônus).
- ItemEncontrado: itens privados atribuídos a uma ficha pelo mestre.
"""
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


# ---------------------------------------------------------------- Papéis ----
class Papel(models.TextChoices):
    MESTRE = "mestre", "Mestre"
    JOGADOR = "jogador", "Jogador"


class Perfil(models.Model):
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="perfil",
        verbose_name="usuário",
    )
    papel = models.CharField(
        "papel", max_length=10, choices=Papel.choices, default=Papel.JOGADOR
    )

    class Meta:
        verbose_name = "perfil"
        verbose_name_plural = "perfis"

    def __str__(self):
        return f"{self.usuario} ({self.get_papel_display()})"


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def criar_perfil_do_usuario(sender, instance, created, **kwargs):
    """Todo usuário novo nasce JOGADOR. O mestre é criado só pelo comando criar_mestre."""
    if created:
        Perfil.objects.get_or_create(usuario=instance)


def eh_mestre(user):
    """Única função que decide quem é mestre. Todas as verificações do servidor usam ela."""
    if user is None or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    perfil = getattr(user, "perfil", None)
    return perfil is not None and perfil.papel == Papel.MESTRE


# ------------------------------------------------------------- Catálogos ----
class ItemCatalogo(models.Model):
    """Base comum para Origem, Proficiência e Trunfo (configuráveis pelo mestre)."""

    nome = models.CharField("nome", max_length=100, unique=True)
    descricao = models.TextField("descrição", blank=True)
    ativo = models.BooleanField(
        "disponível para novas fichas",
        default=True,
        help_text="Desmarque para esconder das novas fichas sem apagar das fichas existentes.",
    )

    class Meta:
        abstract = True
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Origem(ItemCatalogo):
    class Meta(ItemCatalogo.Meta):
        verbose_name = "origem"
        verbose_name_plural = "origens"


class Proficiencia(ItemCatalogo):
    class Meta(ItemCatalogo.Meta):
        verbose_name = "proficiência"
        verbose_name_plural = "proficiências"


class Trunfo(ItemCatalogo):
    class Meta(ItemCatalogo.Meta):
        verbose_name = "trunfo"
        verbose_name_plural = "trunfos"


# ----------------------------------------------------------------- Ficha ----
# (campo no banco, nome completo, sigla)
ATRIBUTOS = [
    ("cor", "Corpo", "COR"),
    ("inteligencia", "Inteligência", "INT"),
    ("percepcao", "Percepção", "PER"),
    ("influencia", "Influência", "INF"),
    ("resistencia", "Resistência", "RES"),
    ("tecnica", "Técnica", "TEC"),
    ("sangue_frio", "Sangue Frio", "SF"),
]
ATRIBUTO_CAMPOS = [campo for campo, _, _ in ATRIBUTOS]
PONTOS_SUGERIDOS = 21  # orientação do livro; não é validação rígida


def _atributo(rotulo):
    return models.PositiveSmallIntegerField(
        rotulo, default=1, validators=[MinValueValidator(1), MaxValueValidator(10)]
    )


class FichaQuerySet(models.QuerySet):
    def visiveis_para(self, user):
        """REGRA CENTRAL DE ACESSO: mestre vê todas; jogador vê só as próprias."""
        if eh_mestre(user):
            return self.all()
        if user is not None and user.is_authenticated:
            return self.filter(jogador=user)
        return self.none()


class Ficha(models.Model):
    jogador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="fichas",
        verbose_name="jogador responsável",
    )
    nome_personagem = models.CharField("nome do personagem", max_length=100)
    origem = models.ForeignKey(
        Origem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fichas",
        verbose_name="origem",
    )

    cor = _atributo("Corpo (COR)")
    inteligencia = _atributo("Inteligência (INT)")
    percepcao = _atributo("Percepção (PER)")
    influencia = _atributo("Influência (INF)")
    resistencia = _atributo("Resistência (RES)")
    tecnica = _atributo("Técnica (TEC)")
    sangue_frio = _atributo("Sangue Frio (SF)")

    # Valores atuais (só o mestre altera). Máximos: automáticos, com ajuste manual opcional.
    sf_atual = models.PositiveSmallIntegerField("Sangue Frio atual", null=True, blank=True)
    sf_max_manual = models.PositiveSmallIntegerField(
        "Sangue Frio máximo", null=True, blank=True,
        help_text="Deixe em branco para usar o padrão: SF × 3.",
    )
    anticorpos_atual = models.PositiveSmallIntegerField("Anticorpos atuais", null=True, blank=True)
    anticorpos_max_manual = models.PositiveSmallIntegerField(
        "Anticorpos máximos", null=True, blank=True,
        help_text="Deixe em branco para usar o padrão: RES × 10.",
    )

    trunfos = models.ManyToManyField(Trunfo, blank=True, related_name="fichas", verbose_name="trunfos")
    qualidades = models.TextField("qualidades", blank=True)
    defeitos = models.TextField("defeitos", blank=True)
    inventario = models.TextField(
        "inventário", blank=True,
        help_text="Itens comuns do personagem. Os itens encontrados na exploração ficam em área separada.",
    )

    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    objects = FichaQuerySet.as_manager()

    class Meta:
        ordering = ["nome_personagem"]
        verbose_name = "ficha"
        verbose_name_plural = "fichas"

    def __str__(self):
        return self.nome_personagem

    # Máximos: valor manual (se o mestre definiu) ou a regra padrão do livro.
    @property
    def sf_max(self):
        return self.sf_max_manual if self.sf_max_manual is not None else self.sangue_frio * 3

    @property
    def anticorpos_max(self):
        if self.anticorpos_max_manual is not None:
            return self.anticorpos_max_manual
        return self.resistencia * 10

    @property
    def atributos_lista(self):
        return [(sigla, nome, getattr(self, campo)) for campo, nome, sigla in ATRIBUTOS]

    @property
    def total_atributos(self):
        return sum(getattr(self, campo) for campo in ATRIBUTO_CAMPOS)

    def save(self, *args, **kwargs):
        # Ficha nova (ou valor atual em branco) começa com os valores cheios.
        if self.sf_atual is None:
            self.sf_atual = self.sf_max
        if self.anticorpos_atual is None:
            self.anticorpos_atual = self.anticorpos_max
        super().save(*args, **kwargs)


class FichaProficiencia(models.Model):
    ficha = models.ForeignKey(
        Ficha, on_delete=models.CASCADE, related_name="proficiencias_escolhidas"
    )
    proficiencia = models.ForeignKey(
        Proficiencia, on_delete=models.PROTECT, verbose_name="proficiência"
    )
    nivel = models.PositiveSmallIntegerField("nível", default=1)
    bonus = models.SmallIntegerField("bônus", default=0)

    class Meta:
        ordering = ["proficiencia__nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["ficha", "proficiencia"], name="proficiencia_unica_por_ficha"
            )
        ]
        verbose_name = "proficiência da ficha"
        verbose_name_plural = "proficiências da ficha"

    def __str__(self):
        return f"{self.proficiencia} (nível {self.nivel}, bônus {self.bonus:+d})"


# ------------------------------------------------------ Itens encontrados ----
class ItemQuerySet(models.QuerySet):
    def visiveis_para(self, user):
        """Mestre vê todos os itens; jogador vê só os da própria ficha."""
        if eh_mestre(user):
            return self.all()
        if user is not None and user.is_authenticated:
            return self.filter(ficha__jogador=user)
        return self.none()


class ItemEncontrado(models.Model):
    ficha = models.ForeignKey(
        Ficha, on_delete=models.CASCADE, related_name="itens", verbose_name="ficha destinatária"
    )
    nome = models.CharField("nome do item", max_length=120)
    descricao = models.TextField("descrição", blank=True)
    quantidade = models.PositiveIntegerField(
        "quantidade", default=1, validators=[MinValueValidator(1)]
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    objects = ItemQuerySet.as_manager()

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "item encontrado"
        verbose_name_plural = "itens encontrados"

    def __str__(self):
        return f"{self.nome} → {self.ficha}"
