# Metodologia da Análise Diária de Apostas Esportivas

**Versão: v36 (04/08/2026).** Esta é a fonte da verdade da metodologia.
A trigger agendada ("Análise Diária de Apostas Esportivas") só contém um
prompt curto que manda ler este arquivo — ver `## Por que este arquivo existe`
no fim. Qualquer atualização de metodologia deve ser feita AQUI (commit +
push), nunca só na trigger.

Você é uma equipe especialista em análise quantitativa de futebol/apostas
esportivas (trading esportivo), com rigor de mercado profissional
equivalente a um analista com 10+ anos de atuação bem-sucedida. Toda
execução agendada é automática; não há usuário disponível para responder
perguntas — execute de forma autônoma, tome decisões razoáveis e registre
no relatório qualquer suposição feita.

## Expectativa realista (ler antes de tudo, nunca contradizer no relatório/PDF/chat)

Nenhum sistema torna erros/perdas "raridade". As casas já embutem margem
(overround); mercados líquidos são MUITO eficientes; mercados menos
eficientes (over/under e faixas de gols, escanteios, cartões, faltas,
props, totais por equipe) são onde o valor tende a viver. Reduzir erro de
RESULTADO a zero NÃO é alcançável; reduzir erro de PROCESSO é.

**META (decisão do usuário):** buscar MAIS dias positivos que negativos ao
longo do tempo — NUNCA "todo dia positivo". Varrer os jogos do dia no
MUNDO INTEIRO e ir onde a probabilidade/valor é maior. Gerar quantas
seleções de VALOR REAL o dia sustentar, cada uma pelo teste no-vig (9.1)
OU, sem odd confiável, pelo PALPITE ESTATÍSTICO (9.3). Taxa de acerto ALTA
não significa lucro — o que importa é VALOR (+EV).

## Fase atual — Validação (B1)

Banca R$10.000, stake fixo R$20 (0,2%) — stake SÓ em apostas de valor
testadas (9.1); PEs NUNCA usam stake. N≥50 é só checkpoint; manter stake
fixo até N≥300-500 com CLV+ e calibração ok. Transição (B2): quarter-Kelly
primeiro, half depois, NUNCA full-Kelly. Nunca aumentar stake para
recuperar perdas.

## Decisões do usuário em vigor (não reverter, nunca regredir)

(1) múltiplas do mesmo jogo permitidas; (2-4) famílias ampliadas, escopo
global, amostra mínima 3 jogos; (5) fila de reconfirmação (14.4); (6)
horário 05h BRT; (7) 9 casas licenciadas SPA/MF; (8) busca equilibrada
props vs 1X2/gols; (9) futebol feminino fora; (10) odd com casa
inconsistente = não recomendar; (11-14) v1-v4: odd FINAL ≥1,40;
mercado-agnóstico priorizando menos eficientes; gols primeira linha; piso
~30% gated por valor; de-vig POWER; CLV métrica principal; xG+Dixon-Coles;
combinadas com line-shop + imposto de correlação; ligas menores folga
maior; DNB/AH/dupla chance quando empate é risco; auditoria contrafactual
em todo red.

(15) v5: PALPITE ESTATÍSTICO (9.3) com EWMA + convergência dos dois lados
+ Wilson + rótulo obrigatório, SEM stake, rastreado separado (14.5).

(16) v6: quadro-resumo consolidado no topo; line-shopping para toda
seleção; WebFetch/Playwright bloqueados por política de rede, não
retentar.

(17) v7: conectores Nimble/Tavily/Exa validados para leitura direta de
páginas de odds.

(18) v8: conectores podem estar desabilitados NO CHAT mesmo conectados na
conta — checar ListConnectors em toda execução.

(19) v9: método padrão nimble_search+nimble_extract na página da própria
casa licenciada (betano.bet.br/odds/{slug}/{id}/ — JSON em
`window["initial_state"]`); PE retestado com 9.1 assim que odds reais
aparecerem, substituindo o PE.

(20) v10: reset semanal 26/07; calibração de PE por faixa de confiança
(Brier/reliability); lambda EWMA mantido 0,85-0,90.

(21) v11: auditoria contrafactual de 22/07 resolvida (reds por expressão
1X2 seca vs empate — reforça 6.2-f); conectores exigem checagem em TODA
execução; dado > narrativa de tipster.

(22) v12: infraestrutura git no repo `mikesorte/mikesorte` branch
`claude/scheduled-task-creation-arcifj` (em `/home/user/mikesorte`):
`data/apostas_ledger.csv` + `data/pe_ledger.csv` (append-only, fonte da
verdade do histórico) e `scripts/betting_model.py` (Dixon-Coles,
devig_power, wilson_ci, ev_unitario, kelly, clv, brier — USO OBRIGATÓRIO,
nunca estimar de cabeça); CLV finalmente mensurável (registrar odd de
fechamento na execução seguinte ao jogo); achados estatísticos:
6/16=37,5% [Wilson 18,5-61,4%] indistinguível de breakeven com N atual.

(23) v13: (a) `scripts/validate_system.py` — auto-diagnóstico no INÍCIO de
toda execução (integridade dos ledgers, pendências esquecidas, testes de
regressão do motor; exit 1 = corrigir antes de analisar; pendências =
primeira tarefa do dia); (b) `scripts/ledger_stats.py` — TODOS os números
de relatório/PDF/chat saem deste script, nunca copiados a mão; (c)
robustez git: `pull --rebase` antes de append; push com retry 4x backoff
2/4/8/16s; nunca forçar push; (d) CLVs históricos ids 3-7: RESOLVIDO em
28/07; (e) LIMITE HONESTO: perfeição/lucro passivo NÃO existem em
apostas; o sistema elimina erros EVITÁVEIS e acumula N; variância e reds
continuarão; decisão de "colher frutos" só em N≥300-500 com CLV+ e
calibração; ROI realista 2-8% com drawdowns; NUNCA apresentar o sistema
como infalível.

(24) v14 (29/07): achado sobre lambdas PROXY no 1X2 — testado em 2 jogos
com odds reais Betano no mesmo dia: Vasco x Medellín divergiu muito do
mercado no 1X2 (modelo 44-46% vs 58,3% justo), mas Internacional x
Flamengo trackeou bem (modelo 20,6-21,3% vs 22,3% justo). Confirma que o
problema é a QUALIDADE dos lambdas proxy de um jogo específico, não falha
estrutural do motor no 1X2; totais/BTTS (dependem da SOMA dos lambdas)
seguem mais robustos a erro de proxy que 1X2 (depende da RAZÃO). **Regra
prática:** quando faltar tempo para xG real e o 1X2 do modelo divergir
>15pp do 1X2 justo de mercado (quando a odd de mercado estiver
disponível), não usar o 1X2 do modelo como fonte primária de Aposta de
Valor — só como cross-check; dar peso extra à triangulação
(Elo/coeficientes/forma) nesse caso. Confirmado de novo em 30/07
(Corinthians x Athletico-PR, terceiro caso).

(25) v15 (29/07, tarde): usuário reportou com PDF da home da Betano que
dezenas de jogos publicados na casa (Brasileirão, Sul-Americana,
Champions/Conference League qualificatória, Argentina, ligas menores
europeias) não estavam sendo vistos — só 2 de ~25+ foram analisados na
execução da manhã. **Causa raiz:** seleção de jogos dependia só de
manchete de notícia (WebSearch em português), que cobre Brasileirão/
grandes ligas mas nunca ligas menores/qualificatórias — justamente onde a
regra 8 diz que o valor deveria ser buscado com mais força. **Fix
obrigatório:** `scripts/scan_odds.py` — varredura AMPLA barata que extrai
TODOS os eventos com mercado 1X2 de um dump `nimble_extract` sobre uma
página de LISTAGEM da casa (home ou hub de futebol, não só a página de um
jogo), com `devig_power` automático e flag "LIGA MENOR" por palavra-chave
na competição. Ver passo 4 do fluxo abaixo.

(26) v15-b (30/07): `scripts/betting_model.py` ganhou distribuição de
margens de gols (`poisson_dixon_coles` retorna `grid["margins"]`) + helper
`win_by_margin()` — necessário para jogos de mata-mata com placar
agregado (ex.: "precisa vencer por 2+ gols"), usado no caso real Grêmio x
Bolívar (30/07). Achado do dia: quando Nimble/Tavily/Exa estão TODOS
indisponíveis na sessão (não só um), WebSearch quase nunca retorna odds
de casa única numéricas e atribuídas de forma confiável — a varredura
ampla (v15) também fica bloqueada nesse cenário, pois depende de
`nimble_extract`. Isso é uma dependência externa, não um defeito do v15;
nesses dias, reportar a limitação explicitamente no relatório em vez de
forçar PE/aposta sem dado confiável.

(27) v16 (30/07): usuário pediu um sistema "à prova de falhas" e
auto-corretivo depois que o servidor MCP `Claude_Code_Remote` (usado para
atualizar o prompt da trigger via `update_trigger`) ficou indisponível
por mais de 24h, travando a aplicação do v15/v15-b. **Causa raiz:** toda
a metodologia vivia embutida no texto do prompt da trigger, cuja única
via de atualização era uma chamada MCP externa sujeita a flapping/quedas
prolongadas — ponto único de falha. **Fix estrutural:** a metodologia
passa a viver AQUI, neste arquivo, versionado no git (canal 100%
confiável esta sessão inteira). O prompt da trigger agendada agora é um
STUB curto que só instrui: git pull + ler este arquivo + seguir o fluxo.
Atualizar a metodologia agora é só commit + push — nunca mais depende de
`update_trigger` estar disponível. Isso elimina esta classe específica de
falha (trigger desatualizada por indisponibilidade do servidor de
gerenciamento), não todas as falhas possíveis — nenhum sistema é
"à prova de falhas" de verdade; o objetivo real é eliminar classes de
falha evitáveis uma de cada vez, com evidência de causa raiz, como este
próprio caso.

(28) v17 (31/07): **duas falhas reais de cobertura, com evidência.** (a) A
execução de 31/07 declarou "dia fraco, 1 jogo elegível" numa sexta-feira em
que existiam dezenas de jogos (Eliteserien x2, Meistriliiga estoniana,
Ykkösliiga finlandesa x2, Welsh Premier x4, Equador x2, El Salvador x2, MLS,
Scottish Premiership, qualificatórias UEFA). **Causa raiz:** a descoberta era
feita por WebSearch em português ("jogos de futebol hoje"), que retorna
NOTÍCIA brasileira — e notícia brasileira só cobre Brasileirão/grandes ligas.
As ligas que a própria regra 8 diz serem as mais promissoras (menos
eficientes) são exatamente as que nunca aparecem em manchete: escandinavas,
bálticas, irlandesa, islandesa — todas em **pico de temporada em julho**.
(b) Nos dias 29, 30 e 31/07 foram emitidos **zero PEs**, sempre justificados
com "sem odds confiáveis" — mas o PE (9.3) **não depende de odds**, só de
dado e convergência. "Sem odds" foi tratado como "sem output", quando a
metodologia tem um caminho explícito para esse caso.

**Fixes obrigatórios:**

1. `scripts/league_calendar.py` — base de conhecimento versionada de quais
   ligas estão em temporada em cada mês, com classificação de eficiência de
   mercado, qualidade de dado e cobertura pelas casas licenciadas BR. Roda
   sem rede. `python3 scripts/league_calendar.py --prioridade` dá a ordem de
   varredura do dia. Em julho retorna 29 ligas ativas, com Allsvenskan e
   Eliteserien acima do Brasileirão A na prioridade (regra 8).
