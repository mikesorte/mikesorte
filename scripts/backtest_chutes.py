#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BACKTEST COM DADO REAL - mercado de chutes a gol / SOT (Fase 2, v32).

Mesmo motor de scripts/backtest_escanteios.py - ver docstring de la para o
algoritmo walk-forward sem vazamento e o teste de sanidade via oraculo.

MERCADO: total de FINALIZACOES NO GOL (shots on target, HST+AST) no jogo,
nao chutes totais (HS+AS) - e o mercado mais liquido/coberto pelas casas e
bate com o exemplo dado pelo usuario ("chutes ao gol").

EXPECTATIVA DECLARADA ANTES DE RODAR (achado do agente de validacao
estatistica, Fase 2): chutes-a-gol sao mais ruidosos que escanteios/cartoes
porque reagem fortemente ao ESTADO DO PLACAR em tempo real (time perdendo
aumenta volume de chutes, geralmente de pior qualidade/mais de fora da
area) - um efeito que a heuristica de "pace" pre-jogo nao capta. Calibracao
pior que escanteios e ESPERADA, nao necessariamente sinal de bug.

Uso:
    python3 scripts/backtest_chutes.py
    python3 scripts/backtest_chutes.py --detalhe
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtest_escanteios import (carrega_jogos_com_stats, walk_forward_lambdas,
                                 oraculo_lambdas, calibracao, avalia, ALPHA_SHRINKAGE,
                                 teste_embaralhamento)
from betting_model import brier

LINHAS = (7.5, 8.5, 9.5, 10.5, 11.5)
CONFIGS = {"poisson": None, "negbin_forma8": 8.0, "negbin_forma4": 4.0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--detalhe", action="store_true")
    args = ap.parse_args()

    jogos = carrega_jogos_com_stats(colunas_casa=("HST",), colunas_fora=("AST",))
    if not jogos:
        print("Nenhum jogo com HST/AST encontrado - rode baixa_dados_backtest.py primeiro.")
        return 1

    ligas = sorted({j["liga"] for j in jogos})
    print("=== BACKTEST COM DADO REAL - CHUTES A GOL / SOT (v32) ===")
    print(f"Jogos: {len(jogos)} | Ligas: {len(ligas)} ({', '.join(ligas)})")
    print(f"Periodo: {jogos[0]['data'].date()} a {jogos[-1]['data'].date()}")
    print("Mercado: finalizacoes NO GOL (SOT), nao chutes totais\n")

    resultados = {}
    for nome, forma in CONFIGS.items():
        previsoes = walk_forward_lambdas(jogos, alpha=ALPHA_SHRINKAGE, forma=forma, linhas=LINHAS)
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

    previsoes_oraculo = oraculo_lambdas(jogos, alpha=ALPHA_SHRINKAGE, linhas=LINHAS)
    brier_oraculo = brier([p for m in avalia(previsoes_oraculo, linhas=LINHAS).values() for p in m])
    brier_melhor = resultados[melhor_nome]["brier_global"]

    print("\n--- TESTE DE SANIDADE (canario: oraculo ve a temporada inteira) ---")
    print(f"Brier walk-forward honesto ({melhor_nome}): {brier_melhor:.5f}")
    print(f"Brier oraculo (ve o futuro):              {brier_oraculo:.5f}")
    veredito_sanidade = brier_melhor > brier_oraculo
    if not veredito_sanidade:
        print("Walk-forward honesto bateu o oraculo em Brier - NAO e prova automatica de "
              "bug (oraculo usa media plana da temporada, sem peso por recencia; se o "
              "mercado tiver tendencia real de curto prazo, o EWMA honesto pode "
              "genuinamente capturar mais sinal sem nunca ver o futuro). Rodando teste "
              "decisivo: embaralhar a ordem dos jogos e conferir se a vantagem some.")
        b_honesto_emb, b_oraculo_emb = teste_embaralhamento(
            jogos, alpha=ALPHA_SHRINKAGE, forma=None, linhas=LINHAS)
        print(f"  embaralhado: honesto={b_honesto_emb:.5f} oraculo={b_oraculo_emb:.5f}")
        if b_honesto_emb <= b_oraculo_emb:
            print("ALERTA: vantagem do honesto sobre o oraculo PERSISTE mesmo com a ordem "
                  "embaralhada - isso sim e sinal de vazamento (nao depende de ordem "
                  "cronologica real). NAO aceitar sem investigar.")
            veredito_sanidade = False
        else:
            print("OK: a vantagem SOME (e inverte) quando embaralhado - confirma que era "
                  "sinal real de recencia capturado pelo EWMA, nao vazamento.")
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
        print("REJEITADO: vies grande demais para promover sem investigar mais (esperado - "
              "chutes reagem ao estado do placar, ver docstring do modulo).")
    print("\nLIMITACOES: validacao agregada/pooled, nao por time; dado ate ~2013; "
          "chutes sao endogenos ao placar em tempo real - a heuristica de pace pre-jogo "
          "nao capta isso, era esperado ser o mercado mais dificil dos tres da Fase 2.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
