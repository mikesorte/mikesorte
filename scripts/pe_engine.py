#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Motor de Palpites Estatisticos em escala (v27).

O PROBLEMA QUE ISTO RESOLVE
---------------------------
Em 01/08 o catalogo trouxe 362 jogos elegiveis e o dia terminou com ZERO
palpites. Nao foi rigor excessivo: foi VAZAO. O funil exigia pesquisa manual
por jogo (tabela, forma, H2H), o que limita a 2-4 jogos por dia. Os outros
358 nunca foram avaliados - nao foram reprovados, foram ignorados.

A virada (v27): o insumo do PE passa a ser a PROPRIA ODD, que ja vem no
catalogo, em vez de pesquisa externa. Caminho:

    odds 1X2 -> de-vig -> probabilidades justas -> INVERSAO Dixon-Coles
    -> lambdas implicitos -> qualquer mercado derivado (over/under, BTTS,
       dupla chance, placar)

Isso avalia 362 jogos em segundos, sem pesquisar nada sobre os times.

O QUE ISTO E E O QUE NAO E
--------------------------
E um enunciado de PROBABILIDADE ancorado no preco da propria casa. Nao e
edge. As probabilidades derivadas herdam a informacao da casa mais o erro
do modelo de gols - por construcao nao ha vantagem sobre o 1X2 de origem
(decisao v17-b: nao competir onde a casa e mais forte).

Uso legitimo:
  (a) PE - dizer "este desfecho tem X% pelo proprio mercado", com o rigor
      de robustez descrito abaixo;
  (b) TRIAGEM DE VALOR - onde a casa tambem precifica o mercado derivado,
      comparar o derivado contra o preco dela. Divergencia grande em
      mercado SECUNDARIO (menos eficiente, regra 8) e candidato a
      investigar - nunca aposta automatica.

Uso ilegitimo, travado no codigo: reapostar no proprio 1X2 que serviu de
entrada. Isso e circular e o motor recusa.

ROBUSTEZ (por que nao basta a probabilidade ser alta)
-----------------------------------------------------
Uma probabilidade derivada depende de rho e do metodo de de-vig. Se o
palpite so sobrevive com um rho especifico, ele e artefato do modelo, nao
propriedade do jogo. Todo candidato e recalculado em varios cenarios e so
passa quem se sustenta no PIOR deles. E a mesma disciplina dos "3 cenarios"
que a metodologia ja exigia na analise manual - agora automatica.

Uso:
    python3 scripts/pe_engine.py <dump.json>        # catalogo real
    python3 scripts/pe_engine.py --demo             # catalogo sintetico
    python3 scripts/pe_engine.py <dump.json> --json # saida para pipeline
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from betting_model import (poisson_dixon_coles, gols_dixon_coles,
                           implied_lambdas, devig_power, devig_shin,
                           InversaoFalhou, poisson_total, ewma_shrinkage)
import scan_odds

# Cenarios de robustez: (rho, forma_dispersao). forma None = Poisson puro.
#
# HISTORICO IMPORTANTE - NAO REINTRODUZIR DISPERSAO SEM DADO REAL (v29)
# ---------------------------------------------------------------------
# Em 02/08 (v28) eu adicionei cenarios superdispersos (forma 8.0 a 2.5)
# porque um estudo de MA-ESPECIFICACAO SIMULADO mostrava vies grande com
# Poisson puro (Over 2.5 +17pp, BTTS +20pp). Reportei "Brier -64%".
#
# Em 03/08, com 1916 jogos REAIS (odds Bet365 + placar final), o veredito se
# inverteu: a dispersao PIOROU o Brier em 1.0% e jogou 4 mercados para fora
# do intervalo de confianca - BTTS de +1.6% para -9.4%, Over 1.5 de +1.3%
# para -6.9%. Poisson puro ja estava calibrado no dado real (vies de +1.2%
# a -2.3%).
#
# O erro: o "mundo verdadeiro" simulado tinha superdispersao porque EU a
# coloquei la. Corrigir o modelo para bater com a minha propria invencao e
# overfitting a fantasia. A literatura (Maher 1982) ja apontava razao
# variancia/media perto de 1 no futebol moderno - eu so fui ler depois.
#
# Fica: rho variavel (efeito pequeno e bem estabelecido) + variacao de
# metodo de de-vig. gols_dixon_coles(forma=) continua no motor porque e
# codigo correto e testado, mas NAO entra em producao sem evidencia de
# dado real.
CENARIOS = (
    (-0.18, None),   # rho forte
    (-0.11, None),   # rho central
    (-0.04, None),   # rho fraco
)