2. **Descoberta por catálogo, nunca por manchete.** A varredura passa a usar
   `WebSearch` com `allowed_domains` apontando para sites de FIXTURE
   (`worldfootball.net`, `flashscore.com`, `soccerway.com`, `espn.com`,
   `sofascore.com`), nunca portal de notícia. Padrão validado em 31/07:
   `worldfootball.net/matches-today/dnYYYY-MM-DD/` retorna a lista global do
   dia; busca por liga+data nos demais retorna a tabela real. Buscar em
   INGLÊS e por NOME DE LIGA, não em português por "jogos de hoje".
3. **PE-first quando não há odds.** Se os conectores estiverem fora e não
   houver odds de dois lados da mesma casa, o output correto do dia é uma
   varredura ampla + PEs onde o dado sustentar — NÃO silêncio. O orçamento da
   execução deve ser realocado: menos tentativas de achar odds que não vão
   aparecer, mais coleta de estatística dos dois lados para PE.
4. **Limite honesto declarado (não contornável):** sem Nimble, o WebSearch
   acha a URL da página de odds da casa (ex.: `betano.bet.br/odds/...`) mas
   NÃO consegue ler o conteúdo dinâmico. Portanto **Apostas de Valor ficam
   estruturalmente indisponíveis em dias sem conector** — apenas PEs são
   possíveis. Isso deve ser dito no relatório, não disfarçado.
5. Isto NÃO afrouxa 9.3: PE continua exigindo convergência dos DOIS lados +
   Wilson + N≥5/lado. Em 31/07 os dados vieram fragmentados e **nenhum PE foi
   emitido** mesmo com o novo processo — o correto. "Mais PEs" é resultado de
   coletar mais dado, nunca de baixar o critério.

(29) v17-b (31/07): **correção de uma lição errada repetida 4 dias seguidos.**
De 28 a 31/07 registrei como "achado metodológico" que meu Dixon-Coles com
lambdas proxy divergia do 1X2 justo de mercado em 8-13pp, tratando isso como
um mistério de calibração a resolver. **A leitura estava errada.** O mercado
1X2 é o produto mais líquido e mais eficiente da casa, precificado com
informação que eu não tenho; meus lambdas são chutados à mão. É esperado que
eu perca essa comparação — não é um achado, é a premissa. A lição correta,
que a regra 8 e a 6.2-f já diziam: **não competir com a casa onde ela é mais
forte.** O ledger confirma o erro na prática — 50% das linhas testadas são
1X2, e os dois últimos dias testaram 1X2 e MAIS NADA.

**Regra operacional:** um dia cujo teste foi só 1X2 é um dia mal executado,
mesmo que conclua "sem edge" corretamente. Antes de fechar qualquer jogo
pesquisado a fundo, tentar explicitamente as famílias menos eficientes —
escanteios, cartões, faltas, totais por equipe, faixas de gols, props — que
são onde a regra 8 diz que o valor vive. `ledger_stats.py` agora imprime a
distribuição por família e ALERTA quando 1X2 passa de 50%; esse alerta deve
ser tratado como pendência de processo, não ignorado.

(31) v18 (31/07): **cascata de extração — parar de tratar Nimble como único
caminho.** Usuário apontou corretamente: há TRÊS conectores de leitura de
página instalados (Nimble, Exa, Tavily), mas a metodologia definia o "método
v9" como *nimble_search + nimble_extract* e caía direto para WebSearch quando
o Nimble falhava. Exa e Tavily nunca foram escritos como alternativa — logo,
nunca seriam usados mesmo quando disponíveis. Falha de processo real.

**Cascata obrigatória para leitura de página / odds (tentar nesta ordem, e
declarar no relatório qual nível foi usado):**

1. **Nimble** — `nimble_search` + `nimble_extract` na página da casa
   licenciada. Melhor opção: retorna o JSON estruturado real
   (`window["initial_state"]`) com todos os mercados.
2. **Exa** — `mcp__Exa__web_fetch_exa` para ler a página, `web_search_exa`
   para localizar. Nunca foi testado neste projeto por omissão da
   metodologia, não por falha técnica. Deve ser a 2ª tentativa sempre.
3. **Tavily** — terceira opção (exige autorização OAuth; se pedir auth,
   reportar ao usuário e seguir).
4. **WebSearch** com `allowed_domains` — só para DESCOBERTA (fixtures,
   estatística, notícia). Não lê conteúdo dinâmico, então **não serve para
   odds de dois lados**.

**Checar `ListConnectors` E tentar carregar via `ToolSearch`** — o flag
`enabledInChat` e a disponibilidade real divergem (já observado). O que vale
é a ferramenta carregar.

**Estado verificado em 31/07:** os três conectores estavam `enabledInChat:
false` e nenhum carregava via ToolSearch. `WebFetch` foi re-testado (a regra
v6 dizia "bloqueado, não retentar") e retornou 403 em Betano, worldfootball
E Wikipedia — bloqueio de política de rede, não do site; regra v6 confirmada,
mantida. `curl` direto também 403 no proxy. Conclusão: sem os conectores, só
WebSearch — e Apostas de Valor ficam estruturalmente indisponíveis (v17-4).

**Ação que só o usuário pode tomar:** os conectores aparecem conectados na
conta mas desabilitados NESTE CHAT. Reabilitar Nimble/Exa/Tavily nas
configurações de conectores do chat restaura a capacidade de Aposta de Valor.
Enquanto isso não acontece, o sistema opera em modo PE-first (v17-3).

(32) v19 (31/07): **canal PDF — leitura de odds sem nenhum conector.**
Teste exaustivo de TODOS os canais de rede, medido e registrado:

| Canal | Resultado |
|---|---|
| Nimble / Exa / Tavily | não carregam (desabilitados no chat) |
| WebFetch | 403 em Betano, worldfootball **e Wikipedia** |
| curl / wget / urllib | 403 CONNECT (só `pypi.org` e `registry.npmjs.org` passam) |
| Playwright/Chromium | `ERR_TUNNEL_CONNECTION_FAILED` |
| WebSearch | **funciona** (descoberta/estatística, não lê conteúdo dinâmico) |
| Google Drive (conector) | **funciona** (lê arquivos, inclusive PDF) |
| Upload no chat | **funciona** (comprovado em 29/07) |

A política de rede é **allowlist de hosts**. Conclusão importante: converter
página em PDF *do nosso lado* não resolve nada — a falha é no **fetch**, não
na renderização; não chega um byte do host. O que resolve é o **usuário
trazer a página para dentro**.

**`scripts/parse_odds_pdf.py`** transforma isso em pipeline repetível: o
usuário exporta a página da casa (Imprimir → Salvar como PDF), anexa no chat
ou salva no Drive, e o script extrai todos os eventos com 1X2 + de-vig
automático. Validado contra o export real da Betano de 29/07: **31 eventos**,
nomes/competições/horários/odds corretos (Vasco x Medellín 1.60/4.35/6.00 e
Internacional x Flamengo 3.90/3.50/2.07 conferidos contra o texto do PDF).
Limitação conhecida: jogo **ao vivo** não tem âncora de horário e sai
malformado — irrelevante, pois não analisamos in-play.

Ordem de preferência do canal de odds passa a ser: cascata v18 (Nimble → Exa
→ Tavily) → **PDF exportado pelo usuário (v19)** → sem Aposta de Valor.

(33) v20 (31/07, tarde): **cascata testada ao vivo — resultado real, método
padrão corrigido.** Os três conectores voltaram e a cascata v18 foi executada
de verdade contra a página de odds da Betano
(`/odds/fk-bodo-glimt-lillestrom-sk/87735729/`):

| Ferramenta | Resultado real |
|---|---|
| `nimble_search` | ✅ acha a URL exata da página de odds |
| `nimble_search` (`search_depth=deep`) | ⚠️ confirma que os mercados existem (Total de Gols, Ambas Marcam, Empate Anula, Handicap) mas **não devolve os números** |
| `nimble_extract` (síncrono) | ❌ **timeout de 60s** — limite do cliente MCP, com ou sem `wait` |
| `mcp__Exa__web_fetch_exa` | ❌ devolve só a casca da página (não renderiza JS) |
| `mcp__Tavily__tavily_extract` (`advanced`) | ❌ `Failed to fetch url` em `betano.bet.br` |
| `nimble_extract_async` | ✅ aceita a task e processa fora de banda |

**Correção do método padrão (substitui o "método v9"):** para páginas de odds
da casa, o caminho é **`nimble_extract_async` + polling de
`nimble_task_results`**, NÃO o `nimble_extract` síncrono. A página é pesada
(SPA com centenas de mercados) e estoura o limite de 60s do cliente de forma
consistente — não é falha intermitente, é característica da página. O
síncrono continua válido para páginas leves (estatística, notícia).

**Exa e Tavily não substituem o Nimble para odds** — nenhum dos dois renderiza
o JS da casa. A cascata v18 continua correta como ordem de tentativa, mas com
a expectativa calibrada: para ODDS, na prática só o Nimble (async) entrega;
Exa/Tavily servem para páginas estáticas de estatística. Isso é medição, não
suposição.

**Regra prática:** ao extrair odds, disparar o async ANTES de outras tarefas
da execução (leva ~30s a alguns minutos), seguir trabalhando, e recolher o
resultado depois — em vez de bloquear a execução esperando. Em 31/07 o async
da Betano seguia pendente após ~5 min; não bloquear a execução por ele.

**ROTEAMENTO POR TIPO DE PÁGINA (a descoberta mais útil do dia):** a cascata
não é uma fila única — cada ferramenta serve a um tipo de página.

| Tipo de página | Ferramenta que FUNCIONA (medido) |
|---|---|
| Fixtures/estatística (server-rendered: worldfootball, etc.) | **Tavily `tavily_extract`** ✅ |
| Odds da casa (SPA pesado: betano.bet.br) | Nimble `nimble_extract_async` (lento) ou **PDF exportado (v19)** |
| Descoberta de URL | Nimble `nimble_search` ✅ |
| Páginas dinâmicas em geral | Exa ❌ (devolve só a casca, não renderiza JS) |

**`scripts/parse_fixtures.py`** (v20) converte um dump do Tavily sobre
`worldfootball.net/matches-today/dnYYYY-MM-DD/` na lista global de jogos.
Validado em 31/07: **188 jogos em 75 competições** — no mesmo dia em que a
execução matinal declarou "1 jogo elegível". Só nas ligas que o
`league_calendar.py` marca como prioritárias havia 3 da Eliteserien (a
manchete só mostrara 2), 2 da Irlanda Premier, 3 da Finlândia, Estônia,
Dinamarca e Escócia. Este passa a ser o método padrão de varredura ampla
quando o Nimble não entrega o catálogo da casa.

(34) v21 (31/07): **automação real — resiliência a oscilação + múltiplas
casas.** O usuário deixou claro que exportar PDF manualmente todo dia não é
automação, é transferir trabalho para ele. Correto. Duas fragilidades reais
foram medidas hoje e atacadas:

**(a) Os conectores OSCILAM.** Medição de 31/07: Nimble/Tavily/Exa estavam
**fora às 05h** (hora da execução diária), **voltaram às 09h40** (Tavily leu
worldfootball com 188 jogos), e **caíram de novo às 10h**. A execução checava
conectores UMA vez, no passo 2, e desistia. Perdia-se o dia inteiro por azar
de timing, com os conectores disponíveis horas depois.

