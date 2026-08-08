#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BACKTEST COM DADO REAL (v29).

Diferente de scripts/backtest.py, que simula um mundo. Aqui as odds sao
REAIS (Bet365, coluna B365H/D/A de football-data.co.uk) e os resultados sao
REAIS (FTHG/FTAG). Nao ha modelo gerando a verdade - a verdade e o placar.

POR QUE ISTO PASSOU A SER POSSIVEL (v29, 03/08)
-----------------------------------------------
Por semanas o sistema tratou "sem conector = sem dado" como fato. Era falso.
Durante a revisao semanal, testando o allowlist de rede, descobri que
`raw.githubusercontent.com` RESPONDE (200), enquanto football-data.co.uk
direto da 403. Ou seja: existia um canal aberto para dado historico com odds
o tempo todo, e eu nunca tinha testado esse host especifico.

Isso e a mesma classe de erro das decisoes 36 e 39: concluir que algo e
impossivel sem ter testado a alternativa obvia. Terceira vez. A regra que
fica: antes de declarar bloqueio estrutural, ENUMERAR os canais e testar um
por um - "a rede esta bloqueada" nao e diagnostico, e generalizacao.

O QUE ESTE BACKTEST MEDE
------------------------
Calibracao: quando o motor afirma 75%, o desfecho ocorre 75% das vezes?
Mede POR MERCADO (nao so agregado - decisao 41 mostrou que o agregado
esconde erros opostos que se cancelam).

Compara configuracoes lado a lado para isolar cada mudanca:
  v27          - Poisson puro + de-vig POWER
  shin         - Poisson puro + de-vig SHIN (isola o efeito do Shin)
  v28          - pior cenario entre dispersoes + Shin (o que esta em producao)

Isto e o que decide se as mudancas de v28 foram melhoria real ou ajuste a
uma simulacao inventada. A literatura esta dividida sobre superdispersao em
futebol moderno (Maher 1982 defende Poisson; Pollard e outros defendem
binomial negativa), entao a pergunta so se resolve com dado.

Uso:
    python3 scripts/backtest_real.py
    python3 scripts/backtest_real.py --detalhe   # tabela por mercado e config
