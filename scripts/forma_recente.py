#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Motor de frequencia EMPIRICA sobre os ultimos jogos de um time (v33).

O QUE ISTO E - O METODO MANUAL DO USUARIO, FORMALIZADO
--------------------------------------------------------
Ate v32 o sistema so tinha modelos PARAMETRICOS (Poisson, calibrado contra
uma base historica generica de 2000-2013, 15.150 jogos de 5 ligas europeias
- ver scripts/backtest_escanteios.py). Isso valida que a FORMA Poisson e
razoavel em agregado, mas nunca olha pros dois times especificos do jogo de
hoje - critica correta do usuario ("base de dados rasa").

O metodo que o usuario descreveu e mais simples e mais direto: pegar os
ULTIMOS N JOGOS REAIS de um time, contar em quantos deles uma estatistica
passou de um limiar (ex.: "7 de 10 jogos com +8 escanteios"), e comparar
essa TAXA EMPIRICA contra a odd oferecida hoje pra esse mesmo limiar. Sem
lambda, sem Poisson, sem inversao - contagem direta.

ESTE MODULO NAO BUSCA DADO NENHUM. A coleta continua sendo pesquisa ao vivo
(WebSearch/Nimble/Tavily na cascata da regra 6.1 - sofascore, whoscored,
flashscore, fbref) durante o aprofundamento de cada jogo (2-4/dia), que
persiste os ultimos jogos de cada time no schema abaixo (mesma disciplina
da regra v26: dump salvo e commitado, nunca perdido) - buscar um scraper
fixo pra um site especifico seria fragil (formato muda, quebra silencioso);
o processo manual/cascata ja existente e mais robusto.

SCHEMA (data/dumps/YYYY-MM-DD-forma-{time-slug}.csv):
    data,adversario,mandante,chutes,chutes_gol,escanteios,cartoes,faltas,posse,resultado
    2026-07-20,Time X,sim,14,6,7,2,11,58,V 2-1
    ...
    (mandante: "sim"/"nao" - o time era mandante NESSE jogo passado; colunas
    numericas vazias quando a fonte nao trouxe - taxa_empirica() ignora None)

Uso:
    python3 scripts/forma_recente.py <csv> --coluna escanteios --limiar 8.5 --odd 1.65
    python3 scripts/forma_recente.py --demo   # reproduz o exemplo do usuario
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from betting_model import wilson_ci, ev_unitario, prob_combinada, odd_combinada, ev_combinada

COLUNAS_NUMERICAS = ("chutes", "chutes_gol", "escanteios", "cartoes", "faltas", "posse")