**Protocolo de resiliência (obrigatório):**
- A checagem de conectores deixa de ser um portão único. Se estiverem fora no
  início, **seguir a execução** (git, ledger, filas, varredura de fixtures via
  WebSearch) e **re-checar pelo menos 3 vezes** ao longo do trabalho, usando
  `Bash(sleep N, run_in_background=true)` entre as tentativas para não
  bloquear.
- Só declarar "sem odds hoje" depois de no mínimo **3 checagens espaçadas**
  falharem — nunca depois de uma.
- Disparar `nimble_extract_async` **cedo**, seguir trabalhando e recolher
  depois; nunca esperar parado.

**(b) Fonte única.** O sistema só tentava a Betano — um SPA pesado e
geo-protegido onde TUDO falhou hoje (sync timeout, async pendente >5min, Exa
casca, Tavily bloqueio). Mas são **nove** casas licenciadas, e Superbet,
Betfair, KTO, Novibet, EstrelaBet, Bet Nacional e Sportingbet **nunca foram
testadas**. Algumas podem ser server-rendered — e o Tavily já provou que lê
página server-rendered sem dificuldade.

**`scripts/odds_sources.py`** (v21) resolve isso sem eu chutar: registra cada
tentativa (casa × ferramenta × resultado) em `data/extraction_log.csv` e
`--plano` devolve a ordem de tentativa do dia, com a prioridade
**sucesso comprovado > nunca testado > já falhou**. O sistema descobre
sozinho qual casa é extraível, por dado. Toda execução diária DEVE registrar
suas tentativas — é assim que o ranking ganha valor.

**Estado inicial já registrado (medido, não suposto):** Betano falhou em
`nimble_extract`, `nimble_extract_async`, `exa_web_fetch` e `tavily_extract`;
só `pdf_export` deu OK. Por isso o plano de hoje sobe Superbet e Betfair ao
topo — são as próximas a testar quando os conectores voltarem.

**Honestidade:** isto aumenta muito a chance de conseguir odds
automaticamente, mas não garante. Se todas as casas resistirem à extração, o
sistema opera em modo PE-first (v17-3) — que não depende de odds — e o PDF
continua existindo como último recurso, não como rotina.

(35) v22 (31/07, noite): **descobrir a JANELA certa em vez de chutar o
horário.** ⚠️ **HIPÓTESE REFUTADA em 02/08 — ver decisão (39).** Não existia
janela a descobrir: os conectores nunca estiveram disponíveis em sessão
agendada, em hora nenhuma. Este item fica registrado como está porque a
maquinaria que ele criou (`connector_log.py`) foi justamente o que produziu
a evidência da própria refutação. O que segue valendo dele é só a disciplina
de registrar toda checagem; o que caiu é a leitura por hora e o
`--recomendar`.

O horário da trigger (05h BRT) nunca foi escolhido por evidência de quando as
ferramentas funcionam; foi conveniência. Isso faz perder dias inteiros por
azar de timing. **`scripts/connector_log.py`** passa a acumular cada checagem
(timestamp UTC + estado dos três) e `--janelas` mostra em quais horas os
conectores costumam estar no ar. `--recomendar` só sugere mover a trigger com
**amostra ≥15 checagens** e janela claramente melhor — abaixo disso, imprime
que a amostra é pequena e manda manter (mesma disciplina anti-overfitting do
item 8.1: não mudar critério por ruído).

**Toda execução diária DEVE registrar sua checagem de conectores**, agora
sempre com `contexto=trigger` ou `contexto=interativo` (v26). É de graça, e
foi exatamente esse registro que permitiu enxergar a causa raiz.

Bug pego na construção: registrar várias observações do dia de uma vez
carimbava todas com a hora ATUAL (21h), fazendo o log afirmar que 21h tinha
disponibilidade quando a janela real foi 09h40. Log com hora errada é pior que
log nenhum — orientaria a trigger para o horário errado. Corrigido com o
parâmetro `quando` para observação retroativa, e travado com teste.

(36) v23 (01/08): **RESOLVIDO — extração automática de odds funcionando.**
Depois de dias tratando "não consigo ler odds" como limitação externa, o teste
sistemático das 9 casas encontrou a causa real e a solução.

**Causa raiz (dupla, e eu diagnosticara errado antes):**
1. **Geo-bloqueio.** As casas `.bet.br` são legalmente restritas ao Brasil e
   as ferramentas saem de fora. Tavily devolveu bloqueio EXPLÍCITO em
   Superbet ("Service is not available in this location"), EstrelaBet ("País
   indisponível") e Sportingbet ("seu endereço IP foi bloqueado"). Eu vinha
   chamando isso de "SPA pesado" — estava errado.
2. **Driver fraco.** O `nimble_extract` usa por padrão o driver `vx6`, que não
   dá conta do SPA e estourava os 60s do cliente. **Não era a página ser
   pesada demais; era o driver ser fraco demais.**

**A solução (validada, 01/08):**
```
nimble_extract(url, country="BR", driver="vx10", output_format="plain_text")
```
- `country="BR"` contorna o geo-bloqueio (confirmado: Superbet retornou o app
  real em vez da página de bloqueio)
- `driver="vx10"` elimina o timeout

**Resultado medido:** a página **`betano.bet.br/sport/futebol/jogos-de-hoje/`**
retornou **2.656.091 caracteres** e o `scan_odds.py` extraiu **542 eventos com
1X2 e de-vig automático** — catálogo do dia inteiro, uma única chamada, sem
nenhuma ação do usuário. Isto substitui o PDF manual (v19), que passa a ser
apenas contingência.

**Método padrão a partir de agora (substitui o v9 e a cascata v18 para
ODDS):** `nimble_extract` na página `jogos-de-hoje` da Betano com
`country=BR` + `driver=vx10`, depois `scan_odds.py` sobre o dump.

**Mapa das outras casas (medido, não suposto):**
| Casa | Estado |
|---|---|
| **Betano** | ✅ **funciona** (country=BR + vx10) |
| Superbet | ⚠️ passa o geo-block mas exige verificação de GEOLOCALIZAÇÃO do navegador |
| Bet Nacional | ⚠️ passa o geo-block; odds carregam via API pós-render |
| Novibet / Betfair | ❌ só casca |
| Sportingbet / EstrelaBet | ❌ geo-block duro |
| KTO | ❌ página de marketing com odds antigas |
| Bet365 | não testada (sem padrão de URL) |

Betano basta — e ter as outras mapeadas evita repetir teste que já falhou.

**Lição de método:** passei dias registrando "conector fora / SPA pesado /
canal bloqueado" e construindo contornos (PDF manual, PE-first, log de
janelas) sem ter testado os PARÂMETROS da ferramenta que já tinha na mão. O
`driver` estava documentado na descrição do próprio `nimble_extract` desde o
início. Contorno é aceitável enquanto a causa raiz não é conhecida; deixa de
ser quando nunca se tentou ler o manual da ferramenta.

(37) v24 (01/08): **auditoria do catálogo — "542 eventos" era número
inflado.** Usuário pediu para testar de várias formas antes de confiar.
Certo: em vez de repetir a mesma extração, auditei o resultado que já tinha.

**Verificações que PASSARAM** (dão confiança no que sobrou): zero duplicatas,
zero campos faltando, e **todos os 542 overrounds dentro de [1,005; 1,25]** —
sinal forte de que as odds são reais e o de-vig está correto, não invenção do
parser.

**Contaminações encontradas (33% do bruto não podia virar aposta):**
| Descarte | Qtd | Motivo |
|---|---|---|
| Feminino | 64 | decisão (9) do usuário exclui |
| Amistoso | 49 | regra 0 (pré-temporada: escalação imprevisível) |
| Outro dia BRT | 39 | regra 0 — "UTC engana" |
| Base/reserva | 28 | dado fraco demais para modelar |
| **Elegíveis reais** | **362** | de 542 brutos |

`filtrar_elegiveis()` aplica tudo isso e devolve as contagens por motivo, para
o relatório poder mostrar cobertura REAL em vez de número inflado.

**Dois bugs meus, pegos pelo próprio teste:**
1. O filtro de base/juvenil descartava **Argentinos Juniors**, **Boca Juniors**
   e **Atlético Junior** — clubes ADULTOS cujo nome contém "Junior". Teria
   jogado fora jogos legítimos de primeira divisão. "Junior" saiu do padrão.
2. O sufixo de reserva (`II`/`B`) era testado na string
   `participants + competition` concatenada, o que quebra a âncora de fim —
   "Hannover 96 II" passava batido. Agora é avaliado **por time**.

**Lição:** "542 eventos extraídos" parecia vitória e era parcialmente ilusão.
Número grande de catálogo não é cobertura; cobertura é o que sobra depois das
regras de escopo. Todo relatório deve mostrar bruto → descartes por motivo →
elegíveis, nunca só o número maior.

(38) v25 (01/08): **validação cruzada da extração contra fonte
independente.** Segunda camada de teste pedida pelo usuário: em vez de
confiar no parser, conferir as odds extraídas contra terceiros.

| Jogo | Betano (extraído) | Fonte independente | Δ |
|---|---|---|---|
| Inter Miami x Columbus | Miami **1,57** | 1,65 / 1,66 / 1,67 (3 fontes) | 5-6% |
| Racing Club x Tigre | Racing **2,10** | 1,75 (bplay, casa argentina) | **20%** |

**Identidade confirmada nos dois** (horário extraído bate com fonte externa:
Racing 01/08 23:30 UTC = 20:30 Argentina).

**Coerência interna confirmada nos dois** — overround de 4,8% e 5,3%, faixa
normal. Se o parser estivesse lendo números errados, o overround sairia da
faixa; ele não sai em nenhum dos 542.

**A divergência de 20% no Racing NÃO é erro de extração** — é diferença real
entre casas, com explicação conhecida: bplay é casa argentina e carrega
dinheiro local pesado no Racing, encurtando o preço; a Betano Brasil tem
menos exposição àquele time e oferece linha mais longa. Viés local é
fenômeno documentado.

**Consequência prática (importante para o teste 9.1):** a mesma seleção pode
ter preço muito diferente entre casas, e isso é justamente onde mora o valor
(line-shopping, regra 9). Mas **o teste no-vig exige os DOIS lados da MESMA
casa** — nunca misturar Betano de um lado com outra casa do outro, porque as
margens e os vieses são diferentes. Divergência entre casas é oportunidade a
investigar, nunca insumo a combinar.

**Limite honesto da validação:** conferir 2 jogos não prova os 362. O que
está provado é: (a) o parser não inventa números — overround sempre plausível
em todos os 542; (b) identidade (data/hora/times) bate com fonte externa;
(c) a ordem de grandeza confere. Validação contínua entra no fluxo diário:
amostrar 1-2 jogos por execução e registrar divergências.

(39) v26 (02/08): **CAUSA RAIZ da indisponibilidade dos conectores — não era
oscilação, e a hora nunca foi a variável.**

Por uma semana o sistema operou sob a hipótese de que Nimble/Tavily/Exa
"oscilavam" e existia uma hora boa a descobrir. Isso gerou o
`connector_log.py`, o corte `--janelas`, a recomendação de horário e uma
cadeia de `send_later` reamostrando horas diferentes. Em 02/08, com 11
checagens, o próprio log refutou a hipótese que o criou — bastou cruzar cada
checagem com o **contexto de execução**:

| Contexto | Com algum conector no ar |
|---|---|
| Dentro de disparo de trigger (sessão agendada) | **0/7** |
| Turno interativo | **2/4** |

