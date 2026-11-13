"""Views (páginas). Toda regra de acesso é aplicada AQUI, no servidor.

Padrão usado em todas as páginas:
- `@login_required`  -> precisa estar logado.
- `@mestre_required` -> precisa ser mestre (senão: 403 com mensagem clara).
- Fichas e itens são SEMPRE buscados por `.visiveis_para(request.user)`. Se o jogador tentar
  abrir a ficha de outra pessoa trocando o número na URL, a resposta é 404 (como se não existisse),
  sem revelar nada.
"""
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import (
    ArmaFormSet, EnvioItensForm, FichaJogadorForm, FichaMestreForm, ItemForm, ItemModeloFormSet,
    MochilaFormSet, TrunfoFormSet,
)
from .models import (
    CAPACIDADE_MOCHILA, PONTOS_SUGERIDOS, Ficha, ItemEncontrado, ItemMochila, TipoMochila, Trunfo, eh_mestre,
)


def mestre_required(view):
    @login_required
    @wraps(view)
    def envelope(request, *args, **kwargs):
        if not eh_mestre(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return envelope


def _obter_ficha(request, pk):
    return get_object_or_404(
        Ficha.objects.visiveis_para(request.user).select_related("jogador", "origem"), pk=pk
    )


def _classe_do_formulario(user):
    return FichaMestreForm if eh_mestre(user) else FichaJogadorForm


# ------------------------------------------------------------------ Início ----
@login_required
def inicio(request):
    fichas = Ficha.objects.visiveis_para(request.user)
    if not eh_mestre(request.user) and fichas.count() == 1:
        return redirect("ficha_detalhe", pk=fichas.first().pk)
    return redirect("ficha_lista")


# ------------------------------------------------------------------ Fichas ----
@login_required
def ficha_lista(request):
    fichas = Ficha.objects.visiveis_para(request.user).select_related("jogador", "origem")
    busca = request.GET.get("q", "").strip()
    if eh_mestre(request.user):
        fichas = fichas.annotate(n_itens=Count("itens", distinct=True))
        if busca:
            fichas = fichas.filter(
                Q(nome_personagem__icontains=busca) | Q(jogador__username__icontains=busca)
            )
    # Jogador só pode criar ficha se ainda não tiver uma. O mestre pode sempre.
    pode_criar = eh_mestre(request.user) or not fichas.exists()
    return render(
        request, "fichas/ficha_lista.html", {"fichas": fichas, "busca": busca, "pode_criar": pode_criar}
    )


@login_required
def ficha_detalhe(request, pk):
    ficha = _obter_ficha(request, pk)
    contexto = {
        "ficha": ficha,
        "armas": ficha.armas.all(),
        "mochila": ficha.mochila.all(),
        "proficiencias": ficha.proficiencias_escolhidas.select_related("proficiencia"),
        "trunfos": ficha.trunfos_escolhidos.all(),
        "itens": ficha.itens.all(),  # só chega aqui quem pode ver esta ficha
    }
    return render(request, "fichas/ficha_detalhe.html", contexto)


@login_required
def ficha_foto(request, pk):
    """Entrega a foto SOMENTE se o usuário pode ver a ficha (mestre ou dono)."""
    ficha = _obter_ficha(request, pk)
    if not ficha.foto:
        raise Http404
    resposta = FileResponse(ficha.foto.open("rb"), content_type="image/jpeg")
    resposta["Cache-Control"] = "private, max-age=300"
    resposta["X-Content-Type-Options"] = "nosniff"
    return resposta


def _salvar_ficha(request, ficha, titulo, novo):
    Formulario = _classe_do_formulario(request.user)
    if request.method == "POST":
        form = Formulario(request.POST, request.FILES, instance=ficha)
        armas = ArmaFormSet(request.POST, instance=ficha, prefix="arma")
        mochila = MochilaFormSet(request.POST, instance=ficha, prefix="mochila")
        trunfos = TrunfoFormSet(request.POST, instance=ficha, prefix="trunfo")
        mochila.capacidade = CAPACIDADE_MOCHILA.get(
            request.POST.get("tipo_mochila"), CAPACIDADE_MOCHILA[TipoMochila.COMUM]
        )
        validos = [form.is_valid(), armas.is_valid(), mochila.is_valid(), trunfos.is_valid()]
        if all(validos):
            with transaction.atomic():
                salva = form.save(commit=False)
                if not eh_mestre(request.user):
                    salva.jogador = request.user  # jogador nunca escolhe/troca o dono
                salva.save()
                form.save_m2m()
                form.salvar_proficiencias(salva)
                for conjunto in (armas, mochila, trunfos):
                    conjunto.instance = salva
                    conjunto.save()
            form.descartar_foto_antiga(salva)
            messages.success(request, f"Ficha de {salva.nome_personagem} salva com sucesso.")
            if salva.total_atributos != PONTOS_SUGERIDOS:
                messages.warning(
                    request,
                    f"Atenção: os atributos somam {salva.total_atributos} pontos e o livro "
                    f"sugere {PONTOS_SUGERIDOS}. A ficha foi salva mesmo assim.",
                )
            return redirect("ficha_detalhe", pk=salva.pk)
        messages.error(request, "Não foi possível salvar. Corrija os campos indicados abaixo.")
    else:
        form = Formulario(instance=ficha)
        armas = ArmaFormSet(instance=ficha, prefix="arma")
        mochila = MochilaFormSet(instance=ficha, prefix="mochila")
        trunfos = TrunfoFormSet(instance=ficha, prefix="trunfo")
    return render(
        request,
        "fichas/ficha_form.html",
        {"form": form, "armas": armas, "mochila": mochila, "trunfos": trunfos,
         "trunfos_sugeridos": Trunfo.objects.filter(ativo=True),
         "titulo": titulo, "novo": novo, "ficha": ficha},
    )


@login_required
def ficha_criar(request):
    if not eh_mestre(request.user):
        existente = Ficha.objects.filter(jogador=request.user).first()
        if existente:
            messages.warning(request, "Cada jogador pode ter apenas uma ficha. Esta é a sua.")
            return redirect("ficha_detalhe", pk=existente.pk)
    return _salvar_ficha(request, Ficha(), "Nova ficha", novo=True)


@login_required
def ficha_editar(request, pk):
    ficha = _obter_ficha(request, pk)
    return _salvar_ficha(request, ficha, f"Editar ficha: {ficha.nome_personagem}", novo=False)


@mestre_required
def ficha_excluir(request, pk):
    ficha = _obter_ficha(request, pk)
    if request.method == "POST":
        nome = ficha.nome_personagem
        ficha.delete()
        messages.success(request, f"Ficha de {nome} excluída.")
        return redirect("ficha_lista")
    return render(request, "fichas/ficha_confirmar_exclusao.html", {"ficha": ficha})


# ------------------------------------------------------------------- Itens ----
@mestre_required
def item_lista(request):
    itens = ItemEncontrado.objects.visiveis_para(request.user).select_related(
        "ficha", "ficha__jogador"
    )
    return render(request, "fichas/item_lista.html", {"itens": itens})


@mestre_required
def item_enviar(request):
    """Envia vários itens (da tabela e/ou avulsos) para uma ou mais fichas de uma só vez."""
    if request.method == "POST":
        form = EnvioItensForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                total, n_fichas = form.enviar(request.user)
            messages.success(
                request, f"{total} item(ns) enviado(s) para {n_fichas} ficha(s), em uma só operação."
            )
            return redirect("item_lista")
        messages.error(request, "Não foi possível enviar. Corrija os campos indicados abaixo.")
    else:
        inicial = {}
        ficha_id = request.GET.get("ficha", "")
        if ficha_id.isdigit():
            inicial["fichas"] = [int(ficha_id)]
        form = EnvioItensForm(initial=inicial)
    return render(request, "fichas/item_enviar.html", {"form": form})


@mestre_required
def item_modelos(request):
    """Tabela (planilha) de itens predefinidos do mestre: edita todas as linhas de uma vez."""
    if request.method == "POST":
        formset = ItemModeloFormSet(request.POST, prefix="modelo")
        if formset.is_valid():
            formset.save()
            messages.success(request, "Tabela de itens salva.")
            return redirect("item_modelos")
        messages.error(request, "Não foi possível salvar a tabela. Corrija as linhas indicadas.")
    else:
        formset = ItemModeloFormSet(prefix="modelo")
    return render(request, "fichas/item_modelos.html", {"formset": formset})


@mestre_required
def item_criar(request):
    if request.method == "POST":
        form = ItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.criado_por = request.user
            item.save()
            messages.success(
                request, f"Item “{item.nome}” atribuído a {item.ficha.nome_personagem}."
            )
            return redirect("item_lista")
        messages.error(request, "Não foi possível registrar o item. Corrija os campos abaixo.")
    else:
        inicial = {}
        ficha_id = request.GET.get("ficha", "")
        if ficha_id.isdigit():
            inicial["ficha"] = int(ficha_id)
        form = ItemForm(initial=inicial)
    return render(request, "fichas/item_form.html", {"form": form, "titulo": "Registrar item encontrado"})


@mestre_required
def item_editar(request, pk):
    item = get_object_or_404(ItemEncontrado.objects.visiveis_para(request.user), pk=pk)
    if request.method == "POST":
        form = ItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, f"Item “{item.nome}” atualizado.")
            return redirect("item_lista")
        messages.error(request, "Não foi possível salvar o item. Corrija os campos abaixo.")
    else:
        form = ItemForm(instance=item)
    return render(request, "fichas/item_form.html", {"form": form, "titulo": "Editar item encontrado"})


