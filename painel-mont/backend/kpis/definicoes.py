"""
Catálogo de KPIs — entregável 15.4 do briefing, servido pela própria API.

O filtro aplicado a todo candidato a indicador:
  1. Muda alguma decisão?               3. Resiste ao gaming?
  2. Tem dono?                          4. É calculável com honestidade hoje?

Métricas reprovadas pelo filtro (total de leads, número de contratos, volume
estruturado, valor de contratos assinados) aparecem no painel como VOLUME, com
rótulo próprio, e nunca como resultado.
"""
from .registry import KpiDef, registrar

R = registrar

# ===========================================================================
# CAMADA DE GRUPO — comparáveis entre as três empresas.
# Só entram aqui grandezas NORMALIZADAS: percentuais, razões e tempos.
# Receita absoluta, ticket médio e volume ficam de fora de propósito.
# ===========================================================================
R(KpiDef(
    slug="rrg", nome="Receita Reconhecida do Grupo",
    finalidade="O único número de receita somável entre as três empresas.",
    formula="Σ Receita.valor no período, todas as naturezas",
    fonte="fato_receita",
    interpretacao="É o resultado de fato. Não confundir com volume intermediado.",
    dono="CFO", armadilha="Some naturezas diferentes (pontual e recorrente); ler junto do mix.",
    unidade="BRL", escopo="grupo"))

R(KpiDef(
    slug="vig", nome="Volume Intermediado do Grupo",
    finalidade="Medir a escala da operação — quanto valor passou pela mesa do grupo.",
    formula="Σ prêmio anualizado (MS) + Σ volume estruturado (P5) + Σ valor contratado (TB)",
    fonte="fato_contrato",
    interpretacao="NÃO é receita. Exibido em separado e jamais somado à RRG.",
    dono="CEO", armadilha="É o número que mais impressiona e o que mais engana: a distorção "
                          "frente à receita chega a 25× na Prop5.",
    unidade="BRL", escopo="grupo"))

R(KpiDef(
    slug="atingimento_ritmo", nome="Atingimento ajustado ao ritmo",
    finalidade="Saber se o resultado até hoje acompanha o ritmo necessário para a meta.",
    formula="realizado ÷ (meta × dias_úteis_decorridos ÷ dias_úteis_totais)",
    fonte="fato_receita × fato_meta × calendário de dias úteis",
    interpretacao="1,00 = exatamente no ritmo. Neutraliza tamanhos e sazonalidades diferentes.",
    dono="CEO", armadilha="Só olha o passado do mês; combinar com cobertura de pipeline.",
    unidade="X", sentido="maior_melhor", escopo="grupo", limiares=(0.95, 0.85)))

R(KpiDef(
    slug="forecast", nome="Projeção de fechamento",
    finalidade="Antecipar onde o período termina se nada mudar.",
    formula="w × (realizado ÷ fração_decorrida) + (1−w) × (realizado + pipeline_ponderado)",
    fonte="fato_receita × fato_oportunidade × fato_meta",
    interpretacao="Comparar com a meta. w é o peso do ritmo e varia por empresa.",
    dono="CEO", armadilha="Heurístico e sem intervalo de confiança — auditável, não estatístico.",
    unidade="BRL", escopo="grupo"))

R(KpiDef(
    slug="indice_esforco", nome="Índice de esforço",
    finalidade="Quantificar o quanto a operação precisa acelerar para bater a meta.",
    formula="necessidade_diária_restante ÷ média_diária_realizada",
    fonte="fato_receita × fato_meta",
    interpretacao="1,0 = manter o ritmo basta. Acima de 1,3 a meta exige mudança estrutural.",
    dono="Diretoria comercial", armadilha="Fica instável nos primeiros dias do período.",
    unidade="X", sentido="menor_melhor", escopo="grupo", limiares=(1.10, 1.30)))

R(KpiDef(
    slug="cobertura_pipeline", nome="Cobertura de pipeline",
    finalidade="Saber se existe funil suficiente para cobrir o que falta da meta.",
    formula="pipeline_ponderado ÷ gap_restante_da_meta",
    fonte="fato_oportunidade (aberta) × fato_meta",
    interpretacao="Referência de mercado: ≥ 3×. Abaixo de 1,5× o próximo período já nasce em risco.",
    dono="Diretoria comercial",
    armadilha="Depende da probabilidade por estágio estar calibrada com histórico real.",
    unidade="X", sentido="maior_melhor", escopo="grupo", limiares=(3.0, 1.5)))

