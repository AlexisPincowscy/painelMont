# Mont Executive Dashboard

An executive analytics dashboard built for a technical challenge. The FastAPI service exposes a typed KPI catalog, Django ORM manages the dimensional model, and the React dashboard presents metrics across three business units. The local setup uses SQLite and demo data, with PostgreSQL supported through configuration.

The original documentation below includes the setup and implementation details.

---

# Painel Executivo · Grupo Mont

Dashboard executivo consolidando **Montseguro**, **Prop5 Investimentos** e **TechBrabo**,
desenvolvido para o Desafio Técnico do Grupo Mont.

> **A tese em uma frase:** o problema não é falta de números, é falta de hierarquia.
> Três modelos de receita diferentes precisam virar uma leitura comparável **sem** virar
> uma média sem sentido.

---

## 1. Como executar

Pré-requisitos: **Python 3.11+** e **Node 18+**. O banco padrão é SQLite — não é
necessário subir infraestrutura para rodar.

```bash
# 1) Backend
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo --reset                    # carga de dados DEMONSTRATIVOS
python -m uvicorn api.main:app --reload --port 8000

# 2) Frontend (em outro terminal)
cd frontend
npm install
npm run dev
```

| Endereço | O que é |
|---|---|
| http://localhost:5173 | O painel |
| http://127.0.0.1:8000/docs | OpenAPI da API analítica (gerado pelo FastAPI) |
| http://127.0.0.1:8000/api/kpis | Catálogo de KPIs — o entregável 15.4 servido como dado |
| http://localhost:5173/#/saude-dados | Saúde dos Dados — adição própria à estrutura mínima |
| http://127.0.0.1:8000/admin | Admin do Django, para conferir a carga |

Testes: `cd backend && python -m pytest` · Tipos do front: `cd frontend && npm run typecheck`

Para usar PostgreSQL em vez de SQLite, basta exportar `DATABASE_URL=postgres://...`.
Nenhuma linha de código muda — o modelo dimensional foi escrito para os dois.

---

## 2. Tecnologias e por quê

| Camada | Escolha | Justificativa |
|---|---|---|
| Modelo de dados | **Django ORM** + migrations + admin | Integridade referencial, evolução versionada do schema e uma ferramenta pronta para conferir a carga |
| API analítica | **FastAPI** + Pydantic | Contratos tipados, OpenAPI automática e respostas rápidas para leitura |
| Camada semântica | Módulo Python próprio (`kpis/`) | O coração da solução: um único lugar define cada indicador |
| Banco | **SQLite** (padrão) / **PostgreSQL** | Star schema não exige banco analítico neste volume; materialização resolve performance |
| Front-end | **React 18 + TypeScript + Vite** | Stack do time; tipos compartilhados com os contratos da API |
| Gráficos | **Recharts** com wrappers próprios | Componentes encapsulam as regras de cor e de contexto |

**Por que Django e FastAPI juntos, e não um só.** Cada um no que é bom: o Django resolve
modelagem, migrations, carga e verificação; o FastAPI resolve a API de leitura que o front
consome. Eles compartilham o **mesmo ORM** — `api/main.py` chama `django.setup()` e usa os
models do Django diretamente. Não há duplicação de modelo nem uma segunda verdade sobre os
dados.

---

## 3. Arquitetura

```
                     ┌───────────────────────────────────────────┐
  Fontes  ──────────▶│  Django  ·  modelo dimensional (core/)     │
  (CSV/API/planilha) │  raw → staging → marts, migrations, admin  │
                     └──────────────────┬────────────────────────┘
                                        │  ORM compartilhado
                     ┌──────────────────▼────────────────────────┐
                     │  CAMADA SEMÂNTICA (kpis/)                 │
                     │  registry · consultas · grupo · comercial  │
                     │  marketing · empresa · alertas · periodo   │
                     │  ── único lugar que define um indicador ── │
                     └──────────────────┬────────────────────────┘
                     ┌──────────────────▼────────────────────────┐
                     │  FastAPI (api/)  ·  contratos Pydantic     │
                     └──────────────────┬────────────────────────┘
                     ┌──────────────────▼────────────────────────┐
                     │  React + TS  ·  6 telas, filtros na URL    │
                     └───────────────────────────────────────────┘
```