# Pisos por faixa, aplicados ao PIOR cenario. Calibrados para serem
# DEFENSAVEIS, nao generosos: a faixa Alta precisa ser algo que, errando,
# constrange - senao a calibracao nao mede nada.
PISO_ALTA = 0.75
PISO_MODERADA = 0.65

# Overround aceitavel num 1X2 de casa licenciada. Fora disso o dado esta
# corrompido ou nao e um 1X2 de verdade. SEM ESTE PORTAO o motor aceitava
# [1.05, 1.05, 1.05] (overround de 186%) e cuspia PE faixa Alta - o de-vig
# POWER normaliza qualquer coisa, entao ele nunca reclama sozinho. Falha
# encontrada na primeira execucao do motor, antes de qualquer uso real.
OVERROUND_MIN, OVERROUND_MAX = 0.005, 0.25

# MERCADOS QUE NAO SAO PE (v27)
# -----------------------------
# Dupla chance sai por ARITMETICA direta do 1X2 ja de-vigado: 1X = P(H)+P(D).
# Nao passa pelo modelo de gols, nao usa os lambdas, nao acrescenta nenhuma
# informacao que nao esteja visivel na propria odd. Emitir "dupla chance do
# favorito, 79%" como palpite seria inflar a contagem com trivialidade -
# geraria dezenas de "palpites" por dia, todos verdadeiros e todos inuteis.
# Volume falso e pior que volume zero: contamina a calibracao com acertos
# faceis e faz o sistema parecer melhor do que e.
# Ficam como CONTEXTO no relatorio, nunca como candidato.
MERCADOS_CONTEXTO = ("Dupla chance 1X", "Dupla chance X2", "Dupla chance 12")


def devig_proporcional(odds):
    imps = [1.0 / o for o in odds]
    s = sum(imps)
    if s <= 1.0:
        raise ValueError("odds sem margem - dado de agregador (regra v8)")
    return [i / s for i in imps]


def mercados_derivados(lh, la, rho, forma=None):
    """Todos os mercados que saem dos lambdas, com nome legivel.

    'forma' None = Poisson puro; finito = superdisperso (ver v28).
    """
    d = gols_dixon_coles(lh, la, rho=rho, forma=forma)
    return {
        "Dupla chance 1X": d["p_home"] + d["p_draw"],
        "Dupla chance X2": d["p_draw"] + d["p_away"],
        "Dupla chance 12": d["p_home"] + d["p_away"],
        "Over 1.5": d["over_1.5"],
        "Under 3.5": d["under_3.5"],
        "Over 2.5": d["over_2.5"],
        "Under 2.5": d["under_2.5"],
        "Ambas marcam (BTTS)": d["btts"],
        "Ambas NAO marcam": 1 - d["btts"],
    }


# GATE DE PRIORIDADE 1X2 vs DERIVADOS (v32, Fase 3)
# --------------------------------------------------
# A regra 8/9 sempre disse "nao competir no 1X2 quando ha mercado menos
# eficiente melhor" - mas isso nunca foi um filtro de codigo, so um aviso
# retrospectivo em ledger_stats.py (conta DEPOIS do fato, nao impede
# recomendar 1X2). O achado concreto que motivou isto: nos ultimos dias
# testados (ver docs/DAILY_METHODOLOGY.md v31, linha ~208-219) 50%+ das
# linhas do ledger eram 1X2 - o proprio sistema documentou que estava
# ignorando a propria regra.
#
# domina_1x2() transforma a regra em portao: roda ANTES de prometer 1X2
# como o palpite do dia, comparando contra os candidatos derivados JA
# calculados para o mesmo jogo (goals/BTTS de avalia_evento(); escanteios
# de candidato_escanteios() quando houver historico de time disponivel -
# cartoes e chutes NAO entram aqui, foram REJEITADOS no backtest real,
# ver scripts/backtest_cartoes.py e scripts/backtest_chutes.py).
VIES_MAX_ESCANTEIOS = 0.012  # pior vies documentado no backtest (Fase 1, ACEITO COM RESSALVA)