R(KpiDef(
    slug="conv_s1_s6", nome="Conversão S1 → S6",
    finalidade="Medir eficiência comercial ponta a ponta, independente do volume.",
    formula="oportunidades que atingiram S6 ÷ leads da coorte",
    fonte="fato_evento_estagio × fato_lead",
    interpretacao="Comparável entre empresas porque é razão, não valor.",
    dono="Diretoria comercial",
    armadilha="Em ciclo longo, a coorte recente ainda não maturou — ler por safra.",
    unidade="PCT", sentido="maior_melhor", escopo="grupo"))

R(KpiDef(
    slug="taxa_realizacao", nome="Taxa de realização (S6 → S7)",
    finalidade="Medir quanto do que foi vendido virou entrega — e portanto receita.",
    formula="entregas concluídas ÷ contratos fechados no período",
    fonte="fato_entrega × fato_contrato",
    interpretacao="Vender e não realizar é o vazamento mais caro e mais invisível.",
    dono="Diretoria de operações",
    armadilha="Contratos recém-assinados ainda não tiveram tempo de entregar; usar janela defasada.",
    unidade="PCT", sentido="maior_melhor", escopo="grupo", limiares=(0.85, 0.70)))

R(KpiDef(
    slug="ciclo_medio", nome="Ciclo médio (S1 → S6)",
    finalidade="Saber quanto tempo o dinheiro leva para chegar.",
    formula="mediana(dias entre o evento S1 e o evento S6 da mesma oportunidade)",
    fonte="fato_evento_estagio",
    interpretacao="Mediana e não média: um negócio gigante de ciclo longo não distorce a leitura.",
    dono="Diretoria comercial",
    armadilha="Só enxerga quem fechou — quem está travado há meses não entra na conta.",
    unidade="DIAS", sentido="menor_melhor", escopo="grupo"))

R(KpiDef(
    slug="produtividade", nome="Produtividade comercial",
    finalidade="Medir eficiência da equipe, não o seu tamanho.",
    formula="receita reconhecida ÷ responsáveis ativos no período",
    fonte="fato_receita × dim_responsavel",
    interpretacao="Comparável entre empresas de portes diferentes.",
    dono="Diretoria comercial",
    armadilha="Penaliza times em formação; ler junto com tempo de casa.",
    unidade="BRL", escopo="grupo"))

R(KpiDef(
    slug="crescimento", nome="Crescimento vs. período anterior",
    finalidade="Enxergar trajetória, não só posição.",
    formula="(receita_atual − receita_anterior) ÷ receita_anterior",
    fonte="fato_receita",
    interpretacao="Comparável mesmo entre bases de tamanhos muito distintos.",
    dono="CEO", armadilha="Base pequena produz percentuais espetaculares e irrelevantes.",
    unidade="PCT", sentido="maior_melhor", escopo="grupo"))

# ===========================================================================
# MARKETING — ligar investimento a receita, não a volume.
# ===========================================================================
R(KpiDef(
    slug="investimento", nome="Investimento de marketing",
    finalidade="Base de todo cálculo de eficiência de aquisição.",
    formula="Σ InvestimentoMarketing.valor no período",
    fonte="fato_investimento_mkt", interpretacao="Volume de verba, não resultado.",
    dono="Head de Marketing", armadilha="Isolado, não diz nada.", unidade="BRL", escopo="marketing"))

R(KpiDef(
    slug="cpl", nome="CPL — custo por lead",
    finalidade="Custo de topo de funil por canal.",
    formula="investimento ÷ leads gerados",
    fonte="fato_investimento_mkt × fato_lead",
    interpretacao="Quanto menor melhor, mas sozinho premia lead barato e inútil.",
    dono="Head de Marketing", armadilha="Métrica de vaidade se não vier acompanhada do CPL qualificado.",
    unidade="BRL", sentido="menor_melhor", escopo="marketing"))

