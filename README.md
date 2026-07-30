# Sistema de Análise Quantitativa de Apostas Esportivas

Infraestrutura de dados e cálculo do sistema automatizado (Routines diárias/semanais).
Criado na avaliação profunda de 27/07/2026 (v12) para corrigir três falhas estruturais:

1. **Perda de dados**: o histórico vivia em tabelas de texto dentro do prompt da Routine
   e detalhes por aposta foram perdidos na compressão (semanas 07-19/07 só têm agregados).
   → Agora todo palpite vai em `data/*.csv`, versionado em git.
2. **CLV nunca medido**: declarado métrica principal desde v4, nunca calculado uma vez
   (odds de fechamento nunca registradas).
   → O ledger tem colunas `odd_fechamento`/`clv`; a execução do dia seguinte preenche.
3. **Modelos declarados mas não computados**: Poisson/Dixon-Coles/de-vig POWER eram
   descritos e aproximados qualitativamente ("~55-58%").
   → `scripts/betting_model.py` calcula de verdade; validado com asserts.

Um quarto problema, estrutural, foi corrigido em 30/07 (v16): a metodologia inteira
vivia embutida no texto do prompt da Routine, cuja única via de atualização era uma
chamada MCP externa (`update_trigger`) que ficou indisponível por >24h, travando a
aplicação de melhorias já prontas.
→ A metodologia agora vive em `docs/*_METHODOLOGY.md`, versionada em git; a Routine só
contém um stub curto que manda ler o arquivo. Atualizar metodologia é só commit+push.

## Estrutura

- `docs/DAILY_METHODOLOGY.md` — fonte da verdade da análise diária (a Routine só aponta pra cá)
- `docs/WEEKLY_METHODOLOGY.md` — fonte da verdade da revisão semanal
- `docs/*_TRIGGER_STUB.txt` — texto real (curto) das duas Routines agendadas
- `data/apostas_ledger.csv` — todas as apostas de valor (1 linha por aposta, nunca apagar)
- `data/pe_ledger.csv` — palpites estatísticos (rastreamento de calibração, sem stake)
- `scripts/betting_model.py` — Dixon-Coles (incl. distribuição de margens de gols p/
  mata-mata), de-vig POWER, Wilson, EV, Kelly, CLV, Brier
  - `python3 scripts/betting_model.py demo` roda o auto-teste
- `scripts/scan_odds.py` — varredura ampla: extrai TODOS os jogos com 1X2 de um dump de
  listagem da casa (home/hub), não só o jogo pesquisado — evita escolher jogos só por
  manchete de notícia
- `scripts/validate_system.py` — auto-diagnóstico obrigatório no início de toda execução
  (integridade dos ledgers e dos docs de metodologia, regressão do motor de cálculo)
- `scripts/ledger_stats.py` — todo número reportado sai daqui, nunca copiado a mão

## Fluxo diário (Routine 05h BRT)

Ver `docs/DAILY_METHODOLOGY.md` para o fluxo completo e todas as regras. Resumo:

1. `validate_system.py` no início; resolver filas + registrar odds de fechamento de ontem → CLV
2. Varredura AMPLA de jogos (não só manchete) via `scan_odds.py`; escolher 2-4 para aprofundar
3. `betting_model.py`: lambdas → Dixon-Coles → prob. própria; odds → de-vig POWER → prob. justa
4. Edge = prob. própria − prob. justa; só recomendar com folga clara; robustez em 3 cenários
5. Append no ledger, commit e push; `ledger_stats.py` para os números do relatório

Fase atual: validação, stake fixo R$20, N≥300–500 antes de qualquer calibração de critério.
Nenhum sistema garante lucro nem é "à prova de falhas" — o alvo é qualidade de processo,
CLV e calibração, e eliminar classes de falha evitáveis uma de cada vez, com causa raiz.
