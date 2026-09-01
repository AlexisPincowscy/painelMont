from django.contrib import admin
from django.urls import path

urlpatterns = [
    # O admin existe para conferir os dados carregados — é uma ferramenta de
    # verificação de modelagem, não parte do produto entregue à liderança.
    path("admin/", admin.site.urls),
]