"""
import argparse
import csv
import glob
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from betting_model import (gols_dixon_coles, implied_lambdas, devig_power,
                           devig_shin, wilson_ci, InversaoFalhou)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DADOS = os.path.join(ROOT, "data/backtest")

# mesmas dispersoes usadas em producao (pe_engine.CENARIOS)
DISPERSOES = (None, 8.0, 5.0, 3.5, 2.5)


def carrega():
    """Le os CSVs reais. Devolve lista de (odds, gols_casa, gols_fora, liga)."""
    jogos = []
    for caminho in sorted(glob.glob(os.path.join(DADOS, "*.csv"))):
        liga = os.path.basename(caminho).replace(".csv", "")
        with open(caminho, encoding="utf-8", errors="replace") as f:
            for r in csv.DictReader(f):
                try:
                    odds = [float(r["B365H"]), float(r["B365D"]), float(r["B365A"])]
                    gh, ga = int(r["FTHG"]), int(r["FTAG"])
                except (KeyError, ValueError, TypeError):
                    continue
                if any(o <= 1.0 for o in odds):
                    continue
                over = sum(1.0 / o for o in odds) - 1.0
                if not (0.005 <= over <= 0.25):
                    continue
                jogos.append((odds, gh, ga, liga))
    return jogos


def desfechos_reais(gh, ga):
    """O que de fato aconteceu, por mercado."""
    tot = gh + ga
    return {
        "Over 1.5": tot > 1.5,
        "Over 2.5": tot > 2.5,
        "Under 2.5": tot < 2.5,
        "Under 3.5": tot < 3.5,
        "Ambas marcam (BTTS)": gh >= 1 and ga >= 1,
        "Ambas NAO marcam": not (gh >= 1 and ga >= 1),
    }


def probs_config(odds, config):
    """Probabilidades derivadas sob uma configuracao. None se a inversao falhar.

    "producao" e IDENTICO a "shin" hoje (devig_shin + sem dispersao,
    decisao 42) - mantido como config separada so por legibilidade da
    tabela de saida (deixa explicito qual coluna e "o que roda de
    verdade"), nao porque calcula algo diferente."""
    try:
        if config == "v27":
            justo, disp = devig_power(odds), (None,)
        elif config in ("shin", "producao"):
            justo, disp = devig_shin(odds), (None,)
        elif config == "v28":
            justo, disp = devig_shin(odds), DISPERSOES
        else:
            raise ValueError(config)
    except Exception:
        return None

    # Achado de auditoria (08/08): implied_lambdas() (um solve de Newton
    # caro) era chamado DENTRO do loop "for forma in disp", embora nao
    # dependa de 'forma' (forma so entra em gols_dixon_coles, a dispersao
    # da PROJECAO, nao a inversao do 1X2 que gera lh/la). Pra config="v28"
    # (5 cenarios de dispersao) isso repetia o solve 5x por nada - movido
    # pra fora do loop, roda 1x e reusa pros 5 cenarios.
    try:
        lh, la = implied_lambdas(*justo)
    except InversaoFalhou:
        return None

    acumulado = {}
    for forma in disp:
        d = gols_dixon_coles(lh, la, rho=-0.11, forma=forma)
        vals = {
            "Over 1.5": d["over_1.5"], "Over 2.5": d["over_2.5"],
            "Under 2.5": d["under_2.5"], "Under 3.5": d["under_3.5"],
            "Ambas marcam (BTTS)": d["btts"], "Ambas NAO marcam": 1 - d["btts"],
        }
        for k, v in vals.items():
            acumulado.setdefault(k, []).append(v)
    # v28 em producao reporta o PIOR cenario; as outras tem so um cenario
    return {k: min(v) for k, v in acumulado.items()}


def avalia(jogos, configs=("v27", "shin", "v28", "producao")):
    """{config: {mercado: [(prob_afirmada, ocorreu), ...]}}

    Achado de auditoria (08/08): "producao" e identico a "shin" em
    probs_config() - calcular os dois de verdade era 100% trabalho
    duplicado. Se ambos estiverem em 'configs', "producao" reusa o
    resultado ja computado de "shin" em vez de rechamar probs_config()."""
    configs_unicas = [c for c in configs if not (c == "producao" and "shin" in configs)]
    out = {c: {} for c in configs}
    descartados = 0
    for odds, gh, ga, _liga in jogos:
        reais = desfechos_reais(gh, ga)
        resultados_linha = {}
        for c in configs_unicas:
            p = probs_config(odds, c)
            resultados_linha[c] = p
            if p is None:
                descartados += 1
                continue
            for merc, prob in p.items():
                out[c].setdefault(merc, []).append((prob, reais[merc]))
        if "producao" in configs and "shin" in configs:
            p_shin = resultados_linha.get("shin")
            if p_shin is not None:
                for merc, prob in p_shin.items():
                    out["producao"].setdefault(merc, []).append((prob, reais[merc]))
    return out, descartados


def resumo(pares):
    """(n, prob_media_afirmada, taxa_real, vies, brier)"""
    n = len(pares)
    if not n:
        return None
    af = sum(p for p, _ in pares) / n
    real = sum(1 for _, o in pares if o) / n
    brier = sum((p - (1 if o else 0)) ** 2 for p, o in pares) / n
    return n, af, real, af - real, brier


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--detalhe", action="store_true")
    args = ap.parse_args()

    jogos = carrega()
    if not jogos:
        print(f"Nenhum jogo carregado de {DADOS} - rode o download primeiro.")
        return 1
    ligas = sorted({j[3] for j in jogos})
    print("=== BACKTEST COM DADO REAL (v29) ===")
    print(f"Jogos: {len(jogos)} | Ligas: {len(ligas)}")
    print(f"Odds: Bet365 (1X2 real) | Verdade: placar final real\n")

    dados, desc = avalia(jogos)

    print("--- CALIBRACAO GLOBAL por configuracao ---")
    print(f"{'config':<8} {'N':>6} {'afirmado':>9} {'real':>8} {'vies':>8} {'Brier':>9}")
    globais = {}
    for c in ("v27", "shin", "v28", "producao"):
        todos = [p for m in dados[c].values() for p in m]
        r = resumo(todos)
        if not r:
            continue
        n, af, real, vies, brier = r
        globais[c] = r
        print(f"{c:<8} {n:>6} {af:>8.1%} {real:>7.1%} {vies:>+7.1%} {brier:>9.5f}")

    print("\n--- VIES POR MERCADO (o corte que o agregado esconde) ---")
    mercados = sorted(dados["v27"].keys())
    print(f"{'mercado':<22} " + "".join(f"{c:>18}" for c in ("v27", "shin", "v28")))
    print(f"{'':<22} " + "".join(f"{'vies':>9}{'Brier':>9}" for _ in range(3)))
    for m in mercados:
        linha = f"{m:<22} "
        for c in ("v27", "shin", "v28"):
            r = resumo(dados[c].get(m, []))
            linha += f"{r[3]:>+8.1%} {r[4]:>8.4f}" if r else f"{'-':>18}"
        print(linha)

    if args.detalhe:
        print("\n--- DETALHE: afirmado vs real, por mercado ---")
        for c in ("v27", "v28"):
            print(f"\n  [{c}]")
            for m in mercados:
                r = resumo(dados[c].get(m, []))
                if not r:
                    continue
                n, af, real, vies, brier = r
                k = sum(1 for _, o in dados[c][m] if o)
                _, lo, hi = wilson_ci(k, n)
                dentro = "ok" if lo <= af <= hi else "FORA do IC"
                print(f"    {m:<22} N={n:<5} afirma {af:.1%} real {real:.1%} "
                      f"[{lo:.1%},{hi:.1%}] {dentro}")

    # veredito
    print("\n--- VEREDITO ---")
    if "v27" in globais and "v28" in globais:
        b27, b28 = globais["v27"][4], globais["v28"][4]
        bshin = globais.get("shin", (0, 0, 0, 0, None))[4]
        print(f"Brier v27 (Poisson+power): {b27:.5f}")
        if bshin:
            print(f"Brier shin (Poisson+Shin): {bshin:.5f}  "
                  f"({'melhora' if bshin < b27 else 'PIORA'} {abs(bshin-b27)/b27:.1%} vs v27)")
        print(f"Brier v28 (disp.+Shin):    {b28:.5f}  "
              f"({'melhora' if b28 < b27 else 'PIORA'} {abs(b28-b27)/b27:.1%} vs v27)")
        if b28 > b27:
            print("\nATENCAO: v28 PIOROU o Brier em dado real. Os cenarios de")
            print("dispersao foram calibrados contra uma simulacao inventada por")
            print("mim, e a literatura (Maher 1982) ja indicava que futebol")
            print("moderno tem razao variancia/media perto de 1. Isto e evidencia")
            print("de overfitting a fantasia - reavaliar (Categoria B).")
    if desc:
        print(f"\n(inversao falhou em {desc} avaliacoes - descartadas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
