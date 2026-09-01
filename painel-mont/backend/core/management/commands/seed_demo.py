"""
Carga de dados DEMONSTRATIVOS.

Por que dados sintéticos: a base real não foi disponibilizada junto com o
briefing. A seção 14 rejeita "dados inexistentes apresentados como se fossem
reais", então a alternativa honesta é gerar dados claramente rotulados como
demonstração — a API devolve `dados_demonstrativos: true` em toda resposta e o
front exibe um aviso permanente.

O gerador é determinístico (semente fixa). Ele não sorteia números bonitos: ele
simula um funil por empresa, com probabilidade de passagem e duração por etapa
diferentes, e deixa a receita cair de acordo com o modelo de remuneração de
cada negócio. Alguns sinais foram plantados de propósito para que o motor de
alertas tenha o que detectar na demonstração — estão marcados com [SINAL].
"""
import datetime as dt
import random
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from core import models as m

SEED = 42
INICIO = dt.date(2025, 9, 1)
FIM = dt.date(2026, 8, 27)

OPERADORAS = ["Bradesco Saúde", "SulAmérica", "Amil", "Unimed", "Porto Saúde"]
PAISES = ["Estados Unidos", "Portugal", "Japão", "Irlanda", "Reino Unido", "Canadá"]
PORTES = ["MEI", "ME", "LTDA", "EIRELI"]
MOTIVOS_PERDA = ["preço", "prazo", "concorrente", "sem budget", "perdeu contato", "fora do perfil"]

# ---------------------------------------------------------------------------
# LACUNAS DE REGISTRO
#
# Nenhum CRM real tem 100% dos campos preenchidos, e uma tela de Saúde dos
# Dados onde está tudo verde não serve para nada. Estas probabilidades simulam
# a disciplina de registro de cada operação — e a variação POR RESPONSÁVEL é o
# que dá sentido ao ranking de quem registra bem.
# ---------------------------------------------------------------------------
DISCIPLINA_RESPONSAVEL = [0.97, 0.88, 0.74, 0.55, 0.41]   # por índice na equipe
LACUNA = {
    "campanha_sem_utm": 0.16,     # leads sem campanha identificada
    "sem_interacao": 0.11,        # oportunidades abertas sem última interação
    "montseguro_sem_vidas": 0.07,
    "prop5_sem_take_rate": 0.09,
    "techbrabo_sem_horas": 0.31,  # apontamento de horas é o mais irregular
}

# ---------------------------------------------------------------------------
# Perfis de funil por empresa. As probabilidades são de PASSAGEM entre estágios
# consecutivos; as durações são em dias (média, desvio).
# ---------------------------------------------------------------------------
PERFIS = {
    "montseguro": {
        "leads_dia": 14,
        "passagem": {"S1": 0.86, "S2": 0.79, "S3": 0.68, "S4": 0.46, "S5": 0.52},
        "duracao": {"S1": (1, 1), "S2": (2, 2), "S3": (3, 2), "S4": (4, 3), "S5": (5, 4), "S6": (12, 6)},
    },
    "prop5": {
        "leads_dia": 6,
        "passagem": {"S1": 0.76, "S2": 0.62, "S3": 0.54, "S4": 0.68, "S5": 0.56},
        "duracao": {"S1": (3, 2), "S2": (8, 5), "S3": (14, 8), "S4": (20, 11), "S5": (28, 14), "S6": (35, 15)},
    },
    "techbrabo": {
        "leads_dia": 1.2,
        "passagem": {"S1": 0.82, "S2": 0.72, "S3": 0.64, "S4": 0.58, "S5": 0.51},
        "duracao": {"S1": (2, 1), "S2": (4, 3), "S3": (7, 4), "S4": (9, 6), "S5": (11, 7), "S6": (28, 14)},
    },
}

CANAIS = [
    ("google-ads", "Google Ads", True),
    ("meta-ads", "Meta Ads", True),
    ("linkedin-ads", "LinkedIn Ads", True),
    ("indicacao", "Indicação", False),
    ("organico", "Orgânico", False),
    ("outbound", "Outbound", False),
]

