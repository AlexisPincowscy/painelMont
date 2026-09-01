"""
Admin do Django usado como ferramenta de VERIFICAÇÃO da modelagem.

Não faz parte do produto entregue à liderança — serve para conferir se a carga
gerou dados coerentes antes de confiar em qualquer número da tela.
"""
from django.contrib import admin

from . import models


@admin.register(models.Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ("nome", "slug", "unidade_valor", "peso_forecast_ritmo", "ciclo_esperado_dias")


@admin.register(models.EstagioCanonico)
class EstagioCanonicoAdmin(admin.ModelAdmin):
    list_display = ("empresa", "estagio_canonico", "estagio_origem", "ordem", "is_ganho")
    list_filter = ("empresa", "estagio_canonico")


@admin.register(models.Oportunidade)
class OportunidadeAdmin(admin.ModelAdmin):
    list_display = ("id", "empresa", "responsavel", "estagio_atual", "status",
                    "valor_potencial", "criada_em", "fechada_em")
    list_filter = ("empresa", "status", "estagio_atual")
    date_hierarchy = "criada_em"


@admin.register(models.Contrato)
class ContratoAdmin(admin.ModelAdmin):
    list_display = ("id", "empresa", "cliente", "data_assinatura", "valor_contratado",
                    "num_vidas", "volume_estruturado", "mrr")
    list_filter = ("empresa", "operadora")
    date_hierarchy = "data_assinatura"


@admin.register(models.Receita)
class ReceitaAdmin(admin.ModelAdmin):
    list_display = ("empresa", "data_reconhecimento", "natureza", "valor")
    list_filter = ("empresa", "natureza")
    date_hierarchy = "data_reconhecimento"


for m in (models.Lead, models.EventoEstagio, models.Entrega, models.InvestimentoMarketing,
          models.MetaPeriodo, models.Canal, models.Campanha, models.Cliente, models.Produto,
          models.Responsavel, models.Equipe, models.Operadora):
    admin.site.register(m)