R(KpiDef(
    slug="cpl_qualificado", nome="CPL qualificado",
    finalidade="Custo de um lead que efetivamente entra em descoberta (S4).",
    formula="investimento ÷ leads que atingiram S4",
    fonte="fato_investimento_mkt × fato_evento_estagio",
    interpretacao="Resiste ao gaming muito melhor que o CPL simples.",
    dono="Head de Marketing", armadilha="Em ciclo longo, a coorte recente ainda não chegou a S4.",
    unidade="BRL", sentido="menor_melhor", escopo="marketing"))

R(KpiDef(
    slug="aproveitamento", nome="Taxa de aproveitamento",
    finalidade="Medir a qualidade da fonte, não o seu volume.",
    formula="leads que atingiram S4 ÷ leads totais",
    fonte="fato_lead × fato_evento_estagio",
    interpretacao="É o indicador que separa canal que traz gente da que traz cliente.",
    dono="Head de Marketing", armadilha="Sensível a mudança de critério de qualificação.",
    unidade="PCT", sentido="maior_melhor", escopo="marketing"))

R(KpiDef(
    slug="cac", nome="CAC — custo de aquisição de cliente",
    finalidade="Entender quanto custa conquistar um cliente novo, por canal e por empresa.",
    formula="investimento de aquisição ÷ novos clientes",
    fonte="fato_investimento_mkt × fato_contrato (via id_lead)",
    interpretacao="Quanto menor, melhor — desde que receita e retenção não caiam junto.",
    dono="Head de Marketing, por canal",
    armadilha="Isolado, incentiva cortar canais caros que trazem o melhor LTV. "
              "Ler sempre ao lado de payback e LTV/CAC.",
    unidade="BRL", sentido="menor_melhor", escopo="marketing"))

R(KpiDef(
    slug="roas", nome="ROAS de receita reconhecida",
    finalidade="Saber o retorno real da verba, e não o retorno de volume.",
    formula="receita reconhecida atribuída ÷ investimento",
    fonte="fato_receita × fato_investimento_mkt (via id_lead)",
    interpretacao="Abaixo de 1 o canal destrói valor no horizonte medido.",
    dono="Head de Marketing",
    armadilha="Dividir receita do mês pelo investimento do mês é errado em ciclo longo — "
              "aqui a atribuição é por coorte de entrada do lead.",
    unidade="X", sentido="maior_melhor", escopo="marketing", limiares=(3.0, 1.0)))

R(KpiDef(
    slug="roas_coorte", nome="ROAS por coorte (30/60/90 dias)",
    finalidade="Comparar canais respeitando o tempo que cada negócio leva para converter.",
    formula="receita gerada pelos leads da coorte até D dias ÷ investimento do mês da coorte",
    fonte="fato_lead × fato_receita × fato_investimento_mkt",
    interpretacao="A coorte amadurece: julgar um canal de ciclo longo aos 30 dias é injusto.",
    dono="Head de Marketing", armadilha="Coorte do mês corrente sempre parece ruim — é imaturidade, não ineficiência.",
    unidade="X", sentido="maior_melhor", escopo="marketing"))

R(KpiDef(
    slug="participacao_verba", nome="Participação na verba",
    finalidade="Ver concentração de investimento por canal.",
    formula="investimento do canal ÷ investimento total da empresa",
    fonte="fato_investimento_mkt",
    interpretacao="Canal com fatia alta e ROAS baixo é a maior oportunidade de realocação.",
    dono="Head de Marketing", armadilha="Fatia alta não é problema se o retorno acompanhar.",
    unidade="PCT", sentido="neutro", escopo="marketing"))

R(KpiDef(
    slug="defasagem_receita", nome="Defasagem lead → receita",
    finalidade="Calibrar a leitura de todos os indicadores de marketing.",
    formula="mediana(dias entre a entrada do lead e o primeiro reconhecimento de receita)",
    fonte="fato_lead × fato_receita",
    interpretacao="Define a janela mínima honesta para avaliar um canal.",
    dono="Head de Marketing", armadilha="Ignorá-la faz um mês de corte de verba parecer o mais eficiente da história.",
    unidade="DIAS", sentido="menor_melhor", escopo="marketing"))

# ===========================================================================
# MONTSEGURO — unidade de valor: a VIDA, não o contrato.
# ===========================================================================
_MS = "montseguro"
R(KpiDef(slug="ms_vidas_implantadas", nome="Vidas implantadas", escopo=_MS, unidade="UN",
         finalidade="A unidade real do negócio — substitui 'número de contratos'.",
         formula="Σ num_vidas de contratos com implantação concluída no período",
         fonte="fato_contrato × fato_entrega",
         interpretacao="Um contrato de 3 vidas e um de 180 deixam de contar igual.",
         dono="Diretoria comercial Montseguro",
         armadilha="Vidas implantadas ≠ vidas contratadas; a diferença é o gap de realização."))
