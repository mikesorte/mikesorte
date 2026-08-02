#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Estudo de ma-especificacao e calibracao do motor de PE (v28).

O QUE ISTO E - E O QUE NAO E
----------------------------
NAO e backtest com dado real. O catalogo de 01/08 nao foi persistido e os
conectores so funcionam em turno interativo, entao nao existe par
(odd real, resultado real) em escala para testar. Fingir que existe seria
inventar dado.

E um ESTUDO DE MA-ESPECIFICACAO: simulo um mundo onde EU sei a verdade e o
motor nao, e pergunto se as probabilidades que ele afirma se sustentam.

A armadilha que este arquivo evita: se eu gerar o mundo com o mesmo
Dixon-Coles que o motor usa para inverter, a calibracao sai perfeita por
construcao e o teste nao prova nada (foi o defeito do --demo do pe_engine,
declarado la). Aqui o mundo verdadeiro e DELIBERADAMENTE diferente do modelo:

  1. GOLS SUPERDISPERSOS - Poisson-gama (binomial negativa) em vez de Poisson
     puro. Futebol real tem variancia maior que a media; o motor assume que
     nao tem.
  2. rho VARIAVEL por jogo - o motor assume rho fixo em torno de -0.11.
  3. JOGOS COM CHOQUE - fracao dos jogos sofre expulsao/lesao que desequilibra
     o placar depois do apito. Informacao que nenhuma odd pre-jogo contem.
  4. VIES FAVORITO-AZARAO na precificacao - a casa poe margem MAIOR no azarao
     que no favorito. E um fenomeno documentado e real; o de-vig POWER nao
     sabe disso e vai errar de forma sistematica, nao aleatoria.

Se o motor continuar calibrado sob esse mundo, a metodologia e robusta. Se
descalibrar, o TAMANHO e a DIRECAO do erro sao o resultado util - e o que
diz onde corrigir.

Uso:
    python3 scripts/backtest.py                  # estudo padrao
    python3 scripts/backtest.py --n 20000        # mais amostra
    python3 scripts/backtest.py --mundo ideal    # controle (mundo = modelo)