# Mix de canal e custo por lead por empresa. O canal com CPL alto e conversão
# ruim é o que dispara o alerta R4 (canal queimando verba).
MIX_CANAL = {
    "montseguro": {"google-ads": 0.34, "meta-ads": 0.30, "organico": 0.16, "indicacao": 0.12, "outbound": 0.08},
    "prop5": {"meta-ads": 0.38, "google-ads": 0.20, "indicacao": 0.22, "organico": 0.12, "outbound": 0.08},
    "techbrabo": {"linkedin-ads": 0.36, "outbound": 0.28, "indicacao": 0.22, "organico": 0.14},
}
# Custo por lead por canal e por empresa, em reais. Ordens de grandeza de
# mercado: saúde empresarial < investimento patrimonial < tecnologia B2B.
CPL_BASE = {
    "montseguro": {"google-ads": 360, "meta-ads": 240, "organico": 0, "indicacao": 0, "outbound": 155},
    "prop5": {"meta-ads": 700, "google-ads": 960, "indicacao": 0, "organico": 0, "outbound": 325},
    "techbrabo": {"linkedin-ads": 1550, "outbound": 660, "indicacao": 0, "organico": 0},
}
# Multiplicador de qualidade do canal: quanto o lead daquele canal converte a
# mais ou a menos que a média da empresa.
QUALIDADE_CANAL = {
    "indicacao": 1.75, "organico": 1.15, "outbound": 1.05,
    "google-ads": 0.95, "meta-ads": 0.82, "linkedin-ads": 0.72,
}


