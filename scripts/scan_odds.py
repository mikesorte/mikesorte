#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Varredura AMPLA de odds (v15). Le um dump JSON salvo de nimble_extract
sobre uma pagina de LISTAGEM da casa (home, hub de futebol, hub de uma
competicao) e extrai TODOS os eventos com mercado 1X2 (MRES) encontrados,
nao so o do jogo que o dump foi originalmente pedido para.

Uso:
    python3 scripts/scan_odds.py <arquivo_dump.txt> [--liga-menor-kw arquivo.txt]

Cada evento e pareado com o competition/participants mais proximo ANTES
do bloco de mercado no JSON bruto (heuristica posicional, valida na pratica
porque a API da casa serializa evento->mercados em sequencia). Roda
devig_power() no 1X2 de cada evento achado e reporta um flag "LIGA MENOR"
quando o nome da competicao bate com uma lista de palavras-chave (regra 8:
valor tende a concentrar em ligas menos eficientes/liquidas).

Isto NAO substitui a analise profunda (xG, Dixon-Coles, H2H, noticias) -
e uma TRIAGEM barata para decidir quais jogos, entre dezenas visiveis na
casa, merecem a analise profunda do dia (2-4 jogos). O objetivo e parar
de escolher jogos so pelas manchetes de noticia (que so cobrem Brasileirao/
grandes ligas) e comecar a olhar o catalogo real da casa, onde ligas
menores (Financas, Europa qualif., Argentina, etc.) aparecem mas nunca
apareceriam numa busca de noticias em portugues.
"""
import argparse
import json
import re
import sys

LIGA_MENOR_DEFAULT = [
    "qualifica", "kakkonen", "ykkonen", "2. liga", "2 liga", "iii liga",
    "segunda divis", "reserve", "ii", "youth", "sub-20", "sub-23",
    "amistoso", "friendly", "liga profesional", "primera b", "primera c",
    "challenger", "conference league", "europa league", "champions league - qualif",
]


def find_all(content, needle):
    idx = 0
    out = []
    while True:
        i = content.find(needle, idx)
        if i == -1:
            break
        out.append(i)
        idx = i + 1
    return out


def extract_json_obj(content, start):
    """Anda a partir de 'start' (posicao de um '{') ate achar o '}' que fecha,
    contando chaves e ignorando as que estao dentro de strings."""
    depth = 0
    in_str = False
    esc = False
    i = start
    n = len(content)
    while i < n:
        c = content[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return content[start:i + 1]
        i += 1
    return None


def parse_mres_blocks(content):
    events = []
    for idx in find_all(content, '"name":"Resultado Final"'):
        # o objeto do mercado comeca no '{' mais proximo antes de idx
        obj_start = content.rfind("{", 0, idx)
        blob = extract_json_obj(content, obj_start)
        if not blob:
            continue
        try:
            market = json.loads(blob)
        except json.JSONDecodeError:
            continue
        sels = market.get("selections", [])
        if len(sels) < 2:
            continue
        odds = [s.get("price") for s in sels]
        names = [s.get("fullName") or s.get("name") for s in sels]
        if any(o is None for o in odds):
            continue
        # contexto: procurar league/evento/horario nos 6000 chars antes do bloco
        # (schema real da casa: event.leagueName, event.name, event.startTime em epoch ms)
        window = content[max(0, obj_start - 6000):obj_start]
        league_m = re.findall(r'"leagueName":"([^"]+)"', window)
        evname_m = re.findall(r'"shortName":"([^"]+)"', window) or re.findall(r'"name":"([^"]+)","startTime"', window)
        time_m = re.findall(r'"startTime":(\d+)', window)
        events.append({
            "odds": odds,
            "names": names,
            "competition": league_m[-1] if league_m else None,
            "participants": evname_m[-1] if evname_m else None,
            "start_time": time_m[-1] if time_m else None,
        })
    return events


def is_liga_menor(competition, keywords):
    if not competition:
        return False
    c = competition.lower()
    return any(kw in c for kw in keywords)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dump_file")
    ap.add_argument("--liga-menor-kw", default=None)
    args = ap.parse_args()

    with open(args.dump_file, encoding="utf-8") as f:
        data = json.load(f)
    content = data["content"]

    keywords = list(LIGA_MENOR_DEFAULT)
    if args.liga_menor_kw:
        with open(args.liga_menor_kw, encoding="utf-8") as f:
            keywords += [l.strip().lower() for l in f if l.strip()]

    sys.path.insert(0, "scripts")
    from betting_model import devig_power

    events = parse_mres_blocks(content)
    print(f"=== VARREDURA AMPLA: {len(events)} evento(s) com 1X2 encontrado(s) no dump ===\n")
    for e in events:
        try:
            fair = devig_power(e["odds"])
        except Exception as ex:
            fair = None
        tag = "LIGA MENOR" if is_liga_menor(e["competition"], keywords) else ""
        label = e["participants"] or "?"
        when = "?"
        if e["start_time"]:
            import datetime
            when = datetime.datetime.fromtimestamp(int(e["start_time"]) / 1000, tz=datetime.timezone.utc).strftime("%d/%m %H:%M UTC")
        print(f"- {label} | {e['competition'] or '?'} | {when} {tag}")
        print(f"  odds 1X2: {e['odds']}", end="")
        if fair:
            print(f" -> justo: {[f'{p:.1%}' for p in fair]}")
        else:
            print(" -> devig falhou (dado suspeito)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
