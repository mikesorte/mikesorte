#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Log de disponibilidade dos conectores MCP + recomendacao de horario (v22).

PROBLEMA QUE ISTO RESOLVE
-------------------------
A trigger diaria roda as 05h BRT (08h UTC). Em 31/07 os conectores
Nimble/Tavily/Exa estavam FORA as 05h, voltaram por volta das 09h40 UTC
(unica janela do dia em que a extracao funcionou - Tavily leu worldfootball
com 141k chars) e cairam de novo por volta das 10h. Ficaram fora o resto do
dia inteiro, ate 21h49 UTC.

Ou seja: o horario fixo da execucao diaria foi escolhido por conveniencia
humana (05h BRT), nunca por evidencia de quando as ferramentas funcionam.
Isso faz o sistema perder dias inteiros por azar de timing.

Este modulo acumula a evidencia: cada checagem de conector vira uma linha
com timestamp UTC e estado. Depois de alguns dias, `--janelas` mostra em
QUAIS HORAS do dia os conectores costumam estar no ar, e a trigger pode ser
movida para la - decisao por dado, nao por chute.

Uso:
    python3 scripts/connector_log.py --registrar nimble=fora tavily=fora exa=fora
    python3 scripts/connector_log.py --janelas
    python3 scripts/connector_log.py --recomendar
"""
import argparse
import csv
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "data/connector_log.csv")
COLUNAS = ["timestamp_utc", "hora_utc", "nimble", "tavily", "exa", "nota"]
ESTADOS = ("ok", "fora")


def _garantir():
    if not os.path.exists(LOG):
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(COLUNAS)


def registrar(nimble, tavily, exa, nota="", quando=None):
    """quando: ISO-8601 UTC para observacao RETROATIVA (ex.: preencher o que
    foi observado mais cedo no dia). Sem isso, usa a hora atual.

    Bug real pego em 31/07: registrar 4 observacoes do dia inteiro de uma vez
    carimbava todas com a hora atual (21h), fazendo o log dizer que 21h tinha
    disponibilidade quando na verdade a unica janela foi ~09h40. Log com hora
    errada e pior que log nenhum - ele orientaria a trigger para a hora errada.
    """
    for nome, v in (("nimble", nimble), ("tavily", tavily), ("exa", exa)):
        if v not in ESTADOS:
            raise ValueError(f"{nome}={v} invalido; use um de {ESTADOS}")
    _garantir()
    if quando:
        ts = datetime.fromisoformat(quando)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
    else:
        ts = datetime.now(timezone.utc)
    with open(LOG, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([ts.isoformat(timespec="seconds"),
                                ts.hour, nimble, tavily, exa, nota])


def ler():
    if not os.path.exists(LOG):
        return []
    with open(LOG, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def por_hora():
    """{hora_utc: (checagens_com_algum_ok, total_checagens)}"""
    agreg = defaultdict(lambda: [0, 0])
    for r in ler():
        try:
            h = int(r["hora_utc"])
        except (TypeError, ValueError):
            continue
        algum_ok = any(r.get(c) == "ok" for c in ("nimble", "tavily", "exa"))
        agreg[h][1] += 1
        if algum_ok:
            agreg[h][0] += 1
    return {h: tuple(v) for h, v in sorted(agreg.items())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--registrar", nargs="*", metavar="conector=estado")
    ap.add_argument("--janelas", action="store_true")
    ap.add_argument("--recomendar", action="store_true")
    args = ap.parse_args()

    if args.registrar:
        kv = dict(p.split("=", 1) for p in args.registrar)
        registrar(kv.get("nimble", "fora"), kv.get("tavily", "fora"),
                  kv.get("exa", "fora"), kv.get("nota", ""),
                  kv.get("quando"))
        print("registrado")
        return 0

    dados = por_hora()
    if args.janelas or args.recomendar:
        if not dados:
            print("Sem checagens registradas ainda.")
            print("Registre em TODA execucao diaria - e assim que o sistema")
            print("descobre a janela real em que as ferramentas funcionam.")
            return 0

    if args.janelas:
        print("=== DISPONIBILIDADE POR HORA UTC (fonte: data/connector_log.csv) ===")
        print("(hora UTC = hora BRT + 3)\n")
        for h, (ok, tot) in dados.items():
            barra = "#" * int(round(10 * ok / tot)) if tot else ""
            print(f"  {h:02d}:00 UTC ({(h-3) % 24:02d}h BRT)  {ok}/{tot} com algum conector no ar  {barra}")
        return 0

    if args.recomendar:
        candidatos = [(ok / tot, tot, h) for h, (ok, tot) in dados.items() if tot]
        candidatos.sort(reverse=True)
        total_checagens = sum(t for _, t in dados.values())
        print("=== RECOMENDACAO DE HORARIO DA TRIGGER ===")
        if total_checagens < 15:
            print(f"AMOSTRA PEQUENA ({total_checagens} checagens). Nao mudar o")
            print("horario ainda - continuar coletando. Isto e so contexto.")
        melhor_taxa, melhor_tot, melhor_h = candidatos[0]
        print(f"\nMelhor janela observada: {melhor_h:02d}:00 UTC "
              f"({(melhor_h-3) % 24:02d}h BRT) - {melhor_taxa:.0%} de {melhor_tot} checagem(ns)")
        print("\nRegra: so mover a trigger com amostra >=15 checagens E uma")
        print("janela claramente melhor. Caso contrario, manter e seguir")
        print("usando o protocolo de re-checagem (v21).")
        return 0

    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