R(KpiDef(slug="ms_ape", nome="Prêmio anualizado (APE)", escopo=_MS, unidade="BRL",
         finalidade="Dimensionar economicamente o que foi vendido, comparável entre meses.",
         formula="Σ (prêmio mensal × 12) dos contratos do período",
         fonte="fato_contrato", interpretacao="É base de comissão, não é receita da corretora.",
         dono="Diretoria comercial Montseguro",
         armadilha="Confundir APE com receita infla o resultado em ~20×."))
R(KpiDef(slug="ms_ticket_vida", nome="Ticket por vida", escopo=_MS, unidade="BRL",
         finalidade="Ler o mix de carteira.",
         formula="prêmio mensal total ÷ vidas", fonte="fato_contrato",
         interpretacao="Sobe = mix mais nobre. Cai = pulverização em MEI.",
         dono="Diretoria comercial Montseguro", armadilha="Média esconde bimodalidade MEI × médias empresas."))
R(KpiDef(slug="ms_agenciamento", nome="Receita de agenciamento", escopo=_MS, unidade="BRL",
         finalidade="Separar a receita que depende de vender de novo todo mês.",
         formula="Σ Receita.valor com natureza = agenciamento",
         fonte="fato_receita", interpretacao="É a parte volátil do resultado.",
         dono="CFO", armadilha="Estornada se o contrato cair em até 90 dias."))
R(KpiDef(slug="ms_recorrente", nome="Receita recorrente de carteira", escopo=_MS, unidade="BRL",
         finalidade="Medir a base estável que cresce sem CAC novo.",
         formula="Σ Receita.valor com natureza = corretagem",
         fonte="fato_receita", interpretacao="É a anuidade do negócio — o ativo real da corretora.",
         dono="CFO", armadilha="Cai silenciosamente com o churn de apólices; ler junto de retenção."))
R(KpiDef(slug="ms_conv_cotacao_proposta", nome="Cotação → proposta", escopo=_MS, unidade="PCT",
         finalidade="Medir aderência da simulação ao que o cliente precisa.",
         formula="oportunidades que atingiram S5 ÷ que atingiram S4",
         fonte="fato_evento_estagio", interpretacao="Queda aqui é problema de oferta, não de demanda.",
         dono="Coordenação comercial", armadilha="Sensível a mudança de tabela das operadoras.",
         limiares=(0.30, 0.22)))
R(KpiDef(slug="ms_conv_proposta_contrato", nome="Proposta → contratação", escopo=_MS, unidade="PCT",
         finalidade="Medir poder de fechamento do time.",
         formula="oportunidades que atingiram S6 ÷ que atingiram S5",
         fonte="fato_evento_estagio", interpretacao="Queda aqui é problema de negociação ou de preço.",
         dono="Coordenação comercial", armadilha="Melhora artificialmente se o time só propõe para quem já ia fechar.",
         limiares=(0.45, 0.33)))
R(KpiDef(slug="ms_prazo_implantacao", nome="Prazo médio de implantação", escopo=_MS, unidade="DIAS",
         sentido="menor_melhor", finalidade="Cada dia a mais atrasa a comissão e aumenta desistência.",
         formula="mediana(dias entre contratação e início de vigência)",
         fonte="fato_contrato × fato_entrega", interpretacao="É um KPI financeiro disfarçado de operacional.",
         dono="Operações Montseguro", armadilha="Média esconde a cauda longa dos casos problemáticos.",
         limiares=(18, 28)))
R(KpiDef(slug="ms_queda_90d", nome="Queda em até 90 dias", escopo=_MS, unidade="PCT",
         sentido="menor_melhor", finalidade="Medir a QUALIDADE da venda, não o volume.",
         formula="contratos cancelados em ≤ 90 dias ÷ contratos do período",
         fonte="fato_contrato (data_cancelamento)",
         interpretacao="Alta = comissão estornada e venda mal feita. É o que separa vender bem de vender muito.",
         dono="Coordenação comercial", armadilha="Só aparece 90 dias depois — usar coorte, não mês corrente.",
         limiares=(0.06, 0.10)))