def candidato_escanteios(historico_casa, historico_fora, media_liga,
                         linhas=(8.5, 9.5, 10.5), alpha=3.0):
    """Gera candidatos de escanteios no MESMO formato dos candidatos de
    avalia_evento(), usando o modelo ACEITO COM RESSALVA na Fase 1
    (scripts/backtest_escanteios.py, N=15137, Poisson puro, vies max 1.2%).

    Exige o CHAMADOR ja ter o historico recente (jogos ANTERIORES ao de
    hoje - nunca incluir o proprio jogo, mesma regra do walk-forward do
    backtest) de escanteios dos dois times envolvidos. Esta funcao nao
    busca dado nenhum, so calcula - buscar o historico (pesquisa por time,
    mesma natureza do que ja e feito hoje para lambdas de gols) e
    responsabilidade de quem chama.

    A probabilidade reportada ja vem DESCONTADA do vies maximo documentado
    (VIES_MAX_ESCANTEIOS) - a mesma filosofia de "sempre reportar o numero
    mais defensavel" que os cenarios de gols usam com o pior cenario.
    """
    lam_casa = ewma_shrinkage(historico_casa, media_liga, alpha=alpha)
    lam_fora = ewma_shrinkage(historico_fora, media_liga, alpha=alpha)
    lam_total = (lam_casa + lam_fora) / 2.0
    dist = poisson_total(lam_total, linhas=linhas)

    candidatos = []
    for linha in linhas:
        for direcao, prob in (("Over", dist[f"over_{linha}"]), ("Under", dist[f"under_{linha}"])):
            prob_conservadora = max(0.0, prob - VIES_MAX_ESCANTEIOS)
            if prob_conservadora >= PISO_ALTA:
                faixa = "Alta"
            elif prob_conservadora >= PISO_MODERADA:
                faixa = "Moderada"
            else:
                continue
            candidatos.append({
                "mercado": f"Escanteios {direcao} {linha}",
                "prob_pior_cenario": prob_conservadora,
                "prob_melhor_cenario": prob,
                "amplitude": prob - prob_conservadora,
                "faixa": faixa,
                "odd_justa": 1.0 / prob_conservadora,
                "lambdas": (lam_casa, lam_fora),
                "ressalva": ("modelo ACEITO COM RESSALVA (Fase 1, vies max "
                             f"{VIES_MAX_ESCANTEIOS:.1%} documentado) - probabilidade "
                             "ja ajustada conservadoramente"),
            })
    candidatos.sort(key=lambda c: -c["prob_pior_cenario"])
    return candidatos


def domina_1x2(candidatos_derivados, prob_1x2, margem_dominancia=0.05):
    """Ha um candidato derivado (mercado menos eficiente, regra 8) que
    dominaria uma selecao de 1X2 com probabilidade propria 'prob_1x2' (a
    probabilidade que sustenta o edge que se pretende recomendar como
    Aposta de Valor)?

    'candidatos_derivados': lista de dicts no formato de avalia_evento()/
    candidato_escanteios() PARA O MESMO JOGO - tipicamente
    avalia_evento(ev)[0] + candidato_escanteios(...) concatenados, quando
    houver historico de escanteios disponivel.

    margem_dominancia: 1X2 so cede lugar se o derivado for melhor por uma
    folga clara (default 5pp) - nao trocar por uma diferenca de ruido.

    Retorna (dominado: bool, melhor_candidato_ou_None). Uso pretendido: no
    fluxo diario, ANTES de declarar um 1X2 como Aposta de Valor do dia,
    chamar isto com os candidatos derivados do mesmo jogo. Se dominado,
    reportar o derivado no lugar (ou junto) - nunca declarar o 1X2 sozinho
    como se fosse a unica opcao vista.
    """
    melhores = [c for c in candidatos_derivados
                if c["prob_pior_cenario"] >= prob_1x2 + margem_dominancia]
    if not melhores:
        return False, None
    return True, max(melhores, key=lambda c: c["prob_pior_cenario"])


