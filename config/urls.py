from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from fichas.forms import LoginForm

urlpatterns = [
    # Em produção, considere trocar "admin/" por um endereço menos óbvio.
    path("admin/", admin.site.urls),
    path(
        "entrar/",
        auth_views.LoginView.as_view(
            authentication_form=LoginForm, redirect_authenticated_user=True
        ),
        name="login",
    ),
    # O logout do Django 5 exige POST (botão em formulário com CSRF).
    path("sair/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("fichas.urls")),
]