**A decisão que mais importa:** nenhum componente de tela calcula KPI. Um gráfico *pede* um
indicador e recebe pronto — valor, unidade, comparação com o período anterior, posição
contra a meta, tendência de 12 meses, status de semáforo e a ficha de documentação. É isso
que garante que "CAC" na tela do CEO e "CAC" na tela de Marketing sejam sempre o mesmo
número.

**Teste da quarta empresa.** Adicionar uma empresa ao grupo deve custar: linhas em
`dim_empresa` e `dim_estagio_canonico`, um mapeamento de origem de dados e um conjunto de
KPIs próprios. **Zero alteração nas telas de grupo.**

---

## 4. Estrutura dos dados

Modelo em estrela com **granularidade de evento, não de estado**. Guardar apenas "a
oportunidade está em Proposta" responde *onde ela está*; guardar "entrou em Proposta em
12/08 às 14h" responde *quanto tempo levou* e *onde vaza*. Sem evento datado não existe
análise de ciclo nem de gargalo — só fotografia.

### Fatos

| Tabela | Grão | Por que existe |
|---|---|---|
| `Lead` | 1 lead | Origem, canal, campanha e data de entrada |
| `EventoEstagio` | 1 mudança de estágio | **Ciclo, conversão real e gargalo** |
| `Oportunidade` | 1 oportunidade | Valor, estágio atual, dono, última interação |
| `Contrato` | 1 contrato fechado | Fechamento, valor e as dimensões próprias de cada empresa |
| `Entrega` | 1 implantação / go-live | A ponte S6 → S7, onde o dinheiro realmente acontece |
| `Receita` | 1 reconhecimento | **Separa pontual, recorrente e comissão** |
| `InvestimentoMarketing` | canal × campanha × dia | Denominador de CPL, CAC e ROAS |
| `MetaPeriodo` | empresa × período | Sem meta não há ritmo, e sem ritmo não há semáforo |

### Dimensões

**Conformadas** (compartilhadas — é o que torna a comparação possível): tempo, empresa,
canal, campanha, origem, responsável, equipe, cliente, produto, estágio canônico, status.

**Próprias** (é o que impede o achatamento):

- Montseguro — `operadora`, `num_vidas`, `premio_mensal`, `porte_cnpj`
- Prop5 — `volume_estruturado`, `take_rate`, `pais_residencia`
- TechBrabo — `mrr`, `horas_estimadas`, `custo_horas`, `origem_cliente`

### A tabela de tradução

`EstagioCanonico` mapeia o funil real de cada empresa para oito estágios canônicos. Cada
empresa mantém o nome do seu estágio na visão individual; o painel de grupo lê tudo por
S1..S8.

| Canônico | Montseguro | Prop5 | TechBrabo |
|---|---|---|---|
| S1 Entrada | Lead | Lead | Lead |
| S2 Contato | Atendimento | Contato | Contato |
| S3 Qualificação | Qualificação | Qualificação | Qualificação |
| S4 Descoberta | **Cotação** | **Diagnóstico financeiro** | **Reunião + diagnóstico** |
| S5 Solução formal | Proposta | Estratégia / oportunidade | Proposta |
| S6 Fechamento | Contratação | Aquisição | Contrato assinado |
| S7 Realização | Implantação concluída | Estruturação concluída | Entrega / go-live |
| S8 Continuidade | Carteira ativa | Acompanhamento | Sustentação / MRR |

---

## 5. Principais decisões técnicas e de negócio

### 5.1 RRG e VIG: as duas grandezas que nunca se somam

O erro mais caro que este painel existe para evitar. Cada empresa tem um momento diferente
em que o dinheiro vira receita:

| | O que parece receita | O que é receita |
|---|---|---|
| Montseguro | Prêmio contratado | Comissão sobre o prêmio, a partir da vigência |
| Prop5 | Volume financeiro estruturado | Comissão sobre a operação fechada |
| TechBrabo | Valor total do contrato | Marco entregue + mensalidade do mês |

Por isso o painel opera com duas grandezas separadas:

- **RRG — Receita Reconhecida do Grupo**: comparável, somável, é o número do CEO.
- **VIG — Volume Intermediado do Grupo**: mede escala de operação, exibido em separado,
  **nunca somado à RRG**.

Na carga demonstrativa a razão VIG/RRG da Prop5 fica acima de 20×. Há um teste automatizado
que falha se esses dois números se aproximarem — porque isso significaria que alguém somou
o que não devia.

### 5.2 Meta não é percentual, é ritmo

"62% da meta" no dia 20 pode ser excelente ou catastrófico. O painel calcula, em **dias
úteis**:

```
meta_esperada_hoje  = meta × (dias_úteis_decorridos ÷ dias_úteis_totais)
gap                 = realizado − meta_esperada_hoje
forecast            = w × (realizado ÷ fração_decorrida)
                    + (1−w) × (realizado + pipeline_ponderado × fração_restante)
necessidade_diária  = (meta − realizado) ÷ dias_úteis_restantes
índice_de_esforço   = necessidade_diária ÷ média_diária_realizada
cobertura_pipeline  = pipeline_ponderado ÷ gap_restante
```

O peso `w` varia por empresa (**0,65** Montseguro · **0,30** Prop5 · **0,40** TechBrabo):
negócio transacional com muitos fechamentos por mês tem ritmo estatisticamente confiável;
negócio de ciclo longo e poucos fechamentos grandes tem ritmo ruidoso, e ali o funil prevê
melhor. É hipótese declarada e recalibrável, não constante mágica.

**Conversão de unidade do pipeline.** O valor da oportunidade está na unidade do *contrato*
de cada empresa (prêmio anualizado, volume estruturado, valor do projeto) e a meta está em
*receita reconhecida*. `fator_receita()` converte um no outro usando o histórico real da
própria empresa. Sem isso, comparar pipeline com meta cometeria exatamente o erro que o
painel existe para evitar.

### 5.3 Semáforo com regra, não com sensação

| Status | Regra combinada |
|---|---|
| 🟢 Verde | atingimento ≥ 0,95 **e** esforço ≤ 1,10 **e** cobertura ≥ 3,0 |
| 🟡 Amarelo | atingimento 0,85–0,95 **ou** esforço 1,10–1,30 **ou** cobertura 1,5–3,0 |
| 🔴 Vermelho | atingimento < 0,85 **ou** esforço > 1,30 **ou** cobertura < 1,5 |
| ⚪ Cinza | meta ausente ou dado insuficiente |

Três condições de propósito: uma empresa pode estar em 98% da meta e ainda assim ser
vermelha se a cobertura de pipeline caiu para 0,8× — o mês fecha bem e o próximo não.
Semáforo só de atingimento é retrovisor; combinado com cobertura, vira para-brisa.

Ressalva implementada: quando o gap restante é menor que 10% da meta, a cobertura fica
numericamente instável e passa a ser **informativa**, não decisória — senão o painel
pintaria de vermelho justamente quem está prestes a bater a meta.

### 5.4 Atribuição por coorte de entrada do lead

Dividir a receita de agosto pelo investimento de agosto é o erro de atribuição mais caro do
desafio: com o ciclo consultivo da Prop5, a receita de agosto veio de leads de maio. Um mês
de corte de verba apareceria como o mês mais eficiente da história — e levaria a cortar
mais.

A tela de Marketing mostra **dois ROAS**, de propósito:

- `roas_caixa` — receita reconhecida no mês ÷ investimento do mês. É o que a maioria dos
  painéis chama de ROAS. Infla, porque mistura receita recorrente de safras antigas com
  verba nova.