def avalia_evento(ev, so_probabilidades=False):
    """Devolve (candidatos, motivo_descarte). candidatos e lista de dicts.

    Um candidato so nasce se sobreviver a TODOS os cenarios - o valor
    reportado e sempre o do PIOR cenario, nunca o melhor nem a media.
    Reportar o melhor cenario seria escolher o numero que agrada.

    so_probabilidades=True devolve {mercado: prob_pior_cenario} de TODOS os
    mercados, sem aplicar piso - usado para calcular a mediana do catalogo.
    """
    odds = ev.get("odds")
    if not odds or len(odds) != 3:
        return [], "sem 1X2 completo"
    if any((not isinstance(o, (int, float))) or o <= 1.0 for o in odds):
        return [], "odd invalida (<=1.0 ou nao numerica)"
    overround = sum(1.0 / o for o in odds) - 1.0
    if not (OVERROUND_MIN <= overround <= OVERROUND_MAX):
        return [], f"overround fora da faixa ({overround:.1%})"
    try:
        justo_power = devig_power(odds)
    except Exception as e:
        return [], f"de-vig falhou ({type(e).__name__})"

    # cenarios: (rho, forma, probabilidades justas). Inclui os dois metodos
    # de de-vig como fonte extra de variacao.
    variantes = [(rho, forma, justo_power) for rho, forma in CENARIOS]
    # de-vigs alternativos como fonte extra de variacao. Shin entrou em v28
    # por causa do vies favorito-azarao (ver betting_model.devig_shin).
    # Shin validado em dado real (v29): melhora o Brier e encolhe o vies em
    # TODOS os mercados, e a literatura (Strumbelj 2014) reporta estimativas
    # nao-enviesadas na Premier League. Ganho pequeno mas consistente.
    for alt in (devig_proporcional, devig_shin):
        try:
            pa = alt(odds)
        except Exception:
            continue
        variantes.append((-0.11, None, pa))

    por_mercado = {}
    lambdas_ref = None
    for rho, forma, justo in variantes:
        try:
            # a INVERSAO usa sempre Poisson+rho: e o modelo com que a casa
            # precifica o 1X2. A dispersao entra so na PROJECAO dos mercados
            # derivados, que e onde o erro de Poisson aparece.
            lh, la = implied_lambdas(*justo, rho=rho)
        except InversaoFalhou:
            return [], "inversao falhou (dado implausivel)"
        if lambdas_ref is None:
            lambdas_ref = (lh, la)
        for nome, p in mercados_derivados(lh, la, rho, forma).items():
            por_mercado.setdefault(nome, []).append(p)

    if so_probabilidades:
        return ({n: min(v) for n, v in por_mercado.items()
                 if n not in MERCADOS_CONTEXTO}, None)

    candidatos, contexto = [], {}
    for nome, valores in por_mercado.items():
        pior, melhor = min(valores), max(valores)
        if nome in MERCADOS_CONTEXTO:
            contexto[nome] = pior
            continue
        if pior >= PISO_ALTA:
            faixa = "Alta"
        elif pior >= PISO_MODERADA:
            faixa = "Moderada"
        else:
            continue
        candidatos.append({
            "mercado": nome,
            "prob_pior_cenario": pior,
            "prob_melhor_cenario": melhor,
            "amplitude": melhor - pior,
            "faixa": faixa,
            "odd_justa": 1.0 / pior,
            "lambdas": lambdas_ref,
            "contexto_dc": contexto,
        })
    candidatos.sort(key=lambda c: -c["prob_pior_cenario"])
    return candidatos, None