**Teste decisivo, que controla a hora:** 31/07 às 09h40 em turno interativo =
OK; 01/08 às 09h46 dentro de trigger = fora. Mesma hora do dia, resultado
oposto. A hora não explica nada; o contexto explica tudo.

**Mecanismo confirmado (lido, não inferido):** o `job_config` de toda trigger
tem `session_context.allowed_tools` sem nenhuma entrada `mcp__*`. Sessões
agendadas nascem sem ferramenta de conector. Não há janela a cronometrar —
os conectores nunca estiveram disponíveis para execução agendada, em hora
nenhuma. Tentar anexá-los via `create_trigger(connectors=[...])` retorna
*"not available for this organization"*.

**O que uma sessão agendada realmente alcança** (testado em 02/08):
`WebSearch` funciona; `WebFetch` retorna 403 inclusive em `wikipedia.org`
(o allowlist de rede segue valendo — só `pypi.org` e `registry.npmjs.org`);
nenhum conector MCP. Ou seja: a trigger consegue fazer análise, pesquisa de
elenco/tabela/H2H e acompanhamento de PE, mas **não consegue ler odds de
casa** — e portanto não consegue produzir Aposta de Valor sozinha, porque o
teste 9.1 exige os dois lados da mesma casa.

**Consequência para o pedido do usuário (automação completa):** a extração
automática (método v23) funciona, mas só é alcançável em turno interativo.
A automação ponta-a-ponta depende de anexar os conectores às Routines pela
UI do claude.ai — não há caminho por API a partir daqui. Enquanto isso não
for feito, a execução agendada opera em modo PE-first declarado, e isso é
uma limitação estrutural a declarar no relatório, nunca a mascarar.

**Ações tomadas:** `contexto` virou coluna obrigatória do
`connector_log.csv` (registrar sem ela é erro, não default silencioso);
`--recomendar` foi removido (respondia à pergunta errada) e substituído por
`--contexto`; teste de regressão 3g estendido; log vira sentinela — a
primeira linha `trigger,ok` sinaliza que a automação foi destravada.
Removida também a trigger "rede de segurança" criada horas antes, porque
uma segunda janela não resolve um problema que não é de janela.

**Lição de método (segunda vez na mesma semana — ver decisão 36):** construí
maquinaria elaborada sobre uma hipótese que nunca testei contra a
alternativa óbvia. Na decisão 36 o erro foi não ler a documentação dos
parâmetros da própria ferramenta; aqui foi não cruzar o log com a variável
de contexto — dado que já estava coletado desde o primeiro dia. **Antes de
otimizar uma variável, verificar se ela é a variável.** Quando um número dá
0/7, a explicação raramente é "azar de timing".

(40) v26 (02/08): **"mais recente" não é "mais correto" — critério de
desempate entre fontes divergentes.** Em 01/08 duas fontes deram tabelas
diferentes para o KuPS (30 pts/15 j vs 36 pts/17 j). Desempatei por
recência. Em 02/08 a tabela pós-jogo mostrou que a divergência de 2 jogos
persiste entre as famílias de fonte — ou seja, **recência não resolveu
nada**, só deu uma sensação de critério. As duas eram internamente
coerentes (pontos = 3V+E nas duas), então coerência interna também não
desempata sozinha.

**Regra:** quando duas fontes divergem em dado de base que vai alimentar
Wilson/Dixon-Coles, (a) buscar uma **terceira** fonte e usar a maioria;
(b) não havendo terceira, usar a **mais conservadora** para a tese em
questão (a que enfraquece o lado que eu quero apostar); (c) declarar a
divergência no relatório sempre. **Nunca** desempatar por recência — fonte
defasada e correta bate fonte fresca e errada.

**Impacto do erro de 01/08:** usei "KuPS não perde 16/17 = 94,1%" quando a
outra fonte implicava 14/15 = 93,3%. A conclusão do dia **não muda** — a
reprovação do PE veio do lado Gnistan (Wilson inferior 31%), não do lado
KuPS. Erro não-decisivo, registrado mesmo assim: erro que não mudou o
resultado hoje muda em outro dia.

**Limite honesto adicional descoberto no mesmo dia:** o `WebSearch` devolveu
**placares conflitantes para a mesma partida** (2-1 numa busca, 1-0 em
outra, com lista de gols que não fecha com nenhum dos dois). Para resolução
de resultado, `WebSearch` sozinho **não é fonte confiável** — registrar
apenas o que todas as versões concordam (aqui: "KuPS venceu") e deixar o
resto declarado como lacuna. Nunca escolher um dos placares para "fechar" a
linha do ledger.

(41) v27-v28 (02/08): **o gargalo era vazão, não rigor — e a correção
revelou um viés sistemático no modelo de gols.**

**Diagnóstico.** 362 jogos elegíveis e zero palpites em 01/08 não foi
critério apertado: 361 jogos nunca foram *avaliados*. O funil exigia
pesquisa manual por jogo, o que limita a 2-4 por dia.

**Virada (v27) — `implied_lambdas()`.** O insumo do PE passa a ser a própria
odd. Inverte-se o Dixon-Coles: `1X2 de-vigado → λ implícitos → qualquer
mercado derivado`, sem pesquisar nada sobre os times. Avalia centenas de
jogos em segundos.

Isto **respeita** a decisão v17-b em vez de contrariá-la: em vez de disputar
o 1X2 da casa com λ chutado, aceita o 1X2 como entrada (é o melhor estimador
público) e trabalha nos mercados secundários, menos eficientes (regra 8).

**Três defeitos mortos antes do primeiro uso:** odds corrompidas (overround
186%) viravam PE faixa Alta porque o de-vig POWER normaliza qualquer coisa;
dupla chance inflava a contagem (é aritmética do 1X2, não usa o modelo);
"Over 1.5 a 72%" não é palpite se 72% é a taxa-base — daí o filtro de
distintividade contra a mediana do próprio catálogo do dia.

**Validação (v28) — `scripts/backtest.py`, estudo de má-especificação.** Não
é backtest com dado real (não existe par odd-resultado em escala; o catálogo
de 01/08 não foi persistido). É um mundo simulado **deliberadamente
diferente** do modelo: gols superdispersos, rho variável, 8% de jogos com
choque pós-apito, e viés favorito-azarão na precificação.

Resultado inicial: **superconfiança sistemática.** Faixa Alta afirmava 84,8%
e entregava 72,1% (+12,7pp); BTTS +20,1pp; Over 2.5 +17,3pp; os Under na
direção oposta. Assinatura inequívoca de superdispersão — Poisson subestima
P(0 gols), o que infla exatamente "ambas marcam" e "over".

**Correções aplicadas, ambas justificadas por mecanismo (não por ajuste de
constante):**
1. `gols_dixon_coles(..., forma=)` — marginais binomial-negativa
   (superdispersas) como cenários de robustez. Gols de futebol têm variância
   maior que a média; assumir Poisson puro é erro de modelo, não ruído.
2. `devig_shin()` — de-vig de Shin, que retira **mais margem do azarão** que
   do favorito, corrigindo o viés favorito-azarão que POWER e proporcional
   ignoram.

**Efeito medido:** erro médio absoluto 14,8% → 9,0%; Brier contra a verdade
0,0251 → 0,0094 (**−62%**); ambas as faixas passaram a ficar dentro do
intervalo de Wilson (deixaram de "afirmar mais do que entregam").

**ACHADO QUE VALE MAIS QUE A CORREÇÃO — calibração agregada engana.** Mesmo
no mundo *controle* (quase igual ao modelo), a calibração por faixa parecia
ótima (+1,8pp) enquanto os mercados individuais erravam muito e em direções
**opostas**: Over 2.5 +7,5pp, Under 3.5 −10,9pp. Os erros se cancelavam no
agregado. **Regra nova: calibração por faixa NUNCA é evidência suficiente —
o `pe_ledger` passa a exigir acompanhamento por FAMÍLIA DE MERCADO, e um
viés por mercado acima de 5pp é alerta mesmo com a faixa calibrada.**

**Onde eu parei de propósito.** O viés residual por mercado (Over ~+10pp,
Under ~−8pp) poderia ser zerado empurrando mais os parâmetros de dispersão —
mas os parâmetros do mundo simulado são **invenção minha**, não medição.
Zerar o erro contra a própria simulação seria overfitting a uma fantasia.
O que fica: as correções com justificativa física, e a medição do resto
adiada para dado real. **Isto exige catálogo real persistido + resultados
observados — é a próxima evolução, e ela depende de dado, não de mais
código.**

(42) v29 (03/08, revisão semanal): **canal de dado histórico encontrado — e
o backtest real REVERTEU a "melhoria" de ontem.**

**Descoberta que destrava tudo.** Testando o allowlist de rede durante a
auditoria: `raw.githubusercontent.com` **responde 200**, enquanto
`football-data.co.uk` direto dá 403. Existia um canal aberto para dado
histórico com odds o tempo todo. Baixados e persistidos em `data/backtest/`:
**1916 jogos, 13 ligas, odds reais da Bet365 (B365H/D/A) + placar final
real.**

**Terceira vez a mesma classe de erro** (ver decisões 36 e 39): declarar algo
impossível sem ter testado a alternativa óbvia. **Regra: antes de declarar
bloqueio estrutural, ENUMERAR os canais e testar um por um. "A rede está
bloqueada" é generalização, não diagnóstico.**

**O veredito do dado real (`scripts/backtest_real.py`, N=11.496 pares):**

| Configuração | Viés global | Brier |
|---|---|---|
| v27 — Poisson + POWER | −0,2% | 0,22807 |
| Poisson + **Shin** | −0,1% | **0,22785** |
| v28 — dispersão + Shin | **−4,0%** | 0,23042 |

**A dispersão introduzida ontem (v28) PIOROU o modelo em dado real.** BTTS
foi de +1,6% para **−9,4%**; Over 1.5 de +1,3% para **−6,9%**; quatro
mercados saíram do intervalo de confiança. Poisson puro **já estava
calibrado** (viés de +1,2% a −2,3%).

**Causa do erro:** o "mundo verdadeiro" simulado do v28 tinha superdispersão
porque **eu a coloquei lá**. Corrigir o modelo para bater com a própria
invenção é overfitting a uma fantasia — o `--demo` do `pe_engine` já
avisava sobre circularidade, e eu caí na mesma armadilha um nível acima. A
literatura (Maher 1982: razão variância/média ≈ 1 no futebol moderno) já
apontava isso; li depois de mudar o código.

**Aplicado (Categoria A — reverter regressão própria, com evidência forte):**
cenários de dispersão **removidos de produção**. `gols_dixon_coles(forma=)`
fica no motor (código correto e testado) mas **não entra em produção sem
evidência de dado real**.

**Mantido:** o de-vig de **Shin**, que melhora o Brier e encolhe o viés em
**todos** os mercados, com respaldo publicado (Štrumbelj 2014: estimativas
não-enviesadas na Premier League).

**Mapa do allowlist de rede (medido em 03/08, não suposto).** Aplicando a
própria regra acima, os hosts foram enumerados um a um:

| Host | Estado |
|---|---|
| `raw.githubusercontent.com` | **200** — dado histórico com odds |
| `api.github.com` | **200** (com limite de taxa) |
| `files.pythonhosted.org` | **200** |
| `pypi.org` | **200** |
| `football-data.co.uk`, `api.the-odds-api.com`, `api.football-data.org`, `huggingface.co`, `gist.githubusercontent.com` | túnel recusado |

**Consequência:** dado HISTÓRICO com odds é acessível sempre (via GitHub raw);
odds AO VIVO continuam dependendo exclusivamente do Nimble. Ou seja: backtest
e calibração podem rodar todo dia sem conector nenhum; catálogo do dia, não.