- `roas` (**de coorte**) — receita gerada pelos leads que **entraram** no período, medida
  até 90 dias depois. É a métrica de decisão.

Coorte do mês corrente aparece marcada como **imatura**: o número é baixo por falta de
tempo, não por ineficiência, e o painel diz isso em vez de deixar induzir a decisão errada.

Pelo mesmo motivo, CPL, CPL qualificado, aproveitamento e **CAC** são todos medidos na
mesma população — a coorte de entrada. Calcular o CAC por data de assinatura misturaria o
numerador de agosto com um denominador de maio.

### 5.5 Probabilidades calibradas, não arbitradas

O pipeline ponderado usa a taxa de conversão **observada** de cada estágio até o fechamento,
recalculada a cada leitura sobre o histórico de cada empresa. Valores fixos de partida
(S1 2% · S2 5% · S3 10% · S4 20% · S5 45%) só permanecem enquanto a amostra do estágio for
menor que 30. Chutar é aceitável no dia 1; continuar chutando com dado na mesa não é.

### 5.6 Motor de alertas

Nove regras rodam a cada atualização. A tela do CEO mostra **no máximo cinco**, ordenadas
por `impacto_em_R$ × urgência × confiança` — a confiança cai quando a amostra é pequena, o
que impede que uma queda de 50% em quatro leads apareça acima de um problema de R$ 200 mil.

| | Regra | Disparo |
|---|---|---|
| R1 | Meta em risco | forecast < 0,90 × meta |
| R2 | Gargalo de funil | conversão da etapa < 0,80 × média histórica, com n ≥ 30 |
| R3 | CAC deteriorando | CAC 30d > 1,25 × CAC 90d |
| R4 | Canal queimando verba | fatia da verba > 15% **e** ROAS de coorte madura < 1 |
| R5 | Pipeline estagnado | sem interação há mais de meio ciclo médio |
| R6 | Gap de realização | fila de entrega cresce 3 períodos **e** ≥ 40% |
| R7 | Concentração | uma operadora / cliente / canal > 40% da receita |
| R8 | Capacidade no limite | ocupação > 90% (TechBrabo) |
| R9 | Oportunidade positiva | aproveitamento do canal ↑ > 15% sem encarecer o CAC |

Todo alerta responde cinco perguntas — o que houve, por que importa, **quanto custa**, o
que fazer e quem faz — e leva, clicável, à tela que o prova. Nenhum alerta afirma a
**causa**: ele aponta onde olhar e propõe uma hipótese de investigação.

### 5.7 A sexta tela: Saúde dos Dados

Adição própria à estrutura mínima da seção 4, e a única tela voltada para a **gestão**, não para
a leitura executiva — por isso fica fora do menu do CEO.

A seção 13 do briefing trata dado faltante como achado. Um achado que fica num slide não muda
nada: precisa virar acompanhamento. Esta tela mede a completude dos campos críticos por empresa,
nomeia **quais KPIs ficam impossíveis** quando cada campo não é registrado, e mostra a disciplina
de registro por responsável.

Três decisões dentro dela:

- **Janela móvel de 180 dias, não o mês.** Completude é métrica de higiene, não de período: medir
  no mês daria n=3 para a TechBrabo, e uma taxa sobre três casos é ruído.
- **Amostra abaixo de 20 registros não pinta semáforo.** O número aparece, mas em cinza — um
  percentual sobre cinco casos não merece a autoridade de uma cor.
- **Campo inexistente ≠ campo vazio.** `data_cancelamento` só existe na Montseguro; nas outras a
  tela reporta "campo inexistente" em vez de uma taxa. É exatamente por isso que `tb_churn` aparece
  indisponível na tela da TechBrabo — e a lista de KPIs bloqueados sai da própria camada semântica,
  não é mantida à mão.

### 5.8 Estado de filtro na URL

`/comercial?periodo=2026-08&empresa=montseguro`. Resolve três problemas de uma vez:
coerência entre telas, link compartilhável do problema exato e o botão voltar do navegador
funcionando como qualquer pessoa espera.

