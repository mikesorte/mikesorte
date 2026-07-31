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
# data explicita no formato do worldfootball: "01.08.2026 16:00"
RE_DATA = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")


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

        # janela ANTES do link: contem horario, data (quando a pagina traz) e
        # placar ("-:-" = ainda nao jogou)
        janela = texto[max(0, m.start() - 400):m.start()]
        horas = RE_HORA.findall(janela)
        placares = RE_PLACAR.findall(texto[max(0, m.start() - 60):m.end() + 60])

        # BUG REAL pego em 31/07: paginas de classificacao/tabela trazem jogos
        # de OUTRAS datas ("01.08.2026 16:00"). Fundir esses dumps com o de
        # matches-today rotulava jogo de amanha como de hoje - erro de
        # identidade (regra 0 da metodologia). Se a pagina declara a data,
        # respeitar; se nao declara (matches-today), fica None = data do dump.
        md = RE_DATA.findall(janela)
        data_iso = None
        if md:
            dd, mm, aaaa = md[-1]
            data_iso = f"{aaaa}-{mm}-{dd}"

        jogos.append(dict(
            competicao=humanizar(m.group("comp")),
            casa=humanizar(casa),
            fora=humanizar(fora),
            hora=horas[-1] if horas else None,
            placar=placares[0] if placares else None,
            data=data_iso,
        ))
    return jogos


# URL do tipo .../matches-today/dn2026-07-31/ implica a data de TODOS os
# jogos daquela pagina, que nao repete a data por jogo.
RE_URL_DATA = re.compile(r"/matches-today/dn(\d{4}-\d{2}-\d{2})")


def carregar(caminho):
    """Devolve [(url, conteudo, data_implicita)] - NUNCA funde as paginas.

    Fundir era o bug de 31/07: a pagina de classificacao traz jogos de outras
    datas e, misturada ao dump de matches-today, fazia jogo de amanha ser
    reportado como de hoje.
    """
    with open(caminho, encoding="utf-8") as f:
        bruto = f.read()
    try:
        d = json.loads(bruto)
        fontes = []
        for r in d.get("results", []):
            url = r.get("url", "")
            conteudo = r.get("raw_content") or r.get("content") or ""
            m = RE_URL_DATA.search(url)
            fontes.append((url, conteudo, m.group(1) if m else None))
        if fontes:
            return fontes
    except json.JSONDecodeError:
        pass
    return [("(texto solto)", bruto, None)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dump")
    ap.add_argument("--so-agendados", action="store_true",
                    help="ocultar jogos ja encerrados (placar preenchido)")
    ap.add_argument("--data", metavar="YYYY-MM-DD",
                    help=("manter apenas jogos desta data. Jogos sem data "
                          "explicita na pagina sao mantidos (vem do dump de "
                          "matches-today). OBRIGATORIO quando o dump mistura "
                          "paginas de tabela/classificacao, que trazem outras "
                          "datas - ver bug de 31/07"))
    args = ap.parse_args()

    jogos = []
    for url, conteudo, data_implicita in carregar(args.dump):
        for j in parse_dump(conteudo):
            # a data da pagina (quando a URL a declara) preenche o que o jogo
            # nao traz; jogo com data propria mantem a sua
            if j["data"] is None:
                j["data"] = data_implicita
            j["fonte"] = url
            jogos.append(j)

    if args.so_agendados:
        jogos = [j for j in jogos if j["placar"] in (None, "-:-")]
    if args.data:
        # ESTRITO: jogo sem data determinavel NAO entra. Deixar passar foi o
        # que trouxe jogos de outros dias no bug de 31/07.
        jogos = [j for j in jogos if j["data"] == args.data]

    # o mesmo jogo costuma aparecer em mais de uma pagina do dump
    unicos, vistos = [], set()
    for j in jogos:
        k = (j["competicao"], j["casa"], j["fora"], j["data"])
        if k not in vistos:
            vistos.add(k)
            unicos.append(j)
    jogos = unicos

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