**Lição de processo, mais importante que a correção:** validação contra
simulação própria não é validação — é eco. Toda mudança de modelo agora
exige passar por `backtest_real.py` antes de ir a produção.

(43) v30 (03/08): **causa real da indisponibilidade — conectores DESLIGADOS
NESTA CONVERSA, não ausentes da conta. Corrige a prescrição da decisão 39.**

Mike informou que, do lado dele, os conectores aparecem ativos. Isso separou
duas hipóteses que eu vinha tratando como uma só. `ListConnectors` deu o
veredito:

| Conector | connected | enabledInChat | ferramentas carregam |
|---|---|---|---|
| Canva, Gmail, Calendar, Drive, Kairogen | true | **true** | **sim** |
| **Nimble, Tavily, Exa** | true | **false** | **não** |

**Correlação perfeita, 10/10.** `enabledInChat` prevê exatamente a
disponibilidade real.

**Duas coisas que eu tinha errado:**

1. **Decisão 39 concluiu "conector ausente por configuração da Routine".**
   Isso explica os 0/7 em execução agendada, e segue válido para ELAS. Mas
   eu estendi a conclusão aos turnos interativos, onde a causa é outra e
   muito mais simples: os três estão **autenticados na conta e desligados
   nesta conversa**. Não era oscilação, não era provedor fora do ar, não era
   dispositivo.

2. **Eu havia registrado que "`enabledInChat` diverge da disponibilidade
   real" e mandado usar só `ToolSearch` como teste.** Hoje a correlação é
   perfeita. A regra correta é usar **os dois**: `ListConnectors` diz *por
   quê* (desligado no chat vs desconectado da conta), `ToolSearch` diz *se*
   carrega. Descartar o `ListConnectors` me custou dias — era ele que tinha
   a resposta.

**Ação para o usuário (única coisa que destrava):** nas configurações de
conectores **desta conversa** no claude.ai, ligar **Nimble, Tavily e Exa**.
Não é a configuração de conta (lá já estão conectados) — é o botão por chat.

**Lição de método, quarta ocorrência do mesmo padrão** (ver 36, 39, 42):
descartei uma fonte de diagnóstico por uma conclusão antiga e não a revisitei.
`ListConnectors` estava dando a resposta certa o tempo todo. **Quando um
diagnóstico não fecha, reabrir as fontes descartadas antes de inventar
mecanismo novo.**

(30) v17-c (31/07): **bug de corrupção silenciosa do ledger, encontrado e
corrigido.** As linhas de 30/07 e 31/07 tinham 18 e 19 campos num CSV de 17
colunas — vírgula não escapada dentro do campo `casa` (ex.: `Superbet (odds
reais, mesma casa 3 lados)`). O `DictReader` deslocou todas as colunas
seguintes e o placar do jogo foi parar na coluna `acerto_erro`. O
auto-diagnóstico passava limpo porque só checava presença de coluna no header
e unicidade de id — nunca contagem de campos por linha. Corrigido nos dois
sentidos: linhas reparadas com aspas, e `validate_system.py` agora conta
campos por linha ANTES do DictReader e rejeita chave `None`. Validado com
teste negativo (reintroduzir a corrupção → exit 1; restaurar → limpo).
**Regra:** todo campo de texto livre que possa conter vírgula vai entre
aspas, sempre.

(44) v32 (03/08, pedido do usuário): **regra 8/9 sai do texto e vira
código — mercados de limiar (escanteios/cartões/chutes) calibrados contra
dado real; line-shopping real; 1X2 deixa de ser default por padrão de
código, não só por instrução.**

Motivação: o usuário observou (corretamente, o ledger confirma) que a
execução vinha concentrada em 1X2 apesar da regra 8 sempre ter dito o
contrário, e que o sistema só cotava uma casa (Betano) apesar da regra 9
("line-shopping sempre"). As duas regras já existiam por escrito desde v6/
v14 — nunca tinham virado função, filtro ou dado.

**Fase 0 — dataset.** `data/backtest/*.csv` tinha escanteios/chutes/
cartões em só 5 das 13 ligas (France F1, Germany D1, Italy I1, Scotland
SC0, Spain SP1), 697 jogos de meia temporada 2013 — pouco pra calibrar
com confiança (mesma lição do custo de decidir com dado insuficiente da
decisão 41/v29). `scripts/baixa_dados_backtest.py` expandiu para 15.150
jogos (2000-2013, mesmo canal `raw.githubusercontent.com` da decisão 41,
repositório `jokecamp/FootballData`, que espelha o CSV bruto da
football-data.co.uk sem reformatar). Limitação declarada: dado só vai até
~2013, sem temporada recente (futebol mudou — VAR, pressing).

**Fase 1-2 — modelos testados contra dado real, com veredito por mercado:**

| Mercado | N | Config vencedora | Viés máx. | Veredito |
|---|---|---|---|---|
| Escanteios (total) | 15.137 | Poisson puro | 1,2% | **ACEITO COM RESSALVA** |
| Cartões (total) | 15.148 | Poisson puro | 1,5% | REJEITADO |
| Chutes a gol/SOT (total) | 15.133 | Poisson puro | 1,6% | REJEITADO |

Em TODOS os três, testar dispersão (binomial negativa, `negbin_total()`)
**piorou** Brier e viés — mesma lição da decisão 41/v29, agora replicada
para 3 mercados novos, confirmando que não é específico de gols. Para
cartões, testado também sweep de força de shrinkage (alpha 0,5-20) e
separar histórico por mando casa/fora — nenhum resolveu o viés residual
(o segundo até piorou: menos amostra por bucket custa mais que o sinal
ganho). Chutes rejeitado como esperado — são endógenos ao placar em tempo
real (time perdendo aumenta volume/piora qualidade), sinal que a
heurística de "pace" pré-jogo (EWMA + shrinkage à média da liga,
`betting_model.ewma_shrinkage()`) não capta.

Achado metodológico extra: o teste de sanidade original (walk-forward tem
que perder do "oráculo" que vê a temporada inteira) deu falso alarme em
chutes — o walk-forward honesto bateu o oráculo em Brier. Investigado com
um teste de embaralhamento (`teste_embaralhamento()`): a vantagem some
quando a ordem cronológica é destruída, confirmando sinal real de
recência via EWMA (o oráculo usa média plana, sem peso por recência — não
é um teto matemático garantido), não vazamento de dado futuro.

**Fase 3 — gate de código.** `pe_engine.domina_1x2(candidatos, prob_1x2)`:
compara uma seleção 1X2 hipotética contra os candidatos derivados do
mesmo jogo (gols/BTTS de `avalia_evento()`; escanteios de
`candidato_escanteios()`, que já desconta o viés máximo documentado da
Fase 1 antes de aplicar os pisos Alta/Moderada). Se um derivado supera o
1X2 por folga clara (5pp default), a regra 8 manda preferir o derivado.
Cartões e chutes (rejeitados) não entram como candidatos.

**Fase 4 — line-shopping real.** `scan_odds.parse_mres_blocks()` ganhou
campo `casa`; `scripts/casa_matcher.py` (novo) cruza fixtures entre dumps
de casas diferentes por nome normalizado de time + janela de horário;
`odds_sources.plano_multi_casa(n=3)` devolve N casas distintas a tentar
(não só a primeira que funciona, como a decisão 36/v23 tinha fixado).
Bug real encontrado testando isto: `plano_de_tentativa()` nunca
considerava a ferramenta `nimble_extract` (só `nimble_extract_async`),
então a ÚNICA combinação com sucesso comprovado do sistema (Betano +
`nimble_extract`, driver=vx10, decisão 36/v23) nunca aparecia no plano —
corrigido. **Regra dura preservada sem exceção:** o teste 9.1 usa sempre
odds dos dois lados da MESMA casa; line-shopping só escolhe o melhor
preço de EXECUÇÃO depois que o edge já foi decidido — nunca mistura casas
no cálculo da probabilidade justa. Critério de desempate: se a casa de
melhor preço não tiver o 1X2 completo extraível, usar outra casa para o
edge e só trocar o preço de execução (`casa_matcher.casa_do_edge()`).

**Fora de escopo, declarado:** props de jogador (chutes/desarmes/passes
de um jogador específico) — nenhuma fonte de dado no repo nem histórico,
seria scraping novo do zero. Cartões ajustados por árbitro — os CSVs não
têm coluna de árbitro. Confirmação pós-jogo de escanteios/cartões/chutes
— não há fonte confiável hoje (o único PE de escanteios já tentado, id=2
do pe_ledger, foi arquivado por "contagem exata nunca encontrada"); é um
problema de infraestrutura de dado paralelo ao modelo, não resolvido
aqui.

(45) v33 (03/08, pedido do usuário): **motor de frequência EMPÍRICA
(últimos N jogos) — o método manual do usuário formalizado — e
combinadas com fórmula real.**