---

## 6. Documentação dos KPIs

Cada indicador é declarado com **nome, finalidade, fórmula, fonte e interpretação**
(entregável 15.4), mais três campos que evitam discussão futura: **dono**, **limiares do
semáforo** e **armadilha conhecida**.

A ficha vive no mesmo arquivo que define o cálculo (`kpis/definicoes.py`), é servida em
`GET /api/kpis` e aparece no tooltip “?” de cada card. Não envelhece num documento paralelo.

São **53 indicadores**: 11 de grupo (comparáveis), 9 de marketing e 10 a 11 próprios de
cada empresa — sem nenhuma interseção entre as três, o que é verificado por teste
automatizado.

Exemplo:

| Campo | CAC |
|---|---|
| Finalidade | Entender quanto custa conquistar um cliente novo, por canal e por empresa |
| Fórmula | `investimento_aquisicao ÷ novos_clientes` (coorte de entrada) |
| Fonte | `fato_investimento_mkt × fato_contrato` (via `id_lead`) |
| Interpretação | Quanto menor, melhor — desde que receita e retenção não caiam junto |
| Dono | Head de Marketing, por canal |
| Armadilha | Isolado, incentiva cortar canais caros que trazem o melhor LTV |

---

## 7. Dados faltantes — o que eu pediria para a operação registrar

O briefing pede esta postura explicitamente. Quando um KPI não pode ser calculado com
honestidade, o painel **diz isso** em vez de estimar (ver `tb_churn` na tela da TechBrabo).

| # | Campo | Momento do registro | KPI impossível sem ele |
|---|---|---|---|
| 1 | `data_hora_mudanca_estagio` | Toda transição | Ciclo, gargalo, tempo por etapa |
| 2 | `id_lead_origem` | Propagado até o contrato | **CAC e ROAS por canal** |
| 3 | `motivo_perda` | Ao marcar como perdida | O “porquê” do vazamento |
| 4 | `valor_comissao` + `data_recebimento` | Fechamento e repasse | Receita real e take rate |
| 5 | `num_vidas` + `premio_per_capita` | Cotação e contratação | Ticket real e APE |
| 6 | `data_implantacao_concluida` | Vigência / go-live | **Taxa de realização** |
| 7 | `horas_e_custo_por_projeto` | Apontamento semanal | Margem e ocupação |
| 8 | `data_cancelamento` + motivo | Saída do cliente | Churn, queda em 90 dias, retenção |

O mais crítico é o **#2**. Sem `id_lead` propagado até a receita, a pergunta “onde eu invisto
o próximo real?” não tem resposta baseada em dado — apenas opinião.

---

## 8. Testes

`python -m pytest` → **57 testes**, na ordem de risco:

1. **Fórmulas de KPI** — casos de borda: divisão por zero, período sem meta, amostra vazia,
   limiares inclusivos, sentido do indicador. Em painel executivo o bug mais caro não quebra
   a tela: mostra um número errado com aparência de certo.
2. **Qualidade dos dados** — integridade referencial cruzada, unicidade, eventos que não
   precedem a criação, entregas que não concluem antes da assinatura.
3. **Reconciliação** — a soma das partes bate com o todo: RRG do grupo = soma das empresas;
   receita por natureza = total; investimento por canal = total; funil monotonicamente
   decrescente; conversão nunca acima de 100%.
4. **Contratos de API** — toda métrica chega com valor, unidade, status e documentação; cada
   empresa tem KPIs próprios sem interseção; alerta traz as cinco perguntas e um destino; a tela de
   Saúde dos Dados declara os KPIs dependentes de cada campo e distingue campo vazio de inexistente.

---

## 9. Limitações conhecidas

**Da solução**

- **Atribuição last-touch na v1.** Subestima canais de descoberta no topo do funil.
  Multi-touch exige rastreio de jornada que provavelmente ainda não existe.
- **Forecast heurístico, não estatístico.** A ponderação entre ritmo e pipeline é
  transparente e auditável, mas não modela sazonalidade nem incerteza — não há intervalo de
  confiança na v1.
