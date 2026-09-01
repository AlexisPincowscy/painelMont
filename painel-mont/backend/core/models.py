"""
Modelo dimensional do Painel Executivo do Grupo Mont.

Princípio: UM modelo físico, TRÊS semânticas de negócio.

  - Dimensões conformadas (tempo, empresa, canal, campanha, responsável,
    cliente, produto, estágio canônico) são compartilhadas pelas três empresas.
    São elas que tornam a comparação possível.

  - Dimensões próprias (operadora na Montseguro, país de residência na Prop5,
    natureza de receita na TechBrabo) existem só onde fazem sentido.
    São elas que impedem o achatamento.

  - Granularidade de EVENTO, não de estado. EventoEstagio guarda cada transição
    com data e hora. Sem isso não existe ciclo médio nem análise de gargalo —
    só uma fotografia do "onde cada oportunidade está agora".
"""
from django.db import models

# ---------------------------------------------------------------------------
# Vocabulário canônico de estágios
# ---------------------------------------------------------------------------
ESTAGIOS_CANONICOS = [
    ("S1", "Entrada"),
    ("S2", "Contato"),
    ("S3", "Qualificação"),
    ("S4", "Descoberta"),
    ("S5", "Solução formal"),
    ("S6", "Fechamento"),
    ("S7", "Realização"),
    ("S8", "Continuidade"),
]
ORDEM_ESTAGIO = {code: i + 1 for i, (code, _) in enumerate(ESTAGIOS_CANONICOS)}


class NaturezaReceita(models.TextChoices):
    """
    A distinção que impede o erro central do desafio: somar coisas que não são
    a mesma coisa. Só `is_reconhecida` entra na Receita Reconhecida do Grupo.
    """

    AGENCIAMENTO = "agenciamento", "Comissão de agenciamento (pontual)"
    CORRETAGEM = "corretagem", "Corretagem recorrente (carteira)"
    COMISSAO = "comissao", "Comissão sobre operação estruturada"
    PROJETO = "projeto", "Receita pontual de projeto (marco entregue)"
    RECORRENTE = "recorrente", "Receita recorrente / MRR"


# ---------------------------------------------------------------------------
# DIMENSÕES CONFORMADAS
# ---------------------------------------------------------------------------
class Empresa(models.Model):
    slug = models.SlugField(unique=True)
    nome = models.CharField(max_length=80)
    descricao = models.CharField(max_length=200)
    unidade_valor = models.CharField(
        max_length=40,
        help_text="A unidade real do negócio: vida, operação estruturada, contrato/mês.",
    )
    cor = models.CharField(max_length=7, default="#1E3FD8")
    # Peso do componente de RITMO no forecast híbrido. Negócio transacional com
    # muitos fechamentos por mês tem ritmo confiável (w alto); negócio de ciclo
    # longo e poucos fechamentos grandes tem ritmo ruidoso (w baixo), e ali o
    # funil prevê melhor. É hipótese declarada e recalibrável, não constante mágica.
    peso_forecast_ritmo = models.FloatField(default=0.5)
    ciclo_esperado_dias = models.PositiveIntegerField(default=30)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Equipe(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="equipes")
    nome = models.CharField(max_length=80)

    def __str__(self):
        return f"{self.nome} ({self.empresa.slug})"


class Responsavel(models.Model):
    """Vendedor / consultor. SCD tipo 2 simplificado: `ativo` preserva o
    histórico de produtividade de quem saiu, em vez de apagar suas vendas."""

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="responsaveis")
    equipe = models.ForeignKey(Equipe, on_delete=models.SET_NULL, null=True, related_name="membros")
    nome = models.CharField(max_length=80)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Canal(models.Model):
    slug = models.SlugField(unique=True)
    nome = models.CharField(max_length=60)
    pago = models.BooleanField(default=True)

    def __str__(self):
        return self.nome


class Campanha(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="campanhas")
    canal = models.ForeignKey(Canal, on_delete=models.CASCADE, related_name="campanhas")
    nome = models.CharField(max_length=100)

    def __str__(self):
        return self.nome


