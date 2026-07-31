#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extrai a lista GLOBAL de jogos do dia a partir de um dump do Tavily/Exa
sobre worldfootball.net/matches-today/dnYYYY-MM-DD/ (v20).

MOTIVACAO: a varredura por manchete (WebSearch em portugues) so enxerga
Brasileirao/grandes ligas - falha documentada de 31/07 (v17). O catalogo
global existe em worldfootball.net, que e server-rendered, e em 31/07 foi
verificado que `mcp__Tavily__tavily_extract` LE essa pagina com sucesso
(141k chars), enquanto falha em betano.bet.br. Exa devolve so a casca.

Ancora de parsing: a URL do match-report, que e estruturada e carrega
competicao e times:
  .../match-report/co129/norway-eliteserien/ma11796943/valerenga-if_hamarkameratene/
             ^codigo   ^competicao                      ^time casa  ^time fora

Uso:
    python3 scripts/parse_fixtures.py <dump_tavily.txt> [--so-agendados]

Cruzar a saida com `scripts/league_calendar.py --prioridade` para escolher
os 2-4 jogos de analise profunda (regra 8).
"""
import argparse
import json
import re
import sys

RE_MATCH = re.compile(
    r"https://www\.worldfootball\.net/match-report/"
    r"(?P<cod>co\d+)/(?P<comp>[a-z0-9\-]+)/ma\d+/(?P<slug>[a-z0-9\-_%\.]+)/"
)
RE_HORA = re.compile(r"(?<!\d)([0-2]?\d:[0-5]\d)(?!\d)")
RE_PLACAR = re.compile(r"\[(\d+:\d+|-:-)\]")


def humanizar(s):
    return s.replace("-", " ").strip().title()


def parse_dump(texto):
    jogos = []
    vistos = set()
    for m in RE_MATCH.finditer(texto):
        slug = m.group("slug")
        if "_" not in slug:
            continue
        casa, _, fora = slug.partition("_")
        chave = (m.group("cod"), casa, fora)
        if chave in vistos:
            continue
        vistos.add(chave)

        # janela ANTES do link: contem horario e placar ("-:-" = ainda nao jogou)
        janela = texto[max(0, m.start() - 400):m.start()]
        horas = RE_HORA.findall(janela)
        placares = RE_PLACAR.findall(texto[max(0, m.start() - 60):m.end() + 60])
        jogos.append(dict(
            competicao=humanizar(m.group("comp")),
            casa=humanizar(casa),
            fora=humanizar(fora),
            hora=horas[-1] if horas else None,
            placar=placares[0] if placares else None,
        ))
    return jogos


def carregar(caminho):
    with open(caminho, encoding="utf-8") as f:
        bruto = f.read()
    # aceita tanto o JSON do Tavily quanto texto solto
    try:
        d = json.loads(bruto)
        partes = []
        for r in d.get("results", []):
            partes.append(r.get("raw_content") or r.get("content") or "")
        return "\n".join(partes) or bruto
    except json.JSONDecodeError:
        return bruto


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dump")
    ap.add_argument("--so-agendados", action="store_true",
                    help="ocultar jogos ja encerrados (placar preenchido)")
    args = ap.parse_args()

    jogos = parse_dump(carregar(args.dump))
    if args.so_agendados:
        jogos = [j for j in jogos if j["placar"] in (None, "-:-")]

    por_comp = {}
    for j in jogos:
        por_comp.setdefault(j["competicao"], []).append(j)

    print(f"=== {len(jogos)} jogo(s) em {len(por_comp)} competicao(oes) ===\n")
    for comp in sorted(por_comp):
        print(f"-- {comp} --")
        for j in por_comp[comp]:
            estado = "" if j["placar"] in (None, "-:-") else f"  [encerrado {j['placar']}]"
            hora = j["hora"] or "--:--"
            print(f"   {hora}  {j['casa']} x {j['fora']}{estado}")
        print()

    if not jogos:
        print("Nenhum jogo reconhecido - o layout do worldfootball pode ter mudado.")
        print("Nunca inventar jogo ou odd; declarar a falha no relatorio.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
