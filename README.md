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

## Estrutura

- `data/apostas_ledger.csv` — todas as apostas de valor (1 linha por aposta, nunca apagar)
- `data/pe_ledger.csv` — palpites estatísticos (rastreamento de calibração, sem stake)
- `scripts/betting_model.py` — Dixon-Coles, de-vig POWER, Wilson, EV, Kelly, CLV, Brier
  - `python3 scripts/betting_model.py demo` roda o auto-teste

## Fluxo diário (Routine 05h BRT)

1. Resolver filas (reconfirmação + PE) e **registrar odds de fechamento** dos jogos de ontem → CLV
2. Varredura global de jogos; odds reais via Nimble (página da casa licenciada) quando disponível
3. `betting_model.py`: lambdas → Dixon-Coles → prob. própria; odds → de-vig POWER → prob. justa
4. Edge = prob. própria − prob. justa; só recomendar com folga clara
5. Append no ledger, commit e push

Fase atual: validação, stake fixo R$20, N≥300–500 antes de qualquer calibração de critério.
Nenhum sistema garante lucro; o alvo é qualidade de processo, CLV e calibração.