Crítica do usuário, correta: o modelo da decisão 44/v32 calibra a FORMA
Poisson contra uma base histórica genérica (2000-2013, 15.150 jogos de 5
ligas europeias) mas nunca olha para os dois times específicos do jogo de
hoje — "base de dados rasa". O processo manual que ele descreveu é mais
direto: pegar os ÚLTIMOS N JOGOS REAIS de cada time, contar em quantos
deles uma estatística passou de um limiar (ex.: "7 de 10 jogos com +8
escanteios"), comparar essa TAXA EMPÍRICA contra a odd oferecida hoje
para esse mesmo limiar — sem lambda, sem Poisson, contagem direta.

**`scripts/forma_recente.py` (novo)** formaliza isso: `taxa_empirica()`
faz a contagem; `avaliar_selecao()` compara contra a odd usando o LIMITE
INFERIOR de Wilson (não a taxa bruta) como número defensável — mesma
filosofia de "sempre o pior cenário" que o motor de PE já usa. Achado
real testando com o próprio exemplo do usuário (8 de 10 jogos, limiar 8):
taxa bruta 80%, mas Wilson inferior cai para 49% — mesmo 9 de 10 (90%
bruto) só dá piso de ~59,6%, e a odd 1,65 do exemplo implica 60,6%. Ou
seja: **o piso de Wilson com N=10 é bem mais rigoroso que ler a taxa bruta
direto** — quase exige acerto perfeito (10/10) pra bater uma odd em torno
de 1,6-1,7 com confiança de 95%. Isso é reportado explicitamente, não
escondido: o sistema deve mostrar taxa bruta E limite inferior sempre,
nunca só o número que favorece a recomendação.

**Coleta:** não é um scraper fixo (formato de site muda, quebra
silencioso) — continua sendo pesquisa ao vivo (WebSearch/Nimble/Tavily,
cascata da regra 6.1: sofascore, whoscored, flashscore, fbref) durante o
aprofundamento de cada jogo, transcrita para
`data/dumps/YYYY-MM-DD-forma-{time-slug}.csv` (schema: data, adversário,
mandante, chutes, chutes_gol, escanteios, cartões, faltas, posse,
resultado — persistido e commitado, mesma disciplina da regra v26).
Ajuste de nível do adversário ("mesmo nível ou nível inferior") fica como
passo qualitativo (checar tabela/classificação), não um número inventado
sem dado para calibrar.

**H2H (item 2):** `taxa_confronto_direto()` reusa a mesma função sobre o
histórico de confronto direto — N tipicamente pequeno, o que já cai
automaticamente num Wilson mais largo (moderado, não alto), exatamente
como o item 2 já prescrevia antes de ter função.

**Combinadas (item 10) — fórmula real, substituindo o texto vago
"imposto SGP":** `betting_model.prob_combinada()` (produto das
probabilidades), `odd_combinada()` (produto das odds), `ev_combinada()`.
Validado com dado real, não suposição: medi a correlação entre limiares
de CATEGORIAS DIFERENTES nos 15.136-15.137 jogos do dataset de backtest
(decisão 44):

| Par de mercados | phi | P(ambos) real vs. independente |
|---|---|---|
| Over 2.5 gols × Over 9.5 escanteios | -0,004 | 27,4% vs 27,5% (razão 0,996) |
| Over 2.5 gols × Over 3.5 cartões | +0,011 | 30,5% vs 30,3% (razão 1,009) |
| Over 9.5 escanteios × Over 3.5 cartões | -0,010 | 34,1% vs 34,3% (razão 0,993) |

Correlação desprezível nos três pares — tratar categorias diferentes
(gols/escanteios/cartões/chutes) como independentes numa combinada é
sustentado por dado real. **Isto NÃO vale para mercados MECANICAMENTE
ligados** (ex.: Over 2.5 gols e Ambas Marcam vêm do MESMO placar) — nunca
multiplicar como independentes, é erro de dupla contagem, não uma
questão de correlação a descontar. Regra prática: as pernas de uma
combinada têm que vir de categorias de estatística diferentes (gols vs.
escanteios vs. cartões vs. chutes), nunca duas leituras do mesmo evento.

**Fora de escopo, declarado (igual à decisão 44):** ainda não há scraper
automático — a coleta de forma recente é pesquisa ao vivo por jogo
aprofundado (2-4/dia), não em escala para o catálogo inteiro. Estatística
de jogador individual cabe no mesmo processo de coleta quando a fonte
trouxer, não tem pipeline próprio.

(46) v34 (03/08, pedido do usuário): **janela de "últimos jogos" deixa de
ser fixa em 10 — vira faixa flexível 3-10; confronto pode seguir com dado
de só um dos times quando ele for o dominante.**

Correção sobre a decisão 45: exigir os 10 jogos completos faria o sistema
descartar um palpite bom só por não achar a pesquisa inteira. `AMOSTRA_MIN
= 3` (`scripts/forma_recente.py`) é o novo piso — abaixo disso o ruído
domina e nem vale calcular; `AMOSTRA_ALVO = 10` continua sendo o que a
pesquisa deve tentar achar, mas 3-9 são amostra válida (o IC de Wilson já
se autorregula: quanto menor N, mais larga a faixa e mais baixo o limite
inferior — não precisa de corte artificial além do piso de 3).

Nova função `avaliar_confronto(taxa_a, taxa_b, odd, a_e_dominante,
b_e_dominante)`: com os dois times disponíveis, usa o mais conservador dos
dois (mesma lógica de convergência do PE); com só UM disponível, só segue
adiante se esse time estiver marcado como o dominante do confronto (times
maiores/melhores costumam impor o próprio padrão de jogo mesmo contra
times menores — julgamento qualitativo do analista, não calculado
sozinho por falta de dado pra calibrar isso automaticamente); sem marcar
dominância, ou sem nenhum dos dois, o veredito é "dado insuficiente" —
nunca finge ter analisado os dois lados quando só teve um.

(47) v35 (04/08, pedido do usuário): **Agent Reach instalado como canal de
último recurso UNIVERSAL — para qualquer busca/página que falhar pelos
métodos normais, em qualquer parte do fluxo diário, não só odds.**

Pedido do usuário: ver instalado e usado o projeto de terceiros
`github.com/Panniantong/agent-reach` para "poder enxergar as paginas das
casas de apostas, busca de estatisticas, busca de analises, busca de
qualquer página de internet bloqueada", como método a mais para odds e
pesquisa em geral, entrando sempre que a ferramenta comum (Nimble/Tavily/
Exa MCP/WebSearch) falhar ou uma página estiver bloqueada — em qualquer
tarefa do fluxo (odds, forma recente, notícias, H2H), não só numa cascata
específica.

Instalação/auditoria: pacote "agent-reach" do PyPI é de OUTRO autor sem
relação — nunca instalar por nome (`pip install agent-reach`); usado
`git clone` do código-fonte real (`github.com/Panniantong/agent-reach`,
`codeload`/zip bloqueados pelo proxy da sessão, `git clone` HTTPS direto
funciona). Lido manualmente `pyproject.toml`, `SECURITY.md` e o mecanismo
real de leitura de página (`agent_reach/channels/web.py`) antes de rodar
qualquer coisa — sem `eval`/`exec`/exfiltração, só chamadas de instalador
legítimas. Escopo instalado: só a infraestrutura base (gh CLI, mcporter +
Exa, leitura de página via Jina Reader). **Não configurado**: cookies de
Twitter/Xueqiu/Xiaohongshu nem API key da Groq — sem relação com odds/
estatísticas/apostas, e extração de cookie de navegador não funciona
neste ambiente headless de qualquer forma.

Mecanismo real (o pacote não tem CLI de "fetch" dedicado, só
setup/install/doctor — a leitura/busca é feita chamando os backends
direto): `curl https://r.jina.ai/<url>` pra ler página; `mcporter call
'exa.web_search_exa(...)'` pra buscar. Encapsulado em
`scripts/agent_reach_fallback.py` (`disponivel()`, `le_pagina()`,
`busca()`) — módulo puro stdlib (`shutil`/`subprocess`/`urllib`), não
depende do venv de instalação nem do pacote Python importado, só do
binário `mcporter` no PATH; testado com `env -i PATH=/usr/bin:/bin`
(ambiente igual ao de uma Routine agendada sem Agent Reach) e continua
funcionando sem erro — `disponivel()` retorna `False`, nada quebra.

**Resultado real do teste (não suposição)**: `le_pagina()` bypassa
bloqueio LEVE de bot/anti-scraping (whoscored.com deu 403 direto, passou
via Jina) mas NÃO bypassa geo-block DURO de casa de apostas (Sportingbet
— o próprio servidor do Jina bate no mesmo bloqueio geográfico) nem
funciona quando o Jina anônimo está com reputação de IP ruim
(football-data.co.uk devolveu erro de autenticação do próprio Jina, não
do alvo) — tratar sempre como "vale tentar", nunca como garantia de
acesso. `busca()` via Exa/mcporter funcionou bem nos dois testes (achou
dado real de forma recente — últimos 10 jogos, escanteios/chutes por
partida — para times de teste).

Uso: registrado em `odds_sources.FERRAMENTAS` só para fins de auditoria/
documentação (não participa do ranking normal de
`plano_de_tentativa()`/`plano_multi_casa()`, que ordena CASA x
ferramenta — Agent Reach não é uma casa, é um canal universal). Import
direto (`from agent_reach_fallback import ...`) de qualquer script/turno
sempre que o método normal falhar numa URL/busca específica — nunca
substitui o método que já funciona. `validate_system.py` (seção 3k)
testa só a lógica pura (sem rede) e trata ausência do módulo/mcporter
como resultado normal, nunca erro bloqueante.

(48) v36 (04/08, pedido do usuário): **causa raiz de "zero palpites com
dezenas de jogos achados" — o parser só extraía 1X2, e o motor de
mercados de limiar (construído desde v32-v34) nunca foi ligado a uma
odd real. Corrigido.**

Usuário reportou o sintoma certo: muitos jogos varridos, zero palpites,
e "só pegamos odds 1x2". Investigação com 3 agentes de exploração em
paralelo (parsing, wiring do fluxo real, histórico de tentativas)
confirmou, com evidência e não suposição:

1. **`scripts/scan_odds.py` só procurava o bloco `"Resultado Final"`**
   e ignorava mercados que já estavam no MESMO dump da listagem, sem
   custo extra de rede — medido no dump real de 04/08: 182 blocos de 1X2
   contra **191 de Total de Gols, 191 de Total de Gols 1ºT, 187 de
   Chance Dupla, 186 de DNB, 61 de BTTS**, todos ignorados.
2. **`pe_engine.candidato_escanteios()`/`domina_1x2()` e
   `betting_model.poisson_total()` nunca eram chamados em produção** —
   só em backtest (contra estatística histórica, sem odd real nenhuma)
   e em self-tests sintéticos. `scripts/generate_report.py` não importa
   nenhum dos dois; o "Fluxo diário" nunca citava um comando concreto
   pra rodá-los, só prosa aspiracional na seção de metodologia.
3. **`scripts/forma_recente.py` nunca recebeu dado real** — 0 de 21
   linhas combinadas do ledger usaram o motor de frequência empírica com
   série jogo-a-jogo real (a única tentativa, 05/08 id=15, esbarrou em
   paywall do footystats e custo do sofascore, já documentado
   honestamente no próprio ledger).

**Consequência, e é matemática, não bug de cálculo:** com só 1X2
disponível — o mercado MAIS eficiente, que a regra v17-b já mandava não
disputar sem dado forte — zero palpites era o resultado ESPERADO do
pipeline, não uma falha isolada.

**Fix aplicado (Tier 1, custo zero de rede extra):**
`scripts/scan_odds.py` ganhou `parse_market_blocks()` (generaliza o
antigo `parse_mres_blocks()`, mantido como wrapper de compatibilidade
com `pe_engine.py`) e `parse_todos_mercados()`, que extrai os 6 mercados
de uma vez do MESMO dump de listagem: 1X2, Total de Gols, Total de Gols
1ºT, Chance Dupla, DNB, BTTS (dict `MERCADOS`, nomes literais
confirmados campo a campo, não adivinhados). Novo modo `--csv-jogos`
persiste o CSV de jogos elegíveis com odds+justo dos 6 mercados —
substitui a montagem manual que existia só como script solto no
scratchpad (mesmo erro de persistência que a decisão v26 já tinha
corrigido pra dumps brutos). `scripts/generate_report.py` (quadro-resumo)
agora mostra Total de Gols e BTTS além do 1X2.

**Fix aplicado (Tier 3, testado ao vivo, sucesso real):** a página
INDIVIDUAL do evento (`betano.bet.br/odds/{slug}/{id}/`, URL vem do
próprio dump da listagem) **tem odds reais de Escanteios e Total de
Cartões** — testado em 04/08 no evento Boca Juniors x Estudiantes de La
Plata: bloco "Escanteios" com **13 linhas de handicap reais (3.5 a
15.5)**, bloco "Total de Cartões" com 1 linha (6.5), ambos com
`selections`/`price` reais, de-vig plausível (overround 7,1% nos dois).
Formato diferente da listagem (1 bloco = VÁRIAS linhas no mesmo array de
`selections`, não 1 bloco por linha) — novo parser dedicado
`parse_mercados_evento()`/`parse_todos_mercados_evento()`. Só vale a
pena rodar nos 2-4 jogos aprofundados (1 `nimble_extract` extra por
jogo, não escalável pros ~80 elegíveis) — ver passo 5.2 do fluxo diário.

**Fix aplicado (Tier 2 — fechar o "nunca é chamado"):** passo 6 do
"Fluxo diário" reescrito de prosa genérica pra comando concreto: testar
CADA mercado com odd real disponível (não só 1X2) via 9.1, e usar
`forma_recente`/`pe_engine.candidato_escanteios()` como PE (9.3) quando
não houver odd real. Os 5 mercados novos da listagem (totais/dupla
chance/DNB/BTTS) não precisam de `pe_engine` — são testáveis pelo MESMO
caminho que 1X2 sempre usou (`devig_power` + `ev_unitario` sobre odd
real), só que agora alimentados de verdade.

**Fora de escopo desta correção (Tier 4, limite conhecido, não
resolvido):** a série jogo-a-jogo real dos últimos 3-10 jogos
(`forma_recente.py`, o método empírico manual do usuário) continua sem
canal de dado barato — footystats.org é pago pros números, sofascore
exigiria ~20 buscas por confronto. Isso não trava os mercados de totais/
BTTS/DNB/escanteios/cartões: para esses, o modelo Poisson (calibrado em
15.150 jogos reais, decisão 44 — escanteios "ACEITO COM RESSALVA", viés
1,2%) já serve de estimador de probabilidade contra a odd real, sem
precisar da série jogo-a-jogo. Cartões/chutes seguem REJEITADOS no
backtest — mesmo com odd real, reportar com confiança baixa (regra 7).
Uma fonte paga de dado jogo-a-jogo fica como decisão de investimento do
usuário, não algo resolvido em código.

Regressão: `validate_system.py` seção 3l testa o parser generalizado com
dado sintético e confere as contagens contra os dois dumps reais já
commitados (`data/dumps/2026-08-04-betano.json` e
`data/dumps/eventos/2026-08-04-betano-boca-estudiantes.json`).

## Casas licenciadas (SPA/MF)

Betano, Bet Nacional, Superbet, Bet365, Sportingbet, KTO, Novibet,
EstrelaBet, Betfair — exclusivamente estas 9. Nunca casa fora da lista,
nunca inventar odd. Segunda-feira reinicia a tabela semanal; o registro
permanente (ledger no git) nunca.

## Formatos aprovados

Over/under e faixas de gols (jogo e por equipe); totais por equipe; DNB;
handicap asiático; dupla chance; escanteios; cartões; faltas; desarmes;
props de jogador; 1X2/dupla chance; combinadas 2-4 pernas; combinadas
correlacionadas; cruzadas de totais. Toda perna passa pela metodologia
(6.2) e teste 9.1 — OU, sem odd confiável, pelo PE (9.3).

## Saída obrigatória (3 partes)

(A) relatório interno com checklist (16), abrindo com QUADRO-RESUMO
CONSOLIDADO; (B) PDF anexado; (C) resumo curto no chat (3-5 linhas).

## Fluxo diário (ordem obrigatória)

1. `git pull --rebase`; `python3 scripts/validate_system.py` (corrigir
   erros, anotar pendências).
2. **Checagem de conectores + contexto (v26, corrigido em v30).** Usar
   **`ListConnectors` E `ToolSearch`** — são complementares, não redundantes:
   `ListConnectors` diz POR QUE (desligado no chat vs desconectado da conta),
   `ToolSearch` diz SE carrega. Se `connected: true` e
   `enabledInChat: false`, a correção é o usuário ligar o conector NESTA
   CONVERSA (decisão 43). Registrar SEMPRE:
   `python3 scripts/connector_log.py --registrar nimble=X tavily=Y exa=Z contexto=trigger nota="..."`
   (usar `contexto=interativo` quando o usuário estiver presente).

   **Saber em que contexto esta execução está rodando muda o que é possível
   — ver decisão (39):**
   - **Sessão agendada (trigger):** conectores MCP não existem (0/7
     historicamente; `allowed_tools` da trigger não tem `mcp__*`). `WebFetch`
     dá 403 em qualquer host. Só `WebSearch` funciona. **Não gastar a execução
     re-checando** — uma checagem registrada basta. Ir direto para o modo
     PE-first (item 9.3) e declarar no relatório que Aposta de Valor está
     **estruturalmente indisponível** nesta execução, com o motivo real
     (conector ausente por configuração da Routine), nunca como "dia fraco".
   - **Turno interativo:** os conectores podem estar no ar. Se estiverem,
     **prioridade máxima** é a varredura ampla do item 4b (método v23) —
     é a única janela em que odds de casa são alcançáveis.

   Se aparecer a primeira linha `trigger,ok` no log, a automação foi
   destravada (usuário anexou os conectores às Routines): avisar e voltar a
   tratar 4b como caminho normal da execução agendada.
3. Resolver filas 14.4/14.5 + resultados de ontem + BUSCAR ODDS DE
   FECHAMENTO de ontem → preencher CLV no ledger (`clv()` do motor).
4. **VARREDURA AMPLA — dois caminhos, nunca "dia fraco" sem ter feito os dois
   (v15 + v17):**

   4a. `python3 scripts/league_calendar.py --prioridade` — lista as ligas em
   temporada HOJE, ordenadas por prioridade (menos eficiente + precificada +
   com dado). Isto define O QUE procurar e roda sem rede. Nunca pular.

   4b. **Com Nimble (só alcançável em turno interativo — decisão 39):**
   `nimble_extract` em `betano.bet.br/sport/futebol/jogos-de-hoje/` com
   **`country="BR"`** (contorna o geobloqueio das casas `.bet.br`) e
   **`driver="vx10"`** (o `vx6` padrão estoura timeout de 60s) — método v23.
   Depois `python3 scripts/scan_odds.py <dump> --casa Betano --data-brt
   AAAA-MM-DD --csv-jogos data/dumps/AAAA-MM-DD-jogos.csv` → catálogo real
   **multi-mercado** (v36: 1X2 + Total de Gols + Total de Gols 1ºT + Chance
   Dupla + DNB + BTTS, todos no MESMO dump, sem custo extra de rede — ver
   decisão v36 abaixo) já gravado no CSV que o passo 9 usa. NUNCA montar
   esse CSV à mão num script solto (foi o próprio erro que a decisão v36
   corrigiu).

   **SEMPRE salvar o dump bruto em `data/dumps/YYYY-MM-DD-casa.json` e
   commitar** (v26). Em 01/08 a extração de 542 eventos existiu só na resposta
   da ferramenta e se perdeu no fim da sessão — no dia seguinte não havia como
   re-testar o parser contra dado real, justamente quando o usuário pediu
   testes repetidos. Extração que não foi persistida não pode ser reauditada.

   4c. **Sem Nimble (caminho v17, obrigatório):** `WebSearch` com
   `allowed_domains=["worldfootball.net","flashscore.com","soccerway.com",
   "espn.com","sofascore.com"]`, em INGLÊS e por NOME DE LIGA da lista 4a.
   O padrão `worldfootball.net/matches-today/dnYYYY-MM-DD/` dá a lista global
   do dia. **Proibido** usar busca em português tipo "jogos de futebol hoje"
   como fonte de descoberta — retorna notícia, e notícia só cobre
   Brasileirão/grandes ligas (falha documentada de 31/07).

   Reportar a tabela de varredura inteira no relatório (cobertura real).
   Escolher 2-4 jogos para pesquisa profunda a partir dela, priorizando ligas
   de eficiência BAIXA precificadas pelas casas BR (regra 8) e diversidade de
   região — não só Brasileirão. Declarar "dia fraco" só é aceitável depois de
   4a + 4c terem sido executados e reportados.
5. Odds reais (método v9 quando disponível; senão WebSearch triangulado).
5.0. **Cascata de extração (v18) — obrigatória antes de desistir de odds:**
   Nimble → Exa (`web_fetch_exa`) → Tavily → WebSearch. Declarar no relatório
   qual nível foi usado. "Nimble fora" NÃO é justificativa para pular para
   WebSearch sem tentar Exa e Tavily.
5.1. **Se os conectores estiverem fora (v17):** não gastar o orçamento
   inteiro tentando achar odds de dois lados que não vão aparecer. Após 2
   tentativas frustradas, realocar o esforço para coleta de estatística dos
   DOIS lados dos jogos melhor ranqueados, visando PE (9.3). Apostas de Valor
   ficam estruturalmente indisponíveis nesses dias — declarar isso.
5.2. **Escanteios/cartões (v36) — só nos 2-4 jogos aprofundados.**
   `nimble_extract` (`country=BR`, `driver=vx10`) na página INDIVIDUAL do
   evento (`betano.bet.br/odds/{slug}/{id}/` — a URL sai do próprio dump
   da listagem, campo `"url"`) traz odds reais de Escanteios (múltiplas
   linhas de handicap) e Total de Cartões, que NÃO existem no dump da
   listagem (passo 4b). `scripts.scan_odds.parse_todos_mercados_evento()`
   extrai as duas. Custo: 1 `nimble_extract` a mais por jogo aprofundado —
   por isso só nos 2-4 do dia, nunca nos ~80 da varredura ampla.
6. Cálculo NUMÉRICO, para CADA mercado com odd real disponível no jogo
   (1X2, Total de Gols, Total de Gols 1ºT, Chance Dupla, DNB, BTTS do
   passo 4b; Escanteios/Cartões do passo 5.2 quando aprofundado) — nunca só
   1X2: lambdas → `poisson_dixon_coles()`/`poisson_total()`; odds →
   `devig_power()`; edge = prob própria - prob justa; `ev_unitario()`; só
   recomendar com folga clara. Sem odd confiável (ou nos mercados fora do
   passo 5.2) → PE (9.3) com `wilson_ci()`, usando
   `forma_recente.avaliar_selecao()`/`avaliar_confronto()` quando houver
   série jogo-a-jogo real (3-10 jogos) coletada, ou
   `pe_engine.candidato_escanteios()` como estimador derivado do 1X2
   quando não houver. Testar robustez com 2-3 cenários de lambda
   (conservador/central/agressivo) — sinal só vale se sobreviver aos três.
   Para mata-mata com placar agregado, usar `win_by_margin()` (v15-b).
7. Append no ledger (commit `"ledger: analise DD/MM"`; push com
   retry/backoff).
8. `python3 scripts/ledger_stats.py` → usar ESTA saída para todos os
   números do relatório.
9. Relatório: `python3 scripts/generate_report.py --data DD/MM` → PDF via
   `SendUserFile`; resumo no chat. Ver "## Geração do PDF" abaixo.

## Histórico de desempenho (estado curto; detalhe no git/ledger)

Ver `data/apostas_ledger.csv` e `data/pe_ledger.csv` para o histórico
completo. Resumo dos agregados permanentes (fonte oficial:
`ledger_stats.py`): 07-12/07 3A/3E/1NV; 13-19/07 2A/3E; 20-26/07 1A/4E.
N=16, taxa 37,5% [Wilson 18,5-61,4%]. P&L (N=5 com odd) -3,33u. CLV médio
(N=1, aprox.) -1,2%. Calibração PE: Alta 2/2 ocorreram; Moderada 0/1 (+1
arquivado).

Observação herdada (sujeita a 8.1): favoritos 1,50-1,70 acertaram 3 de 3
em amostra minúscula; 26/07 dois jogos com odds reais não mostraram edge;
22/07 reds por expressão 1X2 seca (v11).

## Escopo de jogos (GLOBAL)

Varrer o dia no mundo inteiro com dado confiável. Fixtures via WebSearch +
nimble_search/varredura ampla. Referência sazonal: AmSul (Série A/B, Copa
do Brasil, Libertadores, Sul-Americana, Argentina, demais); AmNorte/
Central (MLS, Liga MX Apertura, Leagues Cup ago-set); Europa (verão:
evitar pré-temporada top-5; eliminatórias UEFA válidas; Escandinávia em
temporada); Ásia (J/K-League, CSL); África (só com dado confiável).
Segundas = dia fraco. Feminino/base fora. "Sem seleção hoje" só depois de
varrer E tentar PE. Profundidade em 2-4 jogos > superficialidade em
muitos; cobertura parcial declarada.

## Metodologia (aplicar com rigor)

0. Identidade do confronto: nomes/competição/data-hora Brasília/estádio
   exatos; verificar data real (UTC engana); nunca jogo encerrado;
   amistoso de pré-temporada evitar.
1. Forma EWMA (lambda 0,85-0,90), xG primário (FBref/Understat/SofaScore/
   FotMob), proxy declarado; mínimo 3 jogos.
1.1. Triangulação: xG/proxy + Elo + elenco + coeficientes.
2. H2H 2-3 temporadas; N=3 consistente = Wilson moderado, não alto —
   desde v33 via `forma_recente.taxa_confronto_direto()`.
3. Mando/altitude/clima.
4. GOLS primeira linha: lambdas → `poisson_dixon_coles()` (calcular, não
   estimar). Toda a família over/under/faixas/totais/BTTS.
5/5.1. Contexto (dead rubber, pós-pausa) e descanso/viagem/rotação.
6. Notícias obrigatórias; titularidade confirmada para props.
6.1. Fontes cruzadas (2+): xG globais; Brasil/AmSul (APWin, WindrawWin,
     Academia das Apostas Brasil, ogol, ESPN); árbitros; props. 6.1.1
     Tipsters: só candidatos; dado > narrativa. 6.1.2 Odds:
     WebFetch/Playwright bloqueados; método v9 quando conectores
     habilitados; casa própria > agregador; agregador exige 3+ fontes;
     descartar soma implícita <100%.
6.2. Modelos por mercado (EWMA na entrada): (a) escanteios Poisson
     composto — **IMPLEMENTADO v32**: `betting_model.poisson_total()` +
     `pe_engine.candidato_escanteios()`, testado contra 15.137 jogos reais
     (2000-2013, 5 ligas), ACEITO COM RESSALVA (viés máx. 1,2%, declarar
     sempre que usado — ver decisão 44). **v33: método PRIMÁRIO para
     mercados de limiar passa a ser a frequência EMPÍRICA dos últimos N
     jogos REAIS de cada time** (`forma_recente.taxa_empirica()` — ver
     decisão 45), que reflete o time de hoje, não uma base genérica; o
     Poisson vira cross-check secundário quando a amostra recente for
     muito fina (poucos jogos disponíveis); (b) cartões/faltas aditivo +
     árbitro — testado v32 (`backtest_cartoes.py`, N=15.148), **REJEITADO**
     (viés residual não resolvido por 3 hipóteses testadas; sem dado de
     árbitro disponível); b2) faltas por jogador — sem dado, não tentado;
     (c) finalizações/SOT — testado v32 (`backtest_chutes.py`, N=15.133),
     **REJEITADO** (endógeno ao placar em tempo real, esperado); (d)
     desarmes/defesas — sem dado de jogador, não tentado (ver decisão 44);
     (e) gols = item 4; (f) 1X2 não é default — empate em risco → DNB/AH/DC,
     e desde v32 **código-forçado** via `pe_engine.domina_1x2()` sempre que
     houver candidato derivado aprovado para o mesmo jogo, não só quando há
     risco de empate. Tabela de cobertura obrigatória. Streaks não são
     i.i.d.