- **Sem dado de custo por venda**, o painel mede receita, não margem — exceto na TechBrabo,
  onde há apontamento de horas.
- **A comparação depende de metas bem definidas.** Meta mal calibrada contamina o semáforo
  inteiro, e o painel não tem como detectar isso sozinho.
- **Capacidade instalada da TechBrabo é premissa** (`CAPACIDADE_HORAS_MES`); em produção
  viria de um cadastro de alocação.
- **`tb_churn` não é calculável** com a estrutura atual — está declarado como indisponível
  na interface, com o campo que falta nomeado.

**Da carga demonstrativa**

- Os dados são **sintéticos e determinísticos** (semente fixa). Toda resposta da API traz
  `dados_demonstrativos: true` e a interface exibe aviso permanente e não dispensável — a
  seção 14 do briefing rejeita dado inexistente apresentado como real.
- O funil simulado converte de forma **otimista** frente ao mercado real (a razão
  lead→fechamento é mais alta do que se veria em tráfego pago). Isso afeta a plausibilidade
  absoluta de CAC e ROAS, não a lógica dos indicadores.
- Alguns sinais foram **plantados de propósito** para exercitar o motor de alertas; estão
  marcados com `[SINAL]` no comando de carga.

**Da leitura de negócio**

- A **TechBrabo não possui fonte institucional pública** — a própria seção 18 do briefing
  informa que sua descrição vem apenas do contexto fornecido para o desafio. Tudo que o
  projeto afirma sobre ela vem do briefing; inferências de mercado estão marcadas como
  “a validar”.
- O modelo de remuneração da Montseguro (agenciamento + corretagem recorrente, estorno em
  até 90 dias) segue o padrão do setor e **precisa ser confirmado com a operação**.

---

## 10. Roadmap

| Horizonte | Entrega | Depende de |
|---|---|---|
| v1.1 | Coortes e LTV real | 6+ meses de histórico com `id_lead` |
| v1.1 | Resumo diário para a liderança | Motor de alertas em produção |
| v1.2 | Forecast estatístico com faixa de confiança | 2+ ciclos de histórico |
| v1.2 | Detecção de anomalia por decomposição de série | Série temporal densa |
| v1.3 | Simulador “e se” de realocação de verba | Elasticidade medida por canal |
| v1.3 | Metas por vendedor e por equipe | Metas individuais definidas |
| v2 | Atribuição multi-touch | Rastreio completo de jornada |

A ordem não é por dificuldade técnica, e sim por **quanto cada item muda uma decisão real
da liderança** — o mesmo filtro aplicado aos KPIs.

---

## 11. Estrutura do repositório

```
backend/
  config/          Django: settings, urls, wsgi
  core/            Modelo dimensional + admin + comando de carga
    management/commands/seed_demo.py
  kpis/            CAMADA SEMÂNTICA
    registry.py    KpiDef, Metrica, catálogo
    definicoes.py  Os 53 indicadores documentados
    consultas.py   Consultas base (único lugar que toca o ORM)
    periodo.py     Aritmética de ritmo em dias úteis
    grupo.py       Ritmo, forecast, semáforo, comparação
    comercial.py   Funis, gargalo, pipeline, produtividade
    marketing.py   Cascata, matriz de canais, coortes
    empresa.py     KPIs próprios de cada operação
    alertas.py     As nove regras
    saude_dados.py Completude de campos e KPIs bloqueados
  api/             FastAPI: rotas e contratos Pydantic
  tests/           57 testes
frontend/
  src/lib/         Tipos, cliente da API, formatação
  src/components/  KPI card com ficha, semáforo, medidor, funil, alerta
  src/pages/       As seis telas
```

---

Alexis Pincowscy · Agosto de 2026
Fontes institucionais consultadas conforme a seção 18 do briefing:
[montseguro.com.br](https://montseguro.com.br/) · [prop5.com.br](https://prop5.com.br/)