R(KpiDef(slug="ms_concentracao_operadora", nome="Concentração por operadora", escopo=_MS, unidade="PCT",
         sentido="menor_melhor", finalidade="Expor dependência comercial de uma única operadora.",
         formula="max(participação de uma operadora na receita do período)",
         fonte="fato_contrato × dim_operadora",
         interpretacao="Acima de 40% a corretora perde poder de negociação.",
         dono="CEO", armadilha="Concentração pode ser estratégica; o alerta é para revisão, não para correção automática.",
         limiares=(0.35, 0.45)))
R(KpiDef(slug="ms_retencao", nome="Retenção de carteira", escopo=_MS, unidade="PCT",
         finalidade="Medir o ativo que sustenta a receita recorrente.",
         formula="contratos vigentes no fim ÷ (vigentes no início + novos)",
         fonte="fato_contrato", interpretacao="É mais barato reter uma apólice que vender outra.",
         dono="Pós-venda", armadilha="Retenção alta com carteira encolhendo em vidas é falso conforto.",
         limiares=(0.92, 0.85)))

# ===========================================================================
# PROP5 — ciclo longo e consultivo. Volume ≠ receita.
# ===========================================================================
_P5 = "prop5"
R(KpiDef(slug="p5_volume_estruturado", nome="Volume estruturado", escopo=_P5, unidade="BRL",
         finalidade="Medir a escala da operação patrimonial.",
         formula="Σ volume_estruturado dos contratos do período", fonte="fato_contrato",
         interpretacao="EXIBIDO, nunca somado como receita. Compõe o VIG, não o RRG.",
         dono="CEO Prop5", armadilha="É o número mais impressionante do grupo e o mais enganoso."))
R(KpiDef(slug="p5_take_rate", nome="Take rate", escopo=_P5, unidade="PCT",
         finalidade="Quanto do que passa pela mesa vira dinheiro da Prop5.",
         formula="receita de comissão ÷ volume estruturado", fonte="fato_receita × fato_contrato",
         interpretacao="É a ponte entre as duas grandezas — e o que impede a confusão entre elas.",
         dono="CFO", armadilha="Varia por produto; a média esconde mix."))
R(KpiDef(slug="p5_comissao", nome="Receita de comissão", escopo=_P5, unidade="BRL",
         finalidade="O número que entra no consolidado do Grupo.",
         formula="Σ Receita.valor com natureza = comissao", fonte="fato_receita",
         interpretacao="Reconhecida na estruturação, não na assinatura.",
         dono="CFO", armadilha="Parcelada: o mês de assinatura e o de caixa não coincidem."))
R(KpiDef(slug="p5_lead_diagnostico", nome="Lead → diagnóstico financeiro", escopo=_P5, unidade="PCT",
         finalidade="Medir o portão real de qualificação do negócio.",
         formula="oportunidades que atingiram S4 ÷ leads", fonte="fato_evento_estagio × fato_lead",
         interpretacao="Antes do diagnóstico é interesse; depois dele é oportunidade.",
         dono="Head de Marketing e Comercial",
         armadilha="É o melhor termômetro da qualidade do marketing nesta empresa.",
         limiares=(0.28, 0.18)))
R(KpiDef(slug="p5_diagnostico_reuniao", nome="Diagnóstico → reunião consultiva", escopo=_P5, unidade="PCT",
         finalidade="Medir aderência da estratégia proposta ao perfil do cliente.",
         formula="oportunidades que atingiram S5 ÷ que atingiram S4", fonte="fato_evento_estagio",
         interpretacao="Queda aqui indica diagnóstico raso ou perfil errado na entrada.",
         dono="Consultoria Prop5", armadilha="Pode melhorar por seleção, não por qualidade."))
R(KpiDef(slug="p5_pipeline_ponderado", nome="Pipeline ponderado", escopo=_P5, unidade="BRL",
         finalidade="Previsão realista em vez da soma otimista do funil.",
         formula="Σ (valor da oportunidade × probabilidade do estágio)", fonte="fato_oportunidade",
         interpretacao="Deve ser lido junto do aging: pipeline parado não é pipeline.",
         dono="Diretoria comercial", armadilha="Probabilidade fixa é chute; calibrar com histórico real."))