class Produto(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="produtos")
    nome = models.CharField(max_length=80)

    def __str__(self):
        return self.nome


class Cliente(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="clientes")
    nome = models.CharField(max_length=120)
    # Dimensões próprias, preenchidas apenas onde o negócio as tem:
    porte_cnpj = models.CharField(max_length=20, blank=True)       # Montseguro
    pais_residencia = models.CharField(max_length=40, blank=True)  # Prop5
    origem_cliente = models.CharField(max_length=20, blank=True)   # TechBrabo: grupo|mercado

    def __str__(self):
        return self.nome


class Operadora(models.Model):
    """Dimensão exclusiva da Montseguro."""

    nome = models.CharField(max_length=60, unique=True)

    def __str__(self):
        return self.nome


class EstagioCanonico(models.Model):
    """
    A TABELA DE TRADUÇÃO.

    Cada empresa mantém o nome real do seu estágio na visão individual, e o
    painel de grupo lê tudo pelo código canônico. Adicionar uma quarta empresa
    ao grupo passa a ser inserir linhas aqui — não alterar telas.
    """

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="estagios")
    estagio_origem = models.CharField(max_length=60)
    estagio_canonico = models.CharField(max_length=2, choices=ESTAGIOS_CANONICOS)
    ordem = models.PositiveSmallIntegerField()
    is_ganho = models.BooleanField(default=False)

    class Meta:
        ordering = ["empresa", "ordem"]
        unique_together = [("empresa", "estagio_canonico")]

    def __str__(self):
        return f"{self.empresa.slug}:{self.estagio_canonico}={self.estagio_origem}"


# ---------------------------------------------------------------------------
# FATOS
# ---------------------------------------------------------------------------
class Lead(models.Model):
    """Grão: 1 linha por lead. Origem do CAC e do ROAS."""

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="leads")
    canal = models.ForeignKey(Canal, on_delete=models.PROTECT, related_name="leads")
    campanha = models.ForeignKey(Campanha, on_delete=models.SET_NULL, null=True, related_name="leads")
    data_entrada = models.DateField(db_index=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True, related_name="leads")

    class Meta:
        indexes = [models.Index(fields=["empresa", "data_entrada"])]


class Oportunidade(models.Model):
    """
    Grão: 1 linha por oportunidade.

    `lead` é a chave que sustenta todo o painel de marketing: sem propagar a
    origem do lead até a receita, CAC e ROAS por canal viram rateio — e rateio
    não responde onde investir.
    """

    STATUS = [("aberta", "Aberta"), ("ganha", "Ganha"), ("perdida", "Perdida")]

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="oportunidades")
    lead = models.OneToOneField(Lead, on_delete=models.CASCADE, related_name="oportunidade")
    responsavel = models.ForeignKey(Responsavel, on_delete=models.PROTECT, related_name="oportunidades")
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, related_name="oportunidades")
    valor_potencial = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    estagio_atual = models.CharField(max_length=2, choices=ESTAGIOS_CANONICOS, default="S1")
    status = models.CharField(max_length=10, choices=STATUS, default="aberta")
    criada_em = models.DateField(db_index=True)
    ultima_interacao = models.DateField(null=True, blank=True)
    fechada_em = models.DateField(null=True, blank=True, db_index=True)
    motivo_perda = models.CharField(max_length=60, blank=True)

    class Meta:
        indexes = [models.Index(fields=["empresa", "status", "criada_em"])]

    @property
    def ordem_estagio(self) -> int:
        return ORDEM_ESTAGIO[self.estagio_atual]