@mestre_required
def item_excluir(request, pk):
    item = get_object_or_404(ItemEncontrado.objects.visiveis_para(request.user), pk=pk)
    if request.method == "POST":
        nome = item.nome
        item.delete()
        messages.success(request, f"Item “{nome}” excluído.")
        return redirect("item_lista")
    return render(request, "fichas/item_confirmar_exclusao.html", {"item": item})


# ------------------------------------------------ Pegar / Deixar (jogador e mestre) ----
# Só aceitam POST (botões em formulário com CSRF). O acesso vale para quem pode ver a ficha:
# o mestre ou o dono. Para qualquer outra pessoa a resposta é 404.
@login_required
@require_POST
def item_pegar(request, pk):
    """Item encontrado -> mochila do personagem."""
    item = get_object_or_404(
        ItemEncontrado.objects.visiveis_para(request.user).select_related("ficha"), pk=pk
    )
    ficha = item.ficha
    if ficha.mochila.count() >= ficha.capacidade_mochila:
        messages.error(
            request,
            f"A mochila está cheia ({ficha.capacidade_mochila} itens). "
            f"Deixe algum item antes de pegar “{item.nome}”.",
        )
        return redirect("ficha_detalhe", pk=ficha.pk)
    nome = f"{item.nome} (×{item.quantidade})" if item.quantidade > 1 else item.nome
    with transaction.atomic():
        ItemMochila.objects.create(ficha=ficha, item=nome[:150])
        item.delete()
    messages.success(request, f"{ficha.nome_personagem} pegou “{item.nome}” e guardou na mochila.")
    return redirect("ficha_detalhe", pk=ficha.pk)


@login_required
@require_POST
def item_deixar(request, pk):
    """Item encontrado que o personagem escolhe NÃO pegar: fica marcado como deixado."""
    item = get_object_or_404(
        ItemEncontrado.objects.visiveis_para(request.user).select_related("ficha"), pk=pk
    )
    item.deixado = True
    item.save(update_fields=["deixado"])
    messages.success(request, f"“{item.nome}” foi deixado para trás. Dá para pegá-lo depois.")
    return redirect("ficha_detalhe", pk=item.ficha.pk)


@login_required
@require_POST
def mochila_deixar(request, pk):
    """Item da mochila -> volta para os itens encontrados, marcado como deixado."""
    visiveis = Ficha.objects.visiveis_para(request.user)
    item = get_object_or_404(ItemMochila.objects.select_related("ficha").filter(ficha__in=visiveis), pk=pk)
    ficha = item.ficha
    with transaction.atomic():
        ItemEncontrado.objects.create(
            ficha=ficha, nome=item.item[:120], quantidade=1, deixado=True, criado_por=request.user
        )
        item.delete()
    messages.success(request, f"{ficha.nome_personagem} deixou “{item.item}” para trás.")
    return redirect("ficha_detalhe", pk=ficha.pk)
