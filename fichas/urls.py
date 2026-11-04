from django.urls import path

from . import views

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("fichas/", views.ficha_lista, name="ficha_lista"),
    path("fichas/nova/", views.ficha_criar, name="ficha_criar"),
    path("fichas/<int:pk>/", views.ficha_detalhe, name="ficha_detalhe"),
    path("fichas/<int:pk>/editar/", views.ficha_editar, name="ficha_editar"),
    path("fichas/<int:pk>/excluir/", views.ficha_excluir, name="ficha_excluir"),
    # Itens encontrados: somente o mestre usa estas páginas.
    path("itens/", views.item_lista, name="item_lista"),
    path("itens/novo/", views.item_criar, name="item_criar"),
    path("itens/<int:pk>/editar/", views.item_editar, name="item_editar"),
    path("itens/<int:pk>/excluir/", views.item_excluir, name="item_excluir"),
]