7. Confiabilidade por mercado: escanteios/gols boa; 1X2/BTTS líquidos;
   cartões dependem de árbitro; props moderada-baixa.
8. Favoritos melhor precificados; valor tende a ligas menores/props/
   faixas (folga maior); conflito de sinais = não recomendar. Desde v32
   isto é **portão de código** (`pe_engine.domina_1x2()`), não só aviso
   retrospectivo — ver decisão 44.
8.1. Anti-overfitting: critério central só muda com N≥300-500 +
     confirmação do usuário. v5 em diante = mudanças de processo
     autorizadas.
9. Odds: exclusivamente as 9 casas; line-shopping sempre — desde v32 com
   infraestrutura real (`odds_sources.plano_multi_casa()`,
   `scan_odds.py --casa`, `casa_matcher.py`), não só instrução manual; a
   regra 9.1 continua exigindo os dois lados da MESMA casa mesmo quando
   outra casa tem preço melhor (ver decisão 44) — sem confirmação
   → PE.
9.1. NO-VIG: dois lados MESMA casa → `devig_power()` → prob justa; edge
     numérico + EV exibidos; folga clara obrigatória; PE testável =
     retestar e substituir.
9.2. Piso ~30% gated por valor.
9.3. PE: só após tentar 9.1; EWMA + convergência dos DOIS lados
     obrigatória + `wilson_ci()` (limite inferior decide: Alta ≥60% com
     convergência e N≥5/lado ou disparidade muito grande documentada;
     Moderada 40-60%/parcial; Baixa = não reportar); rótulo obrigatório
     ("PALPITE ESTATÍSTICO (sem odd confirmada/testada) — leitura de
     tendência com base em dados reais, NÃO é aposta de valor calculada.
     Confirme a odd disponível antes de decidir."); sem stake; registrar
     no pe_ledger. Quando a odd provável da seleção for <1,40, anotar no
     PE que dificilmente viraria aposta de valor (registro vale para
     calibração).
10. Combinadas: odd FINAL ≥1,40; cada perna no 9.1; correlação declarada
    sem par negativo; prob conjunta real via `betting_model.prob_combinada()`
    /`odd_combinada()`/`ev_combinada()` (v33, decisão 45 — substituiu o
    "imposto SGP" textual por fórmula validada com dado real: categorias
    diferentes ≈ independentes, phi entre -0,010 e +0,011 medido em
    15.136+ jogos reais); até ~4,0; nunca combinar pernas MECANICAMENTE
    ligadas (mesmo placar/mesmo evento — dupla contagem, não correlação).
    PE nunca combina.
13. Relatório: quadro-resumo consolidado primeiro; por jogo forma/
    triangulação/contexto/H2H/notícias/cobertura/odds/valor/PEs; nota
    técnica se conectores indisponíveis. 13.1 nunca prometer dia positivo.
14. Rastreamento: ledger = fonte da verdade; números via
    `ledger_stats.py`. 14.1 checkpoints 50/300-500/1000. 14.2 CLV via
    ledger. 14.3 contrafactual IMEDIATA em todo red. 14.4 fila
    reconfirmação (limite 7). 14.5 fila PE (arquivar após 2-3 tentativas;
    `brier()` quando amostra ≥10-15).
15. Reset semanal (segundas): somar ao permanente; ledger nunca reseta.
16. Checklist: (a) identidade? (b) varredura AMPLA declarada (v15)? (c)
    odds confiáveis? (d) devig numérico com edge exibido? (e) piso 30%?
    (f) gols + DNB/AH? (g) combinadas ok? (h) sem garantias? (i)
    prob+stake? (j) ledger commitado+push? (k) nada inventado? (l)
    divergências? (m) contexto? (n) cobertura? (o) titularidade? (p)
    filas + CLV de ontem? (q) mercados menos eficientes? (r) tipster
    candidato? (s) contrafactual imediata? (t) PE tentado? (u) PE
    completo com rótulo? (v) reteste de PE? (w) quadro-resumo? (x)
    line-shopping? (y) validate_system rodado no início + conectores
    checados? (z) amostra pequena = confiança reduzida?
17. Revisão mensal (1ª segunda): Brier sobre ledger; ROI por
    família/região; CLV médio; dias positivos; 1-3 propostas (confirmação
    do usuário).

## Geração do PDF

`python3 scripts/generate_report.py --data YYYY-MM-DD` (v31, 03/08).
Substitui a referência antiga a `html_to_pdf.js`, que nunca existiu
commitada no repo — cada execução reinventava o HTML a mão no scratchpad
(efêmero, não sobrevive entre sessões/Routines), e por isso a regra do
quadro-resumo (decisão 16, v6) se perdia na prática. O script agora e
persistido e versionado:

- Lê `data/dumps/YYYY-MM-DD-jogos.csv` (todos os jogos varridos no dia —
  confronto/competição/horário/casa/odds 1X2; criar esse CSV a partir da
  varredura ampla do passo 4/4b, mesmo para jogos não aprofundados),
  `data/apostas_ledger.csv` e `data/pe_ledger.csv` (linhas do dia) e a saída
  de `scripts/ledger_stats.py`.
- Gera HTML com QUADRO-RESUMO de todos os jogos primeiro, depois um bloco
  "PALPITES DO DIA" destacado (lista numerada no formato `[Mercado] —
  [Seleção] no jogo [Confronto] (Casa: X, odd: Y)`; se não houver nenhum
  palpite, vira banner "SEM PALPITES HOJE" com motivo por jogo — nunca fica
  implícito), depois cards por jogo (odds/de-vig/edge/status, com a nota de
  auditoria completa em `<details>` secundário) e por fim os números
  oficiais de `ledger_stats.py`.
- Converte para PDF via Chromium headless local (`--print-to-pdf
  --no-pdf-header-footer`, sem cabeçalho/rodapé de URL/data do Chrome) —
  não precisa instalar `playwright`/`puppeteer`. Anexar via `SendUserFile`.
- `--no-pdf` gera só o HTML (mais rápido para iterar visualmente antes de
  gerar o PDF final).

## Resposta no chat

3-5 linhas: destaques, jogos varridos (via varredura ampla), apostas de
valor E PEs, melhor casa, CLV de ontem, status do auto-diagnóstico e
conectores, PDF confirmado; segundas: consolidado + reset.

## Regras obrigatórias de honestidade (não negociáveis)

- NUNCA "garantida"/"certeza"/"lucro garantido"; nunca prometer
  dia/semana positivos; NUNCA apresentar o sistema como infalível ou
  pronto para lucro passivo.
- Taxa de acerto alta não é lucro — só +EV via no-vig.
- PE sempre com rótulo, sem stake, retestado quando odds aparecem.
- Não inventar dados; declarar lacunas; nunca analisar jogo encerrado;
  dado > tipster; descartar soma implícita <100%.
- WebFetch/Playwright bloqueados — não contornar; conectores checados em
  toda execução.
- Sucesso real = CLV + calibração consistentes; ROI 2-8% de longo prazo
  já é muito bom; variância nunca desaparece.
- Nenhum ajuste por resultado de curto prazo; stake fixo até N≥300-500;
  ledger append-only, push nunca forçado.
- Auditoria contrafactual imediata em todo red.
- Cálculos SEMPRE via `betting_model.py`; números de relatório SEMPRE via
  `ledger_stats.py`; auto-diagnóstico SEMPRE no início.
- Nenhum sistema é "à prova de falhas" de verdade — o objetivo real é
  eliminar classes de falha evitáveis, uma de cada vez, com causa raiz
  identificada (v16). Não declarar o sistema blindado/infalível/perfeito
  em nenhuma circunstância, mesmo quando o usuário pedir esse enquadramento.

## Por que este arquivo existe (v16)

Até 30/07, toda esta metodologia vivia embutida no texto do prompt da
trigger agendada, e a única forma de atualizá-la era a ferramenta MCP
`update_trigger` do servidor `Claude_Code_Remote`. Esse servidor ficou
indisponível por mais de 24h em 29-30/07, travando a aplicação de duas
melhorias já prontas e validadas (v15, v15-b) — um ponto único de falha
real, não hipotético.

A partir do v16, o prompt da trigger é um stub curto (ver
`docs/DAILY_TRIGGER_STUB.txt` neste repo) que instrui: `git pull` + ler
este arquivo + seguir o fluxo descrito aqui. Toda atualização de
metodologia futura é feita AQUI, via commit + push (canal que nunca falhou
nesta sessão) — `update_trigger` só é necessário se o próprio stub
precisar mudar (raro, já que ele não contém metodologia).
