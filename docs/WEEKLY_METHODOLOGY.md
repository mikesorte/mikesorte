# Metodologia da Revisão Semanal do Sistema de Apostas

**Versão: alinhada ao DAILY_METHODOLOGY.md v16 (30/07/2026).** Esta é a
fonte da verdade da revisão semanal. A trigger agendada ("Revisão Semanal
do Sistema de Apostas") só contém um prompt curto que manda ler este
arquivo — mesma lógica do `docs/DAILY_METHODOLOGY.md` (ver a seção
"Por que este arquivo existe" lá).

Esta é a REVISÃO SEMANAL do sistema de análise de apostas esportivas —
execução automática de melhoria contínua com mandato de AUTO-CORREÇÃO,
AUTO-OTIMIZAÇÃO, AUTO-EVOLUÇÃO, AUTO-ALIMENTAÇÃO, rodando na mesma sessão
onde a tarefa diária dispara todo dia. Execute o ciclo completo de forma
autônoma. Objetivo: elevar continuamente a qualidade em TODAS as
dimensões — métodos, formas de cálculo, modelos por mercado, cobertura de
mercados, fontes, formatos de aposta, qualidade dos relatórios — indo
ALÉM do pendente, sempre com base empírica publicada. O que NUNCA muda:
honestidade sobre variância, taxa de acerto alta não é lucro (só
valor/+EV nas apostas de valor; PE mede calibração, não lucro),
anti-overfitting, e as decisões do usuário registradas em
`docs/DAILY_METHODOLOGY.md`.

## Ciclo semanal (executar todos os passos)

**Passo 1 — Estado atual**: `git pull --rebase`; ler
`docs/DAILY_METHODOLOGY.md` por completo e confirmar que reflete a versão
mais recente (se algo tiver regredido, é regressão — restaurar a partir
do histórico git). Reler os relatórios diários da semana nesta conversa.

**Passo 2 — Auditoria de processo**: (a) falhas de processo (14.3) e
repetições; (b) itens de checklist (16 da diária) pulados; (c) fontes
indisponíveis/divergentes recorrentes — checar especificamente o status
do bloqueio de WebFetch/Playwright (persiste, é esperado), a
disponibilidade de Nimble/Tavily/Exa no chat (podem oscilar — checar
`ListConnectors`), e a disponibilidade do servidor `Claude_Code_Remote`
(usado só para o stub da trigger, não mais para metodologia — ver v16);
(d) instruções mal aplicadas ou ineficiências de processo (ex.:
relatórios/PDFs redundantes no mesmo dia); (e) cobertura e distribuição
por família de mercado (apostas de valor E PEs separadamente), incluindo
se a VARREDURA AMPLA (v15, `scan_odds.py`) rodou quando os conectores
estavam disponíveis; (f) odd final ≥1,40 com combinadas formadas
corretamente; (g) teste no-vig POWER aplicado com edge exibido em toda
aposta de valor; (h) CLV consultado e reportado nas apostas de valor
abertas; (i) calibração parcial (checkpoint, N<300 = só contexto); (j)
PEs da semana: quantos emitidos? Quantos com convergência dos dois lados
vs baixa confiança corretamente não-reportada? Algum PE precisou ser
RETESTADO com odds reais que apareceram depois — foi retestado
corretamente? Resolver fila 14.5 (incl. arquivar itens sem verificação
após 2-3 tentativas); (k) frequência de dias positivos vs negativos
(apostas de valor); (l) AUDITORIA CONTRAFACTUAL consolidada da semana —
localizar pendências registradas em revisões anteriores; (m) sequências
vs variância esperada (8.1).

**Passo 3 — Pesquisa dirigida + AUTO-EVOLUÇÃO (mandato permanente)**: 2-4
buscas DIRIGIDAS às fraquezas do Passo 2. ALÉM disso, 1-3 buscas de
auto-evolução em rodízio, priorizando o que ainda não foi coberto: (1)
validar/refinar Poisson composto para escanteios; (2) lambda EWMA (sem
mudança desde a revisão de 26/07; próxima rodada só se houver fonte nova
específica de futebol); (3) formalizar EWMA+Poisson/regressão para
finalizações/desarmes (ainda genéricos); (4) formas de cálculo
(correlação de pernas, staking pós-validação); (5) métricas emergentes;
(6) novas fontes/APIs (além de Nimble/Tavily/Exa); (7) mercados novos; (8)
formatos de aposta profissionais; (9) validação/backtesting (CLV médio
real, Brier aplicado quando houver amostra de PE ≥10-15); (10) melhorias
técnicas ao método Nimble (ex.: parâmetros de renderização completa para
páginas de agregador com JS ofuscado). SEMPRE exigir base empírica
publicada.

**Passo 4 — Classificar e aplicar**:

- **Categoria A (aplicar sozinho)**: correções de processo;
  AUTO-ALIMENTAÇÃO (melhores fontes; refinar fórmula/racional de um
  modelo JÁ aprovado com evidência publicada, incluindo os modelos de
  PE); melhorar formato de relatório/PDF; consolidar texto (o
  `DAILY_METHODOLOGY.md` não deve inchar indefinidamente — resumir
  decisões antigas quando o racional completo já estiver consolidado);
  atualizar histórico embutido (apostas de valor E fila de PE) ao estado
  mais recente sem regredir o permanente; resolver PEs pendentes com
  resultado real (14.5), retestar com odds reais quando disponíveis, e
  consolidar taxa de acerto de PE por faixa de confiança assim que houver
  amostra suficiente; mudanças já confirmadas pelo usuário no chat. Para
  aplicar: editar `docs/DAILY_METHODOLOGY.md` diretamente (commit + push
  — não depende mais de `update_trigger`, ver v16). Confirmar
  imediatamente com `git log`/`git show` após alterar.

- **Categoria B (PROPOR, nunca aplicar sozinho)**: mudança de critério
  central não decidido pelo usuário — piso de odd, mudar o teste de
  valor/de-vig, dimensionamento de stake além do já decidido, REMOÇÃO de
  mercados/casas/formatos, ADIÇÃO de casa além das 9, fontes com
  credencial, mudar os limiares do PE (corte de confiança, lambda do
  EWMA, permitir PE de um lado só) sem evidência nova forte, qualquer
  mudança motivada por resultado de curto prazo. Propor numerado com
  evidência+fonte; aplicar só após confirmação.

**Passo 5 — Tamanho e coerência**: arquivo maior não é melhor — consolidar
(Cat A). Sem falha na auditoria e sem evidência nova: "nenhuma mudança
esta semana", sem inventar.

**Passo 6 — Relatório no chat (único entregável)**: (a) auditoria da
semana incl. distribuição por família, ROI/acerto por família, CLV médio,
frequência de dias positivos vs negativos (apostas de valor); taxa de
acerto de PE por família e faixa de confiança (mesmo com amostra pequena
— contexto, não conclusão); consolidado de auditorias contrafactuais
(incl. pendências); (b) pesquisas feitas + fontes; (c) Categoria A
aplicada (ou "nenhuma"); (d) propostas Categoria B (ou "nenhuma"); (e) 1
linha honesta: melhorias de processo, mais mercados, melhor seleção de
expressão, PE e o pipeline Nimble aumentam as chances de informação útil
e de valor, mas NÃO alteram a variância do futebol nem garantem
dias/semanas positivos, e PE NUNCA é garantia de acerto. Sem PDF nesta
revisão.

## Regras permanentes

- NUNCA prometer/medir/celebrar "redução de erros de resultado" nem "dia
  sempre positivo" — o alvo é qualidade de processo e valor (+EV) de
  longo prazo (apostas) e calibração (PE).
- NUNCA apagar/reescrever o histórico permanente — só cresce.
- NUNCA alterar nome/modo de disparo da diária, nem desativá-la, nem
  regredir decisões históricas.
- NUNCA aplicar Categoria B sem confirmação explícita do usuário.
- Auto-evolução NUNCA justifica afrouxar critérios, inflar confiança,
  baixar o piso do teste de valor, OU relaxar as regras do PE
  (convergência dos dois lados, Wilson, rótulo obrigatório) só para gerar
  mais PEs ou mais apostas de valor. "Mais seleções" é resultado de achar
  mais dados/odds reais, nunca uma cota.
- PE nunca vira aposta de valor sem passar pelo teste 9.1 completo se uma
  odd real aparecer depois — deve ser retestado ativamente, não só
  passivamente esperado.
- Se a diária não existir no `list_triggers`: recriar imediatamente
  apontando para `docs/DAILY_METHODOLOGY.md` (prioridade máxima).
- Este arquivo NUNCA deve regredir a uma versão anterior de si mesmo —
  cada execução deve manter as decisões em vigor descritas em
  `docs/DAILY_METHODOLOGY.md` atualizadas, e não duplicar aqui o que já
  está lá (este arquivo é sobre o PROCESSO da revisão semanal, não sobre
  a metodologia diária em si).
- Nenhum sistema é "à prova de falhas" de verdade — mesma regra do
  `DAILY_METHODOLOGY.md` (v16): eliminar classes de falha evitáveis, uma
  de cada vez, com causa raiz identificada.
