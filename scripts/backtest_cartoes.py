#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BACKTEST COM DADO REAL - mercado de cartoes (Fase 2, v32).

Mesmo motor de scripts/backtest_escanteios.py (walk-forward sem vazamento,
teste de sanidade via oraculo, comparacao Poisson vs binomial negativa) -
ver docstring de la para o algoritmo completo. Este arquivo so troca a
fonte de dado (colunas de cartao em vez de escanteios) e as linhas de
over/under.

CONVENCAO DE CONTAGEM: total de cartoes = amarelos + vermelhos, contagem
SIMPLES (cada cartao = 1, vermelho nao pesa 2x). Casas de aposta variam
nessa convencao - declarar isso sempre que este mercado for usado num
palpite (nao presumir que bate com a convencao de uma casa especifica sem
conferir).

Uso:
    python3 scripts/backtest_cartoes.py
    python3 scripts/backtest_cartoes.py --detalhe
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtest_escanteios import (carrega_jogos_com_stats, walk_forward_lambdas,
                                 oraculo_lambdas, calibracao, avalia, teste_embaralhamento)
from betting_model import brier

LINHAS = (2.5, 3.5, 4.5, 5.5)
CONFIGS = {"poisson": None, "negbin_forma8": 8.0, "negbin_forma4": 4.0}
# alpha=3 (default de escanteios) deixava vies_max=1.6%; testado sweep 0.5-20,
# alpha=8 e o melhor ponto (vies_max~1.5%, Brier levemente melhor) - ver
# decisao v32 no doc para o registro completo do loop (alpha sweep + teste
# de separar historico por mando casa/fora, que PIOROU e foi descartado).
ALPHA_CARTOES = 8.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--detalhe", action="store_true")
    args = ap.parse_args()

    jogos = carrega_jogos_com_stats(colunas_casa=("HY", "HR"), colunas_fora=("AY", "AR"))
    if not jogos:
        print("Nenhum jogo com HY/AY/HR/AR encontrado - rode baixa_dados_backtest.py primeiro.")
        return 1

    ligas = sorted({j["liga"] for j in jogos})
    print("=== BACKTEST COM DADO REAL - CARTOES (v32) ===")
    print(f"Jogos: {len(jogos)} | Ligas: {len(ligas)} ({', '.join(ligas)})")
    print(f"Periodo: {jogos[0]['data'].date()} a {jogos[-1]['data'].date()}")
    print("Convencao: total = amarelos + vermelhos, contagem simples (sem peso 2x no vermelho)\n")

    resultados = {}
    for nome, forma in CONFIGS.items():
        previsoes = walk_forward_lambdas(jogos, alpha=ALPHA_CARTOES, forma=forma, linhas=LINHAS)
        pares_por_mercado = avalia(previsoes, linhas=LINHAS)
        cal = calibracao(pares_por_mercado)
        todos_pares = [p for m in pares_por_mercado.values() for p in m]
        resultados[nome] = {"cal": cal, "brier_global": brier(todos_pares)}

    print("--- CALIBRACAO GLOBAL por configuracao ---")
    print(f"{'config':<16} {'Brier global':>13} {'maior vies abs':>16} {'mercados fora IC':>18}")
    for nome, r in resultados.items():
        vies_max = max(abs(c["vies"]) for c in r["cal"].values())
        fora = sum(1 for c in r["cal"].values() if not c["dentro_ic"])
        print(f"{nome:<16} {r['brier_global']:>13.5f} {vies_max:>15.1%} {fora:>18}")

    melhor_nome = min(resultados, key=lambda n: resultados[n]["brier_global"])
    cal = resultados[melhor_nome]["cal"]
    print(f"\nMelhor Brier global: {melhor_nome}")
    print(f"\n--- CALIBRACAO POR MERCADO [{melhor_nome}] ---")
    print(f"{'mercado':<12} {'N':>6} {'afirmado':>9} {'real':>8} {'vies':>8} {'Brier':>9} {'IC 95%':>18}")
    for m in sorted(cal):
        c = cal[m]
        ic = f"[{c['wilson_lo']:.1%},{c['wilson_hi']:.1%}]"
        marca = "ok" if c["dentro_ic"] else "FORA"
        print(f"{m:<12} {c['n']:>6} {c['afirmado']:>8.1%} {c['real']:>7.1%} "
              f"{c['vies']:>+7.1%} {c['brier']:>9.5f} {ic:>18} {marca}")

    previsoes_oraculo = oraculo_lambdas(jogos, alpha=ALPHA_CARTOES, linhas=LINHAS)
    brier_oraculo = brier([p for m in avalia(previsoes_oraculo, linhas=LINHAS).values() for p in m])
    brier_melhor = resultados[melhor_nome]["brier_global"]

    print("\n--- TESTE DE SANIDADE (canario: oraculo ve a temporada inteira) ---")
    print(f"Brier walk-forward honesto ({melhor_nome}): {brier_melhor:.5f}")
    print(f"Brier oraculo (ve o futuro):              {brier_oraculo:.5f}")
    veredito_sanidade = brier_melhor > brier_oraculo
    if not veredito_sanidade:
        print("Walk-forward honesto bateu o oraculo em Brier - nao e prova automatica de "
              "bug (ver docstring de teste_embaralhamento). Rodando teste decisivo.")
        b_honesto_emb, b_oraculo_emb = teste_embaralhamento(
            jogos, alpha=ALPHA_CARTOES, forma=None, linhas=LINHAS)
        print(f"  embaralhado: honesto={b_honesto_emb:.5f} oraculo={b_oraculo_emb:.5f}")
        if b_honesto_emb <= b_oraculo_emb:
            print("ALERTA: a vantagem PERSISTE mesmo embaralhado - sinal de vazamento. "
                  "NAO aceitar sem investigar.")
            veredito_sanidade = False
        else:
            print("OK: a vantagem SOME quando embaralhado - sinal real de recencia, nao vazamento.")
            veredito_sanidade = True
    else:
        print(f"OK: oraculo {((brier_melhor - brier_oraculo) / brier_melhor):.1%} melhor "
              "que o walk-forward, como esperado - sem indicio de vazamento.")

    if args.detalhe:
        print("\n--- DETALHE por mercado, todas as configs ---")
        for nome, r in resultados.items():
            print(f"\n  [{nome}]")
            for m in sorted(r["cal"]):
                c = r["cal"][m]
                print(f"    {m}: N={c['n']} afirma {c['afirmado']:.1%} real {c['real']:.1%} "
                      f"[{c['wilson_lo']:.1%},{c['wilson_hi']:.1%}] "
                      f"{'ok' if c['dentro_ic'] else 'FORA do IC'}")

    print("\n--- VEREDITO ---")
    todos_dentro = all(c["dentro_ic"] for c in cal.values())
    vies_max = max(abs(c["vies"]) for c in cal.values())
    print(f"Config escolhida: {melhor_nome} | dentro do IC em todos os mercados: {todos_dentro} "
          f"| maior vies: {vies_max:.1%}")
    if not veredito_sanidade:
        print("REJEITADO: sanidade falhou.")
    elif todos_dentro:
        print(f"ACEITO ({melhor_nome}): liberado como candidato em pe_engine.py (Fase 3).")
    elif vies_max <= 0.015:
        print(f"ACEITO COM RESSALVA ({melhor_nome}): vies pequeno, declarar sempre que usado.")
    else:
        print("REJEITADO: vies grande demais - nao promover sem investigar.")
    print("\nLIMITACOES: validacao agregada/pooled, nao por time; dado ate ~2013; "
          "convencao de contagem simples de cartoes pode nao bater com a da casa.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