R(KpiDef(slug="p5_aging", nome="Aging do pipeline", escopo=_P5, unidade="PCT", sentido="menor_melhor",
         finalidade="Distinguir ciclo longo saudável de pipeline morto.",
         formula="% de oportunidades abertas sem interação há mais de meio ciclo médio",
         fonte="fato_oportunidade", interpretacao="É a métrica que impede confundir paciência com abandono.",
         dono="Diretoria comercial", armadilha="Depende de o time registrar interação — campo frequentemente vazio.",
         limiares=(0.20, 0.35)))
R(KpiDef(slug="p5_ciclo", nome="Ciclo médio lead → fechamento", escopo=_P5, unidade="DIAS",
         sentido="menor_melhor", finalidade="Base do forecast desta empresa.",
         formula="mediana(dias entre S1 e S6)", fonte="fato_evento_estagio",
         interpretacao="Espera-se que seja longo — é decisão patrimonial, não compra por impulso.",
         dono="Diretoria comercial", armadilha="Comparar com o ciclo da Montseguro não faz sentido.",
         limiares=(85, 110)))
R(KpiDef(slug="p5_cac_pais", nome="CAC por país de residência", escopo=_P5, unidade="BRL",
         sentido="menor_melhor", finalidade="Descobrir onde o expatriado converte melhor e mais barato.",
         formula="investimento atribuído ao país ÷ clientes adquiridos no país",
         fonte="fato_investimento_mkt × dim_cliente(pais_residencia)",
         interpretacao="Dimensão de primeira classe nesta empresa — não é recorte secundário.",
         dono="Head de Marketing", armadilha="A verba raramente é segmentada por país; hoje é rateio declarado."))
R(KpiDef(slug="p5_operacoes_cliente", nome="Operações por cliente", escopo=_P5, unidade="X",
         finalidade="A prova de que o Método M5 está funcionando.",
         formula="contratos ÷ clientes únicos", fonte="fato_contrato × dim_cliente",
         interpretacao="As etapas 4 e 5 do M5 (renda e reinvestir) só existem se o cliente voltar.",
         dono="CEO Prop5", armadilha="Cresce devagar por natureza; medir em janela anual, não mensal.",
         limiares=(1.25, 1.10)))
R(KpiDef(slug="p5_reinvestimento", nome="% receita de reinvestimento", escopo=_P5, unidade="PCT",
         finalidade="Medir expansão com CAC próximo de zero.",
         formula="receita de clientes com contrato anterior ÷ receita total", fonte="fato_receita × fato_contrato",
         interpretacao="É a receita mais lucrativa da empresa.",
         dono="CEO Prop5", armadilha="Base jovem produz percentual baixo sem que haja problema."))

# ===========================================================================
# TECHBRABO — onde o comercial encosta na capacidade de entrega.
# ===========================================================================
_TB = "techbrabo"
R(KpiDef(slug="tb_mrr", nome="MRR", escopo=_TB, unidade="BRL",
         finalidade="Medir a base previsível de receita.",
         formula="Σ mensalidades ativas no mês", fonte="fato_receita (natureza = recorrente)",
         interpretacao="É o que sobe o valor da empresa, não o faturamento do mês.",
         dono="CEO TechBrabo", armadilha="Confundir MRR com receita total mascara dependência de projeto."))
R(KpiDef(slug="tb_mix_recorrente", nome="Mix pontual × recorrente", escopo=_TB, unidade="PCT",
         finalidade="Saber se o negócio está amadurecendo ou apenas girando.",
         formula="receita recorrente ÷ receita total", fonte="fato_receita",
         interpretacao="Recorrente crescendo = menos dependência de vender de novo todo mês.",
         dono="CEO TechBrabo", armadilha="Pode subir porque a receita de projeto caiu — ler os dois em valor absoluto.",
         limiares=(0.35, 0.20)))
R(KpiDef(slug="tb_backlog", nome="Backlog contratado", escopo=_TB, unidade="BRL",
         finalidade="Ver receita já vendida esperando entrega.",
         formula="Σ valor contratado − Σ receita reconhecida", fonte="fato_contrato × fato_receita",
         interpretacao="Backlog crescendo com entrega estável é risco de capacidade, não boa notícia.",
         dono="Diretoria de operações", armadilha="Backlog alto parece saúde comercial e pode ser gargalo operacional."))