class EventoEstagio(models.Model):
    """
    Grão: 1 linha por MUDANÇA de estágio.

    É a tabela que separa um painel que mostra "onde estamos" de um painel que
    mostra "onde perdemos e quanto tempo levamos". Conversão entre etapas e
    ciclo médio são calculados a partir daqui, nunca do estágio atual.
    """

    oportunidade = models.ForeignKey(Oportunidade, on_delete=models.CASCADE, related_name="eventos")
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="eventos")
    estagio_canonico = models.CharField(max_length=2, choices=ESTAGIOS_CANONICOS)
    data_hora = models.DateTimeField(db_index=True)

    class Meta:
        indexes = [models.Index(fields=["empresa", "estagio_canonico", "data_hora"])]
        ordering = ["data_hora"]


class Contrato(models.Model):
    """
    Grão: 1 linha por contrato fechado (S6).

    ATENÇÃO à distinção que o briefing cobra: `valor_contratado` e
    `volume_estruturado` NÃO são receita. Receita está em `Receita`, e só
    existe quando é reconhecida.
    """

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="contratos")
    oportunidade = models.OneToOneField(Oportunidade, on_delete=models.CASCADE, related_name="contrato")
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="contratos")
    data_assinatura = models.DateField(db_index=True)
    valor_contratado = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # --- Montseguro ---
    operadora = models.ForeignKey(Operadora, on_delete=models.SET_NULL, null=True, blank=True)
    num_vidas = models.PositiveIntegerField(null=True, blank=True)
    premio_mensal = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    data_cancelamento = models.DateField(null=True, blank=True)

    # --- Prop5 ---
    volume_estruturado = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    take_rate = models.FloatField(null=True, blank=True)

    # --- TechBrabo ---
    mrr = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    horas_estimadas = models.PositiveIntegerField(null=True, blank=True)
    custo_horas = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    @property
    def premio_anualizado(self):
        return (self.premio_mensal or 0) * 12


class Entrega(models.Model):
    """
    Grão: 1 linha por implantação/entrega. A ponte S6 → S7.

    Vender e não realizar é o vazamento mais caro e mais invisível das três
    operações. Sem esta tabela ele não aparece em lugar nenhum.
    """

    STATUS = [
        ("em_andamento", "Em andamento"),
        ("concluida", "Concluída"),
        ("atrasada", "Atrasada"),
    ]

    contrato = models.OneToOneField(Contrato, on_delete=models.CASCADE, related_name="entrega")
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="entregas")
    data_prevista = models.DateField()
    data_conclusao = models.DateField(null=True, blank=True, db_index=True)
    status = models.CharField(max_length=14, choices=STATUS, default="em_andamento")


class Receita(models.Model):
    """
    Grão: 1 linha por RECONHECIMENTO de receita.

    Esta é a única tabela que alimenta a Receita Reconhecida do Grupo (RRG).
    Volume estruturado e valor de contrato ficam em `Contrato` e são exibidos
    em separado como Volume Intermediado do Grupo (VIG) — nunca somados à RRG.
    """

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="receitas")
    contrato = models.ForeignKey(Contrato, on_delete=models.CASCADE, related_name="receitas")
    data_reconhecimento = models.DateField(db_index=True)
    valor = models.DecimalField(max_digits=14, decimal_places=2)
    natureza = models.CharField(max_length=14, choices=NaturezaReceita.choices)

    class Meta:
        indexes = [models.Index(fields=["empresa", "data_reconhecimento"])]


class InvestimentoMarketing(models.Model):
    """Grão: canal × campanha × dia. Denominador de CPL, CAC e ROAS."""

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="investimentos")
    canal = models.ForeignKey(Canal, on_delete=models.PROTECT, related_name="investimentos")
    campanha = models.ForeignKey(Campanha, on_delete=models.SET_NULL, null=True, related_name="investimentos")
    data = models.DateField(db_index=True)
    valor = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        indexes = [models.Index(fields=["empresa", "data"])]


class MetaPeriodo(models.Model):
    """Grão: empresa × período. Sem meta não há ritmo, e sem ritmo não há semáforo."""

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="metas")
    inicio = models.DateField()
    fim = models.DateField()
    valor = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        db_table = "core_meta_periodo"
        unique_together = [("empresa", "inicio", "fim")]
        verbose_name = "Meta do período"
        verbose_name_plural = "Metas do período"