def _mediana(xs):
    ys = sorted(xs)
    n = len(ys)
    if not n:
        return None
    return ys[n // 2] if n % 2 else (ys[n // 2 - 1] + ys[n // 2]) / 2.0


def baselines(eventos):
    """Distribuicao de cada mercado no PROPRIO catalogo do dia.

    POR QUE (v27): "Over 1.5 com 72%" nao e palpite se 72% e o valor tipico
    de Over 1.5 em qualquer jogo de futebol - e a taxa-base da populacao,
    verdadeira e sem informacao. Emitir isso em escala encheria o ledger de
    acertos faceis e faria a calibracao parecer boa sem que o sistema
    soubesse de nada.

    Calcular a mediana do proprio catalogo torna o corte auto-calibravel: o
    que vale e o DESVIO em relacao ao que e normal hoje, nao o nivel
    absoluto. Um dia de jogos truncados sobe a mediana de Under e o motor se
    ajusta sozinho, sem constante chumbada.
    """
    acumulado = {}
    for ev in eventos:
        cands, motivo = avalia_evento(ev, so_probabilidades=True)
        if motivo:
            continue
        for nome, p in cands.items():
            acumulado.setdefault(nome, []).append(p)
    return {nome: _mediana(v) for nome, v in acumulado.items() if len(v) >= 8}


def processa(eventos, desvio_minimo=0.08):
    """desvio_minimo: quanto o mercado precisa se afastar da mediana do
    catalogo para contar como informativo. 8pp e deliberadamente exigente -
    prefiro poucos palpites que significam algo a muitos que nao significam."""
    base = baselines(eventos)
    saida, descartes = [], {}
    for ev in eventos:
        cands, motivo = avalia_evento(ev)
        if motivo:
            descartes[motivo] = descartes.get(motivo, 0) + 1
            continue
        if base:
            distintos = []
            for c in cands:
                med = base.get(c["mercado"])
                if med is None:
                    continue
                c["mediana_catalogo"] = med
                c["desvio"] = c["prob_pior_cenario"] - med
                if c["desvio"] >= desvio_minimo:
                    distintos.append(c)
            if cands and not distintos:
                descartes["atinge o piso mas nao e distintivo (taxa-base)"] = \
                    descartes.get("atinge o piso mas nao e distintivo (taxa-base)", 0) + 1
            cands = distintos
        if not cands:
            descartes["nenhum mercado atinge o piso"] = \
                descartes.get("nenhum mercado atinge o piso", 0) + 1
            continue
        saida.append({
            "jogo": ev.get("participants") or "?",
            "competicao": ev.get("competition") or "?",
            "start_time": ev.get("start_time"),
            "odds_1x2": ev.get("odds"),
            "candidatos": cands,
        })
    return saida, descartes


def catalogo_demo(n=362, seed=11):
    """Catalogo sintetico do TAMANHO REAL observado em 01/08 (362 elegiveis).

    Gerado a partir de lambdas plausiveis -> probabilidades verdadeiras ->
    odds com margem de casa. Assim o catalogo tem a mesma ESTRUTURA de um
    catalogo real (mistura de jogos truncados, abertos, parelhos e decididos)
    em vez de uma lista de perfis escolhidos a mao, que enviesaria a medicao
    de vazao para o numero que eu quisesse ver.

    Inclui de proposito alguns registros corrompidos: catalogo real tem.
    """
    import random
    rnd = random.Random(seed)
    eventos = []
    for i in range(n):
        # forca das equipes e ritmo do jogo, em faixas de futebol de verdade
        total = rnd.gauss(2.65, 0.55)
        total = min(max(total, 1.1), 4.6)
        diff = rnd.gauss(0.28, 0.85)          # leve vantagem media de mando
        diff = min(max(diff, -(total - 0.4)), total - 0.4)
        lh, la = (total + diff) / 2, (total - diff) / 2
        d = poisson_dixon_coles(lh, la)
        margem = rnd.uniform(0.04, 0.09)      # overround tipico de casa
        probs = [d["p_home"], d["p_draw"], d["p_away"]]
        odds = [round(1.0 / (p * (1 + margem)), 2) for p in probs]
        eventos.append({"participants": f"Time{2*i} - Time{2*i+1}",
                        "competition": f"Liga {i % 17}",
                        "start_time": None, "odds": odds})
    eventos.append({"participants": "Corrompido A - Corrompido B",
                    "competition": "Demo", "start_time": None,
                    "odds": [1.05, 1.05, 1.05]})
    eventos.append({"participants": "Incompleto A - Incompleto B",
                    "competition": "Demo", "start_time": None,
                    "odds": [2.0, 3.0]})
    return eventos


AVISO_CIRCULARIDADE = """
AVISO SOBRE ESTE NUMERO (leia antes de acreditar nele)
------------------------------------------------------
O catalogo --demo e gerado A PARTIR do proprio Dixon-Coles que o motor usa
para inverter. Ou seja: as odds sinteticas sao DC-consistentes por
construcao, e a inversao recupera os lambdas com erro ~1e-9. Num catalogo
REAL isso nao acontece - a casa precifica over/under e BTTS com informacao
propria (escalacao, lesao, clima, fluxo de dinheiro) que NAO esta contida
no 1X2, entao os derivados vao divergir do preco real dela.

Portanto a taxa de aproveitamento acima mede o ENCANAMENTO (o motor roda em
escala, os portoes de qualidade barram lixo, o filtro de distintividade
funciona), NAO a acuracia. A acuracia so pode ser medida com catalogo real e
resultado observado, acumulando no pe_ledger ao longo de semanas.

Tratar 46% sintetico como "46% dos jogos viram palpite bom" seria
exatamente o auto-engano que a metodologia proibe.
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dump_file", nargs="?")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--max-por-jogo", type=int, default=2,
                    help="quantos mercados reportar por jogo (padrao 2)")
    args = ap.parse_args()

    if args.demo:
        eventos = catalogo_demo()
    elif args.dump_file:
        with open(args.dump_file, encoding="utf-8") as f:
            data = json.load(f)
        eventos = scan_odds.parse_mres_blocks(data["content"])
        eventos, motivos = scan_odds.filtrar_elegiveis(eventos)
        print(f"catalogo: {len(eventos)} elegiveis apos filtros {motivos}\n")
    else:
        ap.error("informe um dump ou use --demo")

    resultados, descartes = processa(eventos)

    if args.json:
        print(json.dumps({"resultados": resultados, "descartes": descartes},
                         ensure_ascii=False, indent=2, default=str))
        return 0

    print("=== MOTOR DE PALPITES ESTATISTICOS (v27) ===")
    print(f"Eventos avaliados: {len(eventos)}")
    print(f"Com ao menos um candidato: {len(resultados)}")
    if len(eventos):
        print(f"Taxa de aproveitamento: {len(resultados)/len(eventos):.1%}")
    print()

    n_alta = n_mod = 0
    for r in resultados:
        print(f"- {r['jogo']} | {r['competicao']} | 1X2 {r['odds_1x2']}")
        for c in r["candidatos"][:args.max_por_jogo]:
            dv = (f" | desvio +{c['desvio']:.1%} sobre mediana "
                  f"{c['mediana_catalogo']:.1%}") if "desvio" in c else ""
            print(f"    {c['faixa']:<9} {c['mercado']:<22} "
                  f"{c['prob_pior_cenario']:.1%} | justa {c['odd_justa']:.2f}"
                  f" | amplitude {c['amplitude']:.1%}{dv}")
            if c["faixa"] == "Alta":
                n_alta += 1
            else:
                n_mod += 1
        lh, la = r["candidatos"][0]["lambdas"]
        print(f"    lambdas implicitos: {lh:.2f} / {la:.2f}")
    print()
    print(f"Candidatos reportados: {n_alta} Alta, {n_mod} Moderada")
    if descartes:
        print("\nDescartes:")
        for m, n in sorted(descartes.items(), key=lambda t: -t[1]):
            print(f"  {n:>4}  {m}")
    if args.demo:
        print(AVISO_CIRCULARIDADE)
        print("\n=== DEMONSTRACAO DO GATE domina_1x2() (Fase 3, v32) ===")
        alvo = next((r for r in resultados if r["candidatos"][0]["faixa"] == "Alta"), None)
        if alvo:
            prob_1x2_hipotetica = 0.60  # simula uma Aposta de Valor 1X2 com edge modesto
            dominado, melhor = domina_1x2(alvo["candidatos"], prob_1x2_hipotetica)
            print(f"Jogo: {alvo['jogo']} | hipotese: 1X2 com probabilidade propria "
                  f"{prob_1x2_hipotetica:.0%}")
            if dominado:
                print(f"DOMINADO: candidato derivado '{melhor['mercado']}' "
                      f"({melhor['prob_pior_cenario']:.1%}, faixa {melhor['faixa']}) supera "
                      "o 1X2 hipotetico por folga clara - regra 8/9 diz para preferir o "
                      "derivado, nao o 1X2, neste jogo.")
            else:
                print("NAO dominado: nenhum candidato derivado supera o 1X2 hipotetico "
                      "por margem suficiente - 1X2 pode seguir como recomendacao.")
        else:
            print("Nenhum jogo do catalogo demo teve candidato Alta para demonstrar o gate.")
    print("\nLEMBRETE: isto e PROBABILIDADE ancorada no preco da casa, nao edge.")
    print("PE nunca usa stake. Para virar Aposta de Valor precisa passar pelo")
    print("teste 9.1 com odds dos DOIS lados da MESMA casa.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