"""
import argparse
import math
import os
import random
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pe_engine as pe
from betting_model import wilson_ci


# ----------------------------------------------------------- mundo verdadeiro
def gols_superdispersos(lmbda, rnd, forma=6.0):
    """Poisson-gama: lambda e sorteado de uma gama com media lmbda, depois o
    placar sai de um Poisson com esse lambda. Produz variancia maior que a
    media (superdispersao), como futebol real. 'forma' alto -> perto de
    Poisson puro; 'forma' baixo -> muito superdisperso."""
    escala = lmbda / forma
    lam_real = rnd.gammavariate(forma, escala)
    # Poisson por metodo de Knuth
    L, k, p = math.exp(-lam_real), 0, 1.0
    while True:
        p *= rnd.random()
        if p <= L:
            return k
        k += 1
        if k > 25:
            return k


def simula_partida(lh, la, rnd, mundo):
    """Devolve (gols_casa, gols_fora) sob o mundo escolhido."""
    if mundo == "ideal":
        # controle: Poisson puro, exatamente o que o modelo assume
        return (gols_superdispersos(lh, rnd, forma=1e6),
                gols_superdispersos(la, rnd, forma=1e6))

    # jogo com choque: expulsao/lesao muda o jogo depois que a odd foi fixada
    if rnd.random() < 0.08:
        if rnd.random() < 0.5:
            lh, la = lh * 0.55, la * 1.60
        else:
            lh, la = lh * 1.60, la * 0.55

    gh = gols_superdispersos(lh, rnd, forma=rnd.uniform(4.0, 9.0))
    ga = gols_superdispersos(la, rnd, forma=rnd.uniform(4.0, 9.0))

    # correlacao de placares baixos, com intensidade variavel por jogo
    if gh <= 1 and ga <= 1 and rnd.random() < 0.10:
        if rnd.random() < 0.5:
            gh = max(0, gh - 1)
        else:
            ga = max(0, ga - 1)
    return gh, ga


def probs_verdadeiras(lh, la, rnd_seed, mundo, n_sim=4000):
    """Probabilidade VERDADEIRA de cada mercado, por Monte Carlo do mundo
    verdadeiro. E contra isto que o motor sera medido - nao contra o DC."""
    rnd = random.Random(rnd_seed)
    c = defaultdict(int)
    for _ in range(n_sim):
        gh, ga = simula_partida(lh, la, rnd, mundo)
        tot = gh + ga
        if gh > ga:
            c["home"] += 1
        elif gh == ga:
            c["draw"] += 1
        else:
            c["away"] += 1
        c["Over 1.5"] += tot > 1.5
        c["Over 2.5"] += tot > 2.5
        c["Under 2.5"] += tot < 2.5
        c["Under 3.5"] += tot < 3.5
        c["Ambas marcam (BTTS)"] += (gh >= 1 and ga >= 1)
        c["Ambas NAO marcam"] += not (gh >= 1 and ga >= 1)
    return {k: v / n_sim for k, v in c.items()}


def precifica(p_home, p_draw, p_away, rnd, mundo, margem_base=0.06):
    """Converte probabilidade verdadeira em odds de casa.

    VIES FAVORITO-AZARAO: a casa nao distribui a margem por igual. O azarao
    leva margem proporcionalmente maior (odd relativamente pior). Isso e real
    e o de-vig POWER nao modela - entao o motor vai herdar um erro
    SISTEMATICO, que e justamente o que queremos medir.
    """
    probs = [p_home, p_draw, p_away]
    if mundo == "ideal":
        infladas = [p * (1 + margem_base) for p in probs]
    else:
        infladas = []
        for p in probs:
            # quanto menor a probabilidade, maior a margem aplicada
            extra = margem_base * (1.0 + 0.9 * (1.0 - p))
            infladas.append(p * (1 + extra))
    odds = []
    for p in infladas:
        if p <= 0:
            return None
        odds.append(round(1.0 / p, 2))
    return odds


# ------------------------------------------------------------------ avaliacao
def roda(n_jogos, mundo, seed=42):
    rnd = random.Random(seed)
    eventos, verdades = [], []
    for i in range(n_jogos):
        total = min(max(rnd.gauss(2.65, 0.55), 1.1), 4.6)
        diff = rnd.gauss(0.28, 0.85)
        diff = min(max(diff, -(total - 0.4)), total - 0.4)
        lh, la = (total + diff) / 2, (total - diff) / 2
        pv = probs_verdadeiras(lh, la, seed * 100000 + i, mundo)
        odds = precifica(pv["home"], pv["draw"], pv["away"], rnd, mundo)
        if odds is None:
            continue
        eventos.append({"participants": f"J{i}", "competition": f"Liga {i%17}",
                        "start_time": None, "odds": odds})
        verdades.append(pv)

    resultados, descartes = pe.processa(eventos)
    idx = {e["participants"]: k for k, e in enumerate(eventos)}

    # cada PE emitido vira um par (prob_afirmada, prob_verdadeira)
    pares = []
    for r in resultados:
        v = verdades[idx[r["jogo"]]]
        for c in r["candidatos"]:
            if c["mercado"] in v:
                pares.append((c["faixa"], c["mercado"],
                              c["prob_pior_cenario"], v[c["mercado"]]))
    return pares, len(eventos), descartes


def relatorio(pares, n_eventos, descartes, mundo, rnd_seed=7):
    print(f"\n=== ESTUDO DE CALIBRACAO - mundo '{mundo}' ===")
    print(f"Jogos simulados: {n_eventos} | PEs emitidos: {len(pares)}")
    if n_eventos:
        jogos_com_pe = len({m for _, m, _, _ in pares}) if pares else 0
        print(f"Taxa de emissao: {len(pares)/n_eventos:.1%} PE por jogo")
    if not pares:
        print("Nenhum PE emitido - nada a calibrar.")
        return None

    # (1) simulacao dos desfechos: o PE ocorreu ou nao?
    rnd = random.Random(rnd_seed)
    ocorrencias = [(faixa, merc, afirm, 1 if rnd.random() < verd else 0, verd)
                   for faixa, merc, afirm, verd in pares]

    print("\n--- Calibracao por FAIXA (o teste que decide) ---")
    print(f"{'faixa':<10} {'N':>5} {'afirmado':>9} {'ocorreu':>9} "
          f"{'verdade':>9} {'vies':>8}  Wilson 95%")
    saida = {}
    for faixa in ("Alta", "Moderada"):
        g = [o for o in ocorrencias if o[0] == faixa]
        if not g:
            continue
        n = len(g)
        af = sum(o[2] for o in g) / n
        oc = sum(o[3] for o in g) / n
        vd = sum(o[4] for o in g) / n
        _, lo, hi = wilson_ci(sum(o[3] for o in g), n)
        flag = ""
        if af > hi:
            flag = "  <-- AFIRMA MAIS DO QUE ENTREGA"
        elif af < lo:
            flag = "  <-- conservador demais"
        print(f"{faixa:<10} {n:>5} {af:>8.1%} {oc:>8.1%} {vd:>8.1%} "
              f"{af-vd:>+7.1%}  [{lo:.1%}, {hi:.1%}]{flag}")
        saida[faixa] = {"n": n, "afirmado": af, "verdade": vd, "vies": af - vd,
                        "wilson": (lo, hi), "descalibrado": af > hi or af < lo}

    print("\n--- Vies por MERCADO (onde o erro se concentra) ---")
    print(f"{'mercado':<24} {'N':>5} {'afirmado':>9} {'verdade':>9} {'vies':>8}")
    por_merc = defaultdict(list)
    for faixa, merc, af, oc, vd in ocorrencias:
        por_merc[merc].append((af, vd))
    for merc, vals in sorted(por_merc.items(), key=lambda t: -len(t[1])):
        n = len(vals)
        af = sum(a for a, _ in vals) / n
        vd = sum(v for _, v in vals) / n
        alerta = "  <-- vies material" if abs(af - vd) > 0.03 else ""
        print(f"{merc:<24} {n:>5} {af:>8.1%} {vd:>8.1%} {af-vd:>+7.1%}{alerta}")

    # (2) Brier contra a probabilidade VERDADEIRA (mede acuracia, nao sorte)
    brier = sum((af - vd) ** 2 for _, _, af, _, vd in ocorrencias) / len(ocorrencias)
    erro_abs = sum(abs(af - vd) for _, _, af, _, vd in ocorrencias) / len(ocorrencias)
    print(f"\nErro medio absoluto (afirmado vs verdadeiro): {erro_abs:.2%}")
    print(f"Brier contra a verdade: {brier:.5f}  (0 = perfeito)")

    if descartes:
        print("\nDescartes do motor:")
        for m, n in sorted(descartes.items(), key=lambda t: -t[1])[:6]:
            print(f"  {n:>5}  {m}")
    return saida


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=4000)
    ap.add_argument("--mundo", choices=["real", "ideal"], default="real")
    ap.add_argument("--ambos", action="store_true",
                    help="roda o controle 'ideal' e o 'real' para comparar")
    args = ap.parse_args()

    mundos = ["ideal", "real"] if args.ambos else [args.mundo]
    for m in mundos:
        pares, n, desc = roda(args.n, m)
        relatorio(pares, n, desc, m)
        if m == "ideal":
            print("\n(Controle: mundo quase igual ao modelo. Se AQUI ja houver")
            print(" vies, o problema e do motor, nao da ma-especificacao.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