def carrega_forma(caminho_csv):
    """Le o schema acima. Devolve lista de dicts com as colunas numericas
    convertidas (None quando vazio/ausente - nunca inventar valor)."""
    linhas = []
    with open(caminho_csv, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            linha = dict(r)
            for col in COLUNAS_NUMERICAS:
                v = (r.get(col) or "").strip()
                linha[col] = float(v) if v else None
            linhas.append(linha)
    return linhas


def taxa_empirica(valores, limiar):
    """O metodo manual do usuario: em quantos dos ultimos jogos o valor
    passou do limiar? valores=None sao ignorados (dado ausente, nao conta
    nem a favor nem contra - nunca inventar).

    Retorna dict: n (amostra valida), k (acima do limiar), taxa (k/n),
    wilson_lo/wilson_hi (IC 95%). wilson_lo e o numero CONSERVADOR a usar
    em decisao (mesma filosofia do "pior cenario sempre" que o motor de PE
    ja usa) - com N=10 o intervalo e largo de proposito, N pequeno nao
    sustenta confianca alta por si so.
    """
    validos = [v for v in valores if v is not None]
    n = len(validos)
    k = sum(1 for v in validos if v > limiar)
    taxa, lo, hi = wilson_ci(k, n) if n else (0.0, 0.0, 0.0)
    return {"n": n, "k": k, "taxa": taxa, "wilson_lo": lo, "wilson_hi": hi}


def taxa_confronto_direto(valores_h2h, limiar):
    """Mesma funcao aplicada ao historico de confronto direto (H2H). N
    tipicamente pequeno (regra 2 do doc: "H2H 2-3 temporadas; N=3
    consistente = Wilson moderado, nao alto") - isso cai de graca do
    mesmo calculo de Wilson, nao precisa de logica separada."""
    return taxa_empirica(valores_h2h, limiar)


def avaliar_selecao(resultado_taxa_empirica, odd_oferecida):
    """Compara o limite INFERIOR de Wilson (nao a taxa bruta - e o numero
    defensavel) contra a probabilidade implicita da odd oferecida hoje.

    Retorna dict com prob_conservadora, prob_implicita_odd, edge, ev,
    veredito (texto). N pequeno (tipico aqui, ~10) faz o wilson_lo cair
    bem abaixo da taxa bruta quando a amostra e curta - e o proposito:
    nao deixar um "8/10" parecer mais forte do que a amostra sustenta.
    """
    prob_conservadora = resultado_taxa_empirica["wilson_lo"]
    prob_implicita = 1.0 / odd_oferecida
    edge = prob_conservadora - prob_implicita
    ev = ev_unitario(prob_conservadora, odd_oferecida)
    if resultado_taxa_empirica["n"] < 5:
        veredito = "amostra insuficiente (N<5) - nao decidir so com isto"
    elif ev > 0:
        veredito = "EV positivo pelo limite inferior de Wilson - candidato"
    else:
        veredito = "sem EV pelo limite inferior de Wilson - nao recomendar"
    return {
        "n": resultado_taxa_empirica["n"],
        "k": resultado_taxa_empirica["k"],
        "taxa_bruta": resultado_taxa_empirica["taxa"],
        "prob_conservadora": prob_conservadora,
        "prob_implicita_odd": prob_implicita,
        "edge": edge,
        "ev": ev,
        "odd_oferecida": odd_oferecida,
        "veredito": veredito,
    }


def _demo():
    print("== Reproduzindo o exemplo do usuario: escanteios ==")
    # "nos ultimos 10 jogos o time conseguiu pelo menos em 8 jogos +8 escanteios"
    ultimos_10 = [10, 9, 10, 11, 9, 8, 9, 7, 10, 9]  # 8 dos 10 valores > 8
    r = taxa_empirica(ultimos_10, limiar=8)
    print(f"ultimos 10 jogos: {ultimos_10}")
    print(f"acima de 8 escanteios: {r['k']}/{r['n']} = {r['taxa']:.0%} "
          f"[Wilson 95%: {r['wilson_lo']:.1%}-{r['wilson_hi']:.1%}]")
    assert r["k"] == 8 and r["n"] == 10, "contagem do exemplo deveria ser 8/10"

    av = avaliar_selecao(r, odd_oferecida=1.65)
    print(f"\nodd oferecida: 1.65 (implica {av['prob_implicita_odd']:.1%})")
    print(f"probabilidade conservadora (Wilson inf.): {av['prob_conservadora']:.1%}")
    print(f"edge: {av['edge']:+.1%} | EV: {av['ev']:+.3f}u | veredito: {av['veredito']}")

    print("\n== Combinando com uma segunda perna (gols) ==")
    ultimos_10_gols = [3, 2, 1, 4, 2, 3, 2, 1, 3, 2]  # 8 dos 10 > 1.5
    r_gols = taxa_empirica(ultimos_10_gols, limiar=1.5)
    av_gols = avaliar_selecao(r_gols, odd_oferecida=1.20)
    print(f"gols: {r_gols['k']}/{r_gols['n']} > 1.5 [Wilson inf {r_gols['wilson_lo']:.1%}] "
          f"@1.20 -> EV {av_gols['ev']:+.3f}u")

    odds = [av["odd_oferecida"], av_gols["odd_oferecida"]]
    probs = [av["prob_conservadora"], av_gols["prob_conservadora"]]
    print(f"\nodd combinada: {odd_combinada(odds):.2f}")
    print(f"prob combinada (conservadora): {prob_combinada(probs):.1%}")
    print(f"EV combinada: {ev_combinada(probs, odds):+.3f}u")
    print("\nLEMBRETE: independencia validada empiricamente so entre CATEGORIAS")
    print("DIFERENTES (ver betting_model.prob_combinada) - nunca combinar mercados")
    print("que descrevem o mesmo desfecho subjacente (ex. Over gols + BTTS).")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_file", nargs="?")
    ap.add_argument("--coluna", choices=COLUNAS_NUMERICAS)
    ap.add_argument("--limiar", type=float)
    ap.add_argument("--odd", type=float)
    ap.add_argument("--demo", action="store_true")
    args = ap.parse_args()

    if args.demo:
        _demo()
        return 0

    if not (args.csv_file and args.coluna and args.limiar is not None):
        ap.error("informe csv_file + --coluna + --limiar (ou use --demo)")

    linhas = carrega_forma(args.csv_file)
    valores = [l[args.coluna] for l in linhas]
    r = taxa_empirica(valores, args.limiar)
    print(f"=== {args.csv_file} | {args.coluna} > {args.limiar} ===")
    print(f"{r['k']}/{r['n']} jogos = {r['taxa']:.1%} "
          f"[Wilson 95%: {r['wilson_lo']:.1%}-{r['wilson_hi']:.1%}]")
    if args.odd:
        av = avaliar_selecao(r, args.odd)
        print(f"odd {args.odd} (implica {av['prob_implicita_odd']:.1%}) -> "
              f"edge {av['edge']:+.1%} | EV {av['ev']:+.3f}u | {av['veredito']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