class Command(BaseCommand):
    help = "Popula o banco com dados DEMONSTRATIVOS determinísticos (semente fixa)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Apaga tudo antes de carregar.")

    @transaction.atomic
    def handle(self, *args, **opts):
        rnd = random.Random(SEED)
        if opts["reset"]:
            for Model in (m.Receita, m.Entrega, m.Contrato, m.EventoEstagio, m.Oportunidade,
                          m.Lead, m.InvestimentoMarketing, m.MetaPeriodo, m.Campanha, m.Produto,
                          m.Cliente, m.Responsavel, m.Equipe, m.EstagioCanonico, m.Operadora,
                          m.Canal, m.Empresa):
                Model.objects.all().delete()

        empresas = self._empresas()
        canais = self._canais()
        operadoras = [m.Operadora.objects.create(nome=n) for n in OPERADORAS]
        self._estagios(empresas)
        equipes, responsaveis, produtos, campanhas = self._org(empresas, canais, rnd)
        self._metas(empresas)

        total = {}
        for slug, empresa in empresas.items():
            n = self._simular(empresa, canais, campanhas[slug], responsaveis[slug],
                              produtos[slug], operadoras, rnd)
            total[slug] = n
        self._investimento(empresas, canais, campanhas, rnd)

        self.stdout.write(self.style.SUCCESS(
            "Carga concluída (DADOS DEMONSTRATIVOS) — "
            + " · ".join(f"{k}: {v} leads" for k, v in total.items())
        ))
        self.stdout.write(
            f"  {m.Oportunidade.objects.count()} oportunidades · "
            f"{m.EventoEstagio.objects.count()} eventos de estágio · "
            f"{m.Contrato.objects.count()} contratos · "
            f"{m.Receita.objects.count()} lançamentos de receita"
        )

    # ------------------------------------------------------------------ setup
    def _empresas(self):
        dados = [
            dict(slug="montseguro", nome="Montseguro", cor="#1E3FD8",
                 descricao="Corretagem de planos de saúde empresariais",
                 unidade_valor="vida coberta", peso_forecast_ritmo=0.65, ciclo_esperado_dias=20),
            dict(slug="prop5", nome="Prop5 Investimentos", cor="#6B3FA0",
                 descricao="Consultoria e estruturação patrimonial para expatriados",
                 unidade_valor="operação estruturada", peso_forecast_ritmo=0.30, ciclo_esperado_dias=72),
            dict(slug="techbrabo", nome="TechBrabo", cor="#A6510B",
                 descricao="Tecnologia B2B, projetos digitais e sustentação",
                 unidade_valor="contrato / mês", peso_forecast_ritmo=0.40, ciclo_esperado_dias=45),
        ]
        return {d["slug"]: m.Empresa.objects.create(**d) for d in dados}

    def _canais(self):
        return {slug: m.Canal.objects.create(slug=slug, nome=nome, pago=pago)
                for slug, nome, pago in CANAIS}

    def _estagios(self, empresas):
        traducao = {
            "montseguro": ["Lead", "Atendimento", "Qualificação", "Cotação", "Proposta",
                           "Contratação", "Implantação concluída", "Carteira ativa"],
            "prop5": ["Lead", "Contato", "Qualificação", "Diagnóstico financeiro",
                      "Estratégia / oportunidade", "Aquisição", "Estruturação concluída",
                      "Acompanhamento"],
            "techbrabo": ["Lead", "Contato", "Qualificação", "Reunião + diagnóstico", "Proposta",
                          "Contrato assinado", "Entrega / go-live", "Sustentação"],
        }
        for slug, nomes in traducao.items():
            for i, (code, _) in enumerate(m.ESTAGIOS_CANONICOS):
                m.EstagioCanonico.objects.create(
                    empresa=empresas[slug], estagio_origem=nomes[i], estagio_canonico=code,
                    ordem=i + 1, is_ganho=(code == "S6"))

    def _org(self, empresas, canais, rnd):
        nomes = ["Ana Ribeiro", "Bruno Sato", "Carla Nunes", "Diego Alves", "Elisa Prado",
                 "Fábio Lima", "Gabi Rocha", "Heitor Dias", "Iris Campos", "João Meireles",
                 "Karina Souza", "Lucas Prado", "Marina Vieira", "Nuno Ferraz", "Olívia Braga"]
        produtos_por = {
            "montseguro": ["Plano PME", "Plano MEI", "Plano Adesão", "Plano Empresarial+"],
            "prop5": ["Imóvel para renda", "Consórcio imobiliário", "Crédito não residente",
                      "Carteira patrimonial"],
            "techbrabo": ["Plataforma web", "Integração / API", "Automação comercial",
                          "Sustentação mensal", "Dashboard de dados"],
        }
        equipes, responsaveis, produtos, campanhas = {}, {}, {}, {}
        i = 0
        for slug, empresa in empresas.items():
            eqs = [m.Equipe.objects.create(empresa=empresa, nome=n)
                   for n in (f"{empresa.nome} · Time A", f"{empresa.nome} · Time B")]
            equipes[slug] = eqs
            responsaveis[slug] = []
            for k in range(5):
                responsaveis[slug].append(m.Responsavel.objects.create(
                    empresa=empresa, equipe=eqs[k % 2], nome=nomes[i % len(nomes)],
                    ativo=not (slug == "montseguro" and k == 4)))  # 1 desligado: SCD preservado
                i += 1
            produtos[slug] = [m.Produto.objects.create(empresa=empresa, nome=n)
                              for n in produtos_por[slug]]
            campanhas[slug] = {}
            for canal_slug in MIX_CANAL[slug]:
                campanhas[slug][canal_slug] = [
                    m.Campanha.objects.create(empresa=empresa, canal=canais[canal_slug],
                                              nome=f"{canais[canal_slug].nome} · {suf}")
                    for suf in ("Sempre ativo", "Sazonal")]
        return equipes, responsaveis, produtos, campanhas

    def _metas(self, empresas):
        """Metas mensais de RECEITA RECONHECIDA — a mesma grandeza que o painel
        mede. Meta em outra unidade que não a do KPI é a origem mais comum de
        semáforo mentiroso."""
        base = {"montseguro": 385_000, "prop5": 230_000, "techbrabo": 256_000}
        for slug, empresa in empresas.items():
            ano, mes, i = INICIO.year, INICIO.month, 0
            while dt.date(ano, mes, 1) <= FIM:
                ini = dt.date(ano, mes, 1)
                prox = dt.date(ano + 1, 1, 1) if mes == 12 else dt.date(ano, mes + 1, 1)
                m.MetaPeriodo.objects.create(
                    empresa=empresa, inicio=ini, fim=prox - dt.timedelta(days=1),
                    valor=Decimal(round(base[slug] * (1.021 ** i), 2)))
                ano, mes, i = prox.year, prox.month, i + 1

    # -------------------------------------------------------------- simulação
    def _simular(self, empresa, canais, campanhas, responsaveis, produtos, operadoras, rnd):
        perfil = PERFIS[empresa.slug]
        mix = MIX_CANAL[empresa.slug]
        canal_slugs, pesos = list(mix.keys()), list(mix.values())

        leads, oportunidades, eventos = [], [], []
        contratos, entregas, receitas, clientes = [], [], [], []

        dia = INICIO
        n_leads = 0
        while dia <= FIM:
            # Menos leads no fim de semana; crescimento leve ao longo do período.
            fator_semana = 0.35 if dia.weekday() >= 5 else 1.0
            crescimento = 1 + 0.05 * ((dia - INICIO).days / 180)
            qtd = max(0, int(round(rnd.gauss(perfil["leads_dia"] * fator_semana * crescimento,
                                             max(0.6, perfil["leads_dia"] * 0.22)))))
            for _ in range(qtd):
                canal_slug = rnd.choices(canal_slugs, weights=pesos)[0]
                # Parte dos leads é de CLIENTE QUE JÁ EXISTE. Na Prop5 isso é o
                # próprio Método M5 funcionando (etapa 5, reinvestir); nas outras
                # é expansão de base. Sem isso, "operações por cliente" seria
                # sempre 1,00 e o indicador não mediria nada.
                taxa_retorno = {"prop5": 0.24, "montseguro": 0.07, "techbrabo": 0.18}[empresa.slug]
                if clientes and rnd.random() < taxa_retorno:
                    cliente = rnd.choice(clientes[-400:])
                else:
                    cliente = self._cliente(empresa, rnd)
                    clientes.append(cliente)
                lead = m.Lead(empresa=empresa, canal=canais[canal_slug],
                              # Parte dos leads chega sem campanha identificada.
                              # O painel marca como "não atribuído" — ratear
                              # seria inventar dado.
                              campanha=(None if rnd.random() < LACUNA["campanha_sem_utm"]
                                        else rnd.choice(campanhas[canal_slug])),
                              data_entrada=dia, cliente=cliente)
                leads.append((lead, canal_slug))
                n_leads += 1
            dia += dt.timedelta(days=1)

        m.Cliente.objects.bulk_create(clientes)
        # bulk_create não devolve pk em todos os backends: relemos para garantir
        # que as FKs de Lead apontem para registros realmente persistidos.
        salvos_cli = {c.nome: c for c in m.Cliente.objects.filter(empresa=empresa)}
        for lead, _ in leads:
            lead.cliente = salvos_cli[lead.cliente.nome]
        m.Lead.objects.bulk_create([l for l, _ in leads])
        # bulk_create com SQLite não preenche pk de forma confiável em versões
        # antigas; relemos para garantir integridade das FKs.
        salvos = list(m.Lead.objects.filter(empresa=empresa).order_by("id"))
        canal_por_lead = {salvos[i].id: leads[i][1] for i in range(len(salvos))}

        for lead in salvos:
            canal_slug = canal_por_lead[lead.id]
            qualidade = QUALIDADE_CANAL[canal_slug]
            idx_resp = rnd.randrange(len(responsaveis))
            op = m.Oportunidade(empresa=empresa, lead=lead,
                                responsavel=responsaveis[idx_resp],
                                produto=rnd.choice(produtos),
                                valor_potencial=Decimal(self._valor(empresa.slug, rnd)),
                                criada_em=lead.data_entrada, estagio_atual="S1",
                                ultima_interacao=lead.data_entrada)
            oportunidades.append((op, qualidade, canal_slug, idx_resp))
        m.Oportunidade.objects.bulk_create([o for o, _, _, _ in oportunidades])
        ops = list(m.Oportunidade.objects.filter(empresa=empresa).order_by("id"))
        extras = {ops[i].id: oportunidades[i][1:] for i in range(len(ops))}

        atualizar = []
        for op in ops:
            qualidade, canal_slug, idx_resp = extras[op.id]
            disciplina = DISCIPLINA_RESPONSAVEL[idx_resp % len(DISCIPLINA_RESPONSAVEL)]
            data = op.criada_em
            eventos.append(m.EventoEstagio(oportunidade=op, empresa=empresa,
                                           estagio_canonico="S1",
                                           data_hora=self._dh(data, rnd)))
            estagio_final = "S1"
            # 5 transições: chegar a S6 (fechamento) é ganhar. S6→S7 é
            # realização, modelada pela Entrega — não pelo funil comercial.
            for code in ("S1", "S2", "S3", "S4", "S5"):
                p = perfil["passagem"][code] * self._ajuste(empresa.slug, code, data, qualidade)
                if rnd.random() > min(p, 0.985):
                    op.status = "perdida"
                    # Registrar o motivo da perda depende da disciplina de quem
                    # perdeu a oportunidade — é exatamente o que a tela de Saúde
                    # dos Dados existe para expor.
                    op.motivo_perda = (rnd.choice(MOTIVOS_PERDA)
                                       if rnd.random() < disciplina else "")
                    op.fechada_em = data
                    break
                mu, sd = perfil["duracao"][code]
                data = data + dt.timedelta(days=max(1, int(rnd.gauss(mu, sd))))
                if data > FIM:
                    break  # ainda em andamento: fica aberta no estágio atual
                # Parte das oportunidades simplesmente PARA de avançar sem ser
                # marcada como perdida — é o que acontece em qualquer CRM real,
                # e é o que o indicador de aging existe para revelar.
                if rnd.random() < 0.045:
                    break
                proximo = f"S{int(code[1]) + 1}"
                eventos.append(m.EventoEstagio(oportunidade=op, empresa=empresa,
                                               estagio_canonico=proximo,
                                               data_hora=self._dh(data, rnd)))
                estagio_final = proximo
                op.ultima_interacao = data

            if op.status == "aberta" and rnd.random() < LACUNA["sem_interacao"] * (2 - disciplina):
                op.ultima_interacao = None
            op.estagio_atual = estagio_final
            if estagio_final == "S6" and op.status != "perdida":
                op.status = "ganha"
                op.fechada_em = data
                c, e, rs = self._fechar(empresa, op, data, operadoras, rnd)
                contratos.append(c)
                entregas.append(e)
                receitas.extend(rs)
            atualizar.append(op)

        m.Oportunidade.objects.bulk_update(
            atualizar, ["estagio_atual", "status", "fechada_em", "motivo_perda", "ultima_interacao"])
        m.EventoEstagio.objects.bulk_create(eventos, batch_size=2000)
        m.Contrato.objects.bulk_create(contratos, batch_size=1000)

        # Reassociar entregas e receitas aos contratos já persistidos.
        salvos_c = {c.oportunidade_id: c for c in m.Contrato.objects.filter(empresa=empresa)}
        for e in entregas:
            e.contrato = salvos_c[e.contrato.oportunidade_id]
        for r in receitas:
            r.contrato = salvos_c[r.contrato.oportunidade_id]
        m.Entrega.objects.bulk_create(entregas, batch_size=1000)
        m.Receita.objects.bulk_create(receitas, batch_size=2000)
        return n_leads

    # ---------------------------------------------------------------- helpers
    def _ajuste(self, slug, code, data, qualidade):
        """
        Ajustes de conversão. Além da qualidade do canal, aqui ficam os [SINAL]
        plantados para que o motor de alertas tenha o que detectar na demo.
        """
        fator = 1 + (qualidade - 1) * 0.45
        # [SINAL R2] Montseguro: queda de cotação → proposta nas últimas semanas.
        if slug == "montseguro" and code == "S4" and data >= FIM - dt.timedelta(days=17):
            fator *= 0.74
        # [SINAL R9] Indicação melhorando na Montseguro nas últimas semanas.
        # Empresa de ciclo curto: a coorte recente já matura o suficiente para
        # o alerta positivo ser detectável.
        if slug == "montseguro" and qualidade > 1.5 and data >= FIM - dt.timedelta(days=50):
            fator *= 1.35
        return fator

    def _cliente(self, empresa, rnd):
        n = rnd.randint(1000, 9999)
        if empresa.slug == "montseguro":
            return m.Cliente(empresa=empresa, nome=f"Empresa {n}", porte_cnpj=rnd.choices(
                PORTES, weights=[0.34, 0.31, 0.26, 0.09])[0])
        if empresa.slug == "prop5":
            return m.Cliente(empresa=empresa, nome=f"Investidor {n}", pais_residencia=rnd.choices(
                PAISES, weights=[0.41, 0.19, 0.13, 0.11, 0.09, 0.07])[0])
        return m.Cliente(empresa=empresa, nome=f"Cliente {n}",
                         origem_cliente=rnd.choices(["grupo", "mercado"], weights=[0.44, 0.56])[0])

    def _valor(self, slug, rnd):
        if slug == "montseguro":
            return round(rnd.lognormvariate(10.95, 0.85), 2)   # prêmio anual estimado
        if slug == "prop5":
            return round(rnd.lognormvariate(13.1, 0.7), 2)     # volume a estruturar
        return round(rnd.lognormvariate(10.75, 0.7), 2)        # valor do projeto

    def _dh(self, d, rnd):
        return dt.datetime.combine(d, dt.time(rnd.randint(8, 18), rnd.randint(0, 59)),
                                   tzinfo=dt.timezone.utc)

    def _fechar(self, empresa, op, data, operadoras, rnd):
        """Cria contrato, entrega e o cronograma de receita conforme o modelo de
        remuneração de cada empresa. É aqui que 'contrato' vira (ou não) receita."""
        cliente = op.lead.cliente
        c = m.Contrato(empresa=empresa, oportunidade=op, cliente=cliente,
                       data_assinatura=data, valor_contratado=op.valor_potencial)
        receitas = []

        if empresa.slug == "montseguro":
            # O contrato DERIVA do valor da oportunidade (prêmio anual estimado),
            # com desvio de negociação. Sem esse vínculo, pipeline e receita
            # ficariam em escalas independentes e o forecast perderia sentido.
            premio_anual = float(op.valor_potencial) * rnd.uniform(0.85, 1.15)
            premio_vida = rnd.uniform(190, 720)
            c.premio_mensal = Decimal(round(premio_anual / 12, 2))
            c.num_vidas = (None if rnd.random() < LACUNA["montseguro_sem_vidas"]
                           else max(1, round(premio_anual / 12 / premio_vida)))
            c.valor_contratado = c.premio_mensal * 12
            # Concentração em uma operadora — o alerta R7 é real na base.
            c.operadora = rnd.choices(operadoras, weights=[0.44, 0.21, 0.14, 0.13, 0.08])[0]
            dias_impl = max(3, int(rnd.gauss(16, 7)))
            inicio_vigencia = data + dt.timedelta(days=dias_impl)
            # Agenciamento: 1,5 prêmio mensal, reconhecido na vigência (não na assinatura).
            if inicio_vigencia <= FIM:
                receitas.append(m.Receita(empresa=empresa, contrato=c,
                                          data_reconhecimento=inicio_vigencia,
                                          valor=c.premio_mensal * Decimal("1.5"),
                                          natureza=m.NaturezaReceita.AGENCIAMENTO))
            # Corretagem recorrente: 3,2% do prêmio, todo mês enquanto vigente.
            # 8% dos contratos caem em até 90 dias — o indicador de qualidade da venda.
            cancela = rnd.random() < 0.08
            if cancela:
                c.data_cancelamento = data + dt.timedelta(days=rnd.randint(25, 88))
            mes = inicio_vigencia
            while mes <= FIM:
                if c.data_cancelamento and mes > c.data_cancelamento:
                    break
                receitas.append(m.Receita(empresa=empresa, contrato=c, data_reconhecimento=mes,
                                          valor=c.premio_mensal * Decimal("0.032"),
                                          natureza=m.NaturezaReceita.CORRETAGEM))
                mes += dt.timedelta(days=30)
            entrega = m.Entrega(contrato=c, empresa=empresa, data_prevista=data + dt.timedelta(days=15),
                                data_conclusao=inicio_vigencia if inicio_vigencia <= FIM else None,
                                status="concluida" if inicio_vigencia <= FIM else
                                ("atrasada" if data + dt.timedelta(days=15) < FIM else "em_andamento"))

        elif empresa.slug == "prop5":
            c.volume_estruturado = op.valor_potencial
            take = round(rnd.uniform(0.035, 0.062), 4)
            # Take rate nem sempre é registrado no fechamento; quando falta, o
            # painel não consegue separar volume de receita naquele contrato.
            c.take_rate = None if rnd.random() < LACUNA["prop5_sem_take_rate"] else take
            comissao = c.volume_estruturado * Decimal(str(take))
            c.valor_contratado = comissao
            # Comissão em duas parcelas: 60% na estruturação, 40% em 45 dias.
            estruturacao = data + dt.timedelta(days=max(5, int(rnd.gauss(28, 12))))
            for atraso, frac in ((0, Decimal("0.6")), (45, Decimal("0.4"))):
                quando = estruturacao + dt.timedelta(days=atraso)
                if quando <= FIM:
                    receitas.append(m.Receita(empresa=empresa, contrato=c, data_reconhecimento=quando,
                                              valor=comissao * frac,
                                              natureza=m.NaturezaReceita.COMISSAO))
            entrega = m.Entrega(contrato=c, empresa=empresa,
                                data_prevista=data + dt.timedelta(days=30),
                                data_conclusao=estruturacao if estruturacao <= FIM else None,
                                status="concluida" if estruturacao <= FIM else
                                ("atrasada" if data + dt.timedelta(days=30) < FIM else "em_andamento"))

        else:  # techbrabo
            recorrente = rnd.random() < 0.55
            c.mrr = Decimal(round(rnd.uniform(1800, 7500), 2)) if recorrente else None
            # Horas derivadas do preço de venda (taxa/hora praticada) e custo
            # interno abaixo dela — é o que dá margem realista e permite medir
            # ocupação contra a capacidade instalada.
            taxa_hora = rnd.uniform(115, 150)
            horas = max(40, int(float(op.valor_potencial) / taxa_hora))
            prazo = max(20, int(horas / 12))
            # Apontamento de horas é o registro mais irregular da operação — e
            # é justamente o único dado de custo do grupo inteiro.
            if rnd.random() < LACUNA["techbrabo_sem_horas"]:
                c.horas_estimadas = c.custo_horas = None
            else:
                c.horas_estimadas = horas
                c.custo_horas = Decimal(round(horas * rnd.uniform(52, 78), 2))
            # [SINAL R6] a partir de julho a entrega começa a acumular atraso.
            atraso_extra = 20 if data >= dt.date(2026, 7, 1) else 0
            go_live = data + dt.timedelta(days=max(12, int(rnd.gauss(prazo + atraso_extra, 10))))
            # Receita pontual em 2 marcos: 40% na assinatura, 60% no go-live.
            receitas.append(m.Receita(empresa=empresa, contrato=c, data_reconhecimento=data,
                                      valor=op.valor_potencial * Decimal("0.4"),
                                      natureza=m.NaturezaReceita.PROJETO))
            if go_live <= FIM:
                receitas.append(m.Receita(empresa=empresa, contrato=c, data_reconhecimento=go_live,
                                          valor=op.valor_potencial * Decimal("0.6"),
                                          natureza=m.NaturezaReceita.PROJETO))
                if c.mrr:
                    mes = go_live
                    while mes <= FIM:
                        receitas.append(m.Receita(empresa=empresa, contrato=c,
                                                  data_reconhecimento=mes, valor=c.mrr,
                                                  natureza=m.NaturezaReceita.RECORRENTE))
                        mes += dt.timedelta(days=30)
            prevista = data + dt.timedelta(days=prazo)
            entrega = m.Entrega(contrato=c, empresa=empresa, data_prevista=prevista,
                                data_conclusao=go_live if go_live <= FIM else None,
                                status="concluida" if go_live <= FIM else
                                ("atrasada" if prevista < FIM else "em_andamento"))

        return c, entrega, receitas

    def _investimento(self, empresas, canais, campanhas, rnd):
        """
        Investimento diário por canal. Calibrado para bater aproximadamente com
        CPL × volume de leads — é o que torna CAC e ROAS críveis.
        [SINAL R4] LinkedIn Ads da TechBrabo com verba alta e retorno ruim.
        """
        registros = []
        for slug, empresa in empresas.items():
            for canal_slug, share in MIX_CANAL[slug].items():
                cpl = CPL_BASE[slug][canal_slug]
                if cpl == 0:
                    continue  # canal não pago: sem investimento direto
                dia = INICIO
                while dia <= FIM:
                    fator = 0.35 if dia.weekday() >= 5 else 1.0
                    base = PERFIS[slug]["leads_dia"] * share * cpl * fator
                    if slug == "techbrabo" and canal_slug == "linkedin-ads" and dia >= dt.date(2026, 6, 15):
                        base *= 1.55
                    registros.append(m.InvestimentoMarketing(
                        empresa=empresa, canal=canais[canal_slug],
                        campanha=rnd.choice(campanhas[slug][canal_slug]), data=dia,
                        valor=Decimal(round(max(0, rnd.gauss(base, base * 0.15)), 2))))
                    dia += dt.timedelta(days=1)
        m.InvestimentoMarketing.objects.bulk_create(registros, batch_size=2000)
