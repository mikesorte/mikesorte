#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reproduz o calculo de correlacao (phi) entre categorias de mercado que
embasa a decisao 45/v33 (independencia entre gols/escanteios/cartoes numa
combinada). Achado de auditoria (08/08): esse calculo so existia como
RESULTADO documentado em docs/DAILY_METHODOLOGY.md e comentario em
betting_model.py - nao havia script persistido/reproduzivel no repo, um
auditor futuro tinha que refazer o trabalho do zero pra conferir (foi
exatamente isso que a auditoria de 08/08 fez, e bateu quase exato com os
numeros da decisao 45).

Le os mesmos CSVs de data/backtest/*.csv (football-data.co.uk via
raw.githubusercontent.com, decisao 41/44), pareando por LINHA (mesmo jogo)
gols/escanteios/cartoes - diferente de carrega_jogos_com_stats() dos
scripts backtest_*.py, que filtra cada mercado separadamente e por isso
NAO preserva pareamento por jogo entre mercados diferentes.

Limiares (os mesmos da decisao 45): Over 2.5 gols, Over 9.5 escanteios,
Over 3.5 cartoes (amarelos+vermelhos, mesma convencao de
scripts/backtest_cartoes.py).

Uso:
    python3 scripts/compute_market_correlation.py
"""
import csv
import glob
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DADOS = os.path.join(ROOT, "data/backtest")

LIMIAR_GOLS = 2.5
LIMIAR_ESCANTEIOS = 9.5
LIMIAR_CARTOES = 3.5

COLUNAS_NECESSARIAS = ("FTHG", "FTAG", "HC", "AC", "HY", "AY", "HR", "AR")


def carrega_pareado():
    """Le todos os CSVs, mantendo so linhas com TODAS as colunas de gols +
    escanteios + cartoes presentes - o pareamento por LINHA (mesmo jogo)
    e o que garante que a correlacao medida e real, nao um artefato de
    juntar amostras diferentes de jogos diferentes."""
    linhas = []
    for caminho in sorted(glob.glob(os.path.join(DADOS, "*.csv"))):
        with open(caminho, encoding="utf-8", errors="replace") as f:
            for r in csv.DictReader(f):
                if any(not r.get(c) for c in COLUNAS_NECESSARIAS):
                    continue
                try:
                    gols = int(r["FTHG"]) + int(r["FTAG"])
                    escanteios = int(r["HC"]) + int(r["AC"])
                    cartoes = int(r["HY"]) + int(r["AY"]) + int(r["HR"]) + int(r["AR"])
                except (ValueError, TypeError):
                    continue
                linhas.append((gols, escanteios, cartoes))
    return linhas


def phi(bin_a, bin_b):
    """Coeficiente phi (correlacao de Pearson entre duas variaveis
    binarias 0/1) - formula direta da tabela de contingencia 2x2."""
    n = len(bin_a)
    n11 = sum(1 for a, b in zip(bin_a, bin_b) if a and b)
    n10 = sum(1 for a, b in zip(bin_a, bin_b) if a and not b)
    n01 = sum(1 for a, b in zip(bin_a, bin_b) if not a and b)
    n00 = n - n11 - n10 - n01
    n1_ = n11 + n10
    n0_ = n01 + n00
    n_1 = n11 + n01
    n_0 = n10 + n00
    denom = math.sqrt(n1_ * n0_ * n_1 * n_0)
    if denom == 0:
        return 0.0, n11 / n if n else 0.0, (n1_ / n) * (n_1 / n) if n else 0.0
    coef = (n11 * n00 - n10 * n01) / denom
    p_ambos_real = n11 / n
    p_ambos_indep = (n1_ / n) * (n_1 / n)
    return coef, p_ambos_real, p_ambos_indep


def main():
    linhas = carrega_pareado()
    if not linhas:
        print("Nenhuma linha com gols+escanteios+cartoes pareados - rode "
              "scripts/baixa_dados_backtest.py primeiro.")
        return 1

    gols_bin = [1 if g > LIMIAR_GOLS else 0 for g, _, _ in linhas]
    esc_bin = [1 if e > LIMIAR_ESCANTEIOS else 0 for _, e, _ in linhas]
    cart_bin = [1 if c > LIMIAR_CARTOES else 0 for _, _, c in linhas]

    print(f"=== CORRELACAO ENTRE CATEGORIAS DE MERCADO (N={len(linhas)}) ===")
    print(f"Limiares: Over {LIMIAR_GOLS} gols | Over {LIMIAR_ESCANTEIOS} escanteios | "
          f"Over {LIMIAR_CARTOES} cartoes\n")

    pares = (
        ("Over gols x Over escanteios", gols_bin, esc_bin),
        ("Over gols x Over cartoes", gols_bin, cart_bin),
        ("Over escanteios x Over cartoes", esc_bin, cart_bin),
    )
    for nome, a, b in pares:
        coef, p_real, p_indep = phi(a, b)
        razao = p_real / p_indep if p_indep else float("nan")
        print(f"{nome:35s} phi={coef:+.4f} | P(ambos) real {p_real:.1%} vs "
              f"independente {p_indep:.1%} (razao {razao:.3f})")

    print("\nReferencia (decisao 45/v33, N=15.136-15.137, medido em 03/08/2026):")
    print("  Over 2.5 gols x Over 9.5 escanteios: phi=-0.004 | 27.4% vs 27.5% (razao 0.996)")
    print("  Over 2.5 gols x Over 3.5 cartoes:    phi=+0.011 | 30.5% vs 30.3% (razao 1.009)")
    print("  Over 9.5 escant. x Over 3.5 cartoes: phi=-0.010 | 34.1% vs 34.3% (razao 0.993)")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