R(KpiDef(slug="tb_margem_projeto", nome="Margem por projeto", escopo=_TB, unidade="PCT",
         finalidade="Distinguir vender caro de ganhar dinheiro.",
         formula="(receita − custo de horas) ÷ receita", fonte="fato_contrato (custo_horas)",
         interpretacao="É o único KPI do grupo que enxerga custo — as outras duas empresas não têm o dado.",
         dono="CEO TechBrabo", armadilha="Depende de apontamento de horas confiável.",
         limiares=(0.40, 0.25)))
R(KpiDef(slug="tb_ocupacao", nome="Ocupação da equipe", escopo=_TB, unidade="PCT", sentido="neutro",
         finalidade="Saber qual é o teto do comercial.",
         formula="horas alocadas em projetos ativos ÷ horas disponíveis",
         fonte="fato_contrato (horas_estimadas) × capacidade da equipe",
         interpretacao="Acima de 90% = risco de atraso, queda de margem e queima do time.",
         dono="Diretoria de operações",
         armadilha="Ocupação baixa não é folga: é capacidade ociosa sendo paga."))
R(KpiDef(slug="tb_projetos_risco", nome="Projetos em risco", escopo=_TB, unidade="UN",
         sentido="menor_melhor", finalidade="Semáforo de entrega ligado a renovação e reputação.",
         formula="contagem de entregas com status atrasada", fonte="fato_entrega",
         interpretacao="Atraso hoje é churn daqui a dois trimestres.",
         dono="Diretoria de operações", armadilha="Depende de prazo previsto realista no contrato.",
         limiares=(2, 5)))
R(KpiDef(slug="tb_lead_time", nome="Lead time contrato → go-live", escopo=_TB, unidade="DIAS",
         sentido="menor_melhor", finalidade="Velocidade de transformar contrato em receita.",
         formula="mediana(dias entre assinatura e conclusão da entrega)",
         fonte="fato_contrato × fato_entrega", interpretacao="É o que separa backlog de faturamento.",
         dono="Diretoria de operações", armadilha="Projetos grandes distorcem a média — usar mediana.",
         limiares=(40, 60)))
R(KpiDef(slug="tb_ticket", nome="Ticket médio de projeto", escopo=_TB, unidade="BRL",
         finalidade="Ler o posicionamento: fábrica de horas ou parceiro estratégico.",
         formula="valor contratado ÷ número de contratos", fonte="fato_contrato",
         interpretacao="Subir o ticket costuma valer mais que subir o volume.",
         dono="CEO TechBrabo", armadilha="Média sobe com um único contrato atípico."))
R(KpiDef(slug="tb_intercompany", nome="% receita intercompany", escopo=_TB, unidade="PCT",
         sentido="menor_melhor", finalidade="Expor risco de concentração dentro do próprio grupo.",
         formula="receita de clientes do grupo ÷ receita total",
         fonte="fato_receita × dim_cliente(origem_cliente)",
         interpretacao="Alta = a empresa ainda não foi testada pelo mercado. Leitura de holding.",
         dono="CEO do Grupo", armadilha="Pode ser estratégia deliberada de incubação — o alerta é para decidir, não para corrigir.",
         limiares=(0.40, 0.60)))
R(KpiDef(slug="tb_churn", nome="Churn de contratos recorrentes", escopo=_TB, unidade="PCT",
         sentido="menor_melhor", finalidade="Medir saúde da base recorrente.",
         formula="MRR cancelado ÷ MRR do início do período", fonte="fato_contrato × fato_receita",
         interpretacao="Reter é mais barato que vender.",
         dono="CEO TechBrabo", armadilha="Base pequena torna o percentual muito volátil.",
         limiares=(0.02, 0.05)))
R(KpiDef(slug="tb_nrr", nome="NRR — retenção líquida de receita", escopo=_TB, unidade="PCT",
         finalidade="Saber se a empresa cresce sem precisar vender para clientes novos.",
         formula="(MRR base + expansão − churn) ÷ MRR base", fonte="fato_receita (natureza = recorrente)",
         interpretacao="Acima de 100% a base cresce sozinha.",
         dono="CEO TechBrabo", armadilha="Exige histórico de pelo menos 12 meses para significar algo.",
         limiares=(1.05, 0.95)))
