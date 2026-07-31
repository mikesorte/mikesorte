#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extrai jogos + odds 1X2 de um PDF exportado da casa de apostas (v19).

MOTIVACAO: em 31/07 foi verificado que TODOS os canais de leitura de pagina
estao bloqueados neste ambiente:
  - Nimble / Exa / Tavily: conectores desabilitados no chat (nao carregam)
  - WebFetch: 403 em qualquer host (Betano, worldfootball, Wikipedia)
  - curl / wget / urllib: 403 CONNECT no proxy (so pypi e npm passam)
  - Playwright/Chromium: ERR_TUNNEL_CONNECTION_FAILED
A politica de rede e uma ALLOWLIST de hosts. Nao adianta converter a pagina
em PDF do lado de ca: a falha e no FETCH, nao na renderizacao - nao chega
um byte do host.

O que FUNCIONA e o usuario trazer a pagina para dentro: em 29/07 o usuario
exportou a home da Betano em PDF e anexou no chat; a leitura funcionou e
rendeu ~25 jogos com odds. Este script transforma aquele esforco manual
pontual em pipeline repetivel.

FLUXO DE USO:
  1. usuario abre a pagina da casa (home, hub de futebol, ou pagina de um
     jogo) e usa Imprimir -> Salvar como PDF
  2. anexa o PDF no chat, OU salva no Google Drive (conector ativo)
  3. python3 scripts/parse_odds_pdf.py <arquivo.pdf>

Saida: tabela de eventos com times, competicao/horario quando detectavel, e
odds 1X2, ja com devig_power() aplicado quando os 3 lados existem.

Dependencia: pymupdf (pip install pymupdf) - registries de pacote sao
permitidos pela politica de rede, entao a instalacao funciona.
"""
import argparse
import os
import re
import sys

# odd decimal tipica de futebol: 1.01 a 99.0, sempre com casa decimal
RE_ODD = re.compile(r"^\d{1,2}\.\d{1,2}$")
# linhas de ruido comuns em export de PDF da casa (inclui selos promocionais,
# que ficam ENTRE a competicao e o bloco de odds e quebravam a atribuicao)
RUIDO = ("http", "página", "pagina", "betano.bet.br", "bet365", "superbet",
         "cassino", "bônus", "bonus", "promo", "cadastre", "registrar",
         "entrar", "ao vivo", "menu", "início", "inicio",
         "turbinada", "super boost", "substituição de ouro",
         "substituicao de ouro", "múltiplas", "multiplas", "mais mercados",
         "acumulador", "escolhas principais", "jogadores populares")

# linha de data/hora que delimita o inicio de um bloco de evento
RE_QUANDO = re.compile(r"(\d{1,2}/\d{1,2}\s+\d{1,2}:\d{2})|(^hoje\s+\d{1,2}:\d{2})",
                       re.IGNORECASE)


def extrair_linhas(caminho):
    try:
        import fitz  # pymupdf
    except ImportError:
        print("ERRO: pymupdf nao instalado. Rode: pip install pymupdf", file=sys.stderr)
        raise SystemExit(2)
    doc = fitz.open(caminho)
    linhas = []
    for pagina in doc:
        for ln in pagina.get_text().splitlines():
            ln = ln.strip()
            if ln:
                linhas.append(ln)
    return linhas


def eh_ruido(linha):
    b = linha.lower()
    return any(r in b for r in RUIDO)


def parse_eventos(linhas):
    """Heuristica sobre o layout de export da casa.

    Padrao observado no PDF real da Betano (29/07/2026):
        <data/hora>            ex.: '29/07 19:30' ou 'Hoje 19:00'
        <time casa>
        <time visitante>
        <competicao>           (as vezes ausente)
        '1' <odd> 'X' <odd> '2' <odd>

    A ancora confiavel e a sequencia 1/X/2 com odds - a partir dela olhamos
    para tras para recuperar times, competicao e horario.
    """
    eventos = []
    i = 0
    n = len(linhas)
    while i < n:
        # ancora: '1' seguido de odd, depois 'X' + odd, depois '2' + odd
        if (linhas[i] == "1" and i + 5 < n
                and RE_ODD.match(linhas[i + 1] or "")
                and linhas[i + 2] == "X" and RE_ODD.match(linhas[i + 3] or "")
                and linhas[i + 4] == "2" and RE_ODD.match(linhas[i + 5] or "")):
            odds = [float(linhas[i + 1]), float(linhas[i + 3]), float(linhas[i + 5])]

            # Andar para tras ate a linha de data/hora, que delimita o inicio
            # do bloco do evento. Layout real observado:
            #     <data/hora> / <time casa> / <time fora> / <competicao> /
            #     [selo promocional] / 1 <odd> X <odd> 2 <odd>
            # Ancorar na data/hora e mais confiavel que contar N linhas para
            # tras, porque a quantidade de selos varia por evento.
            hora = None
            bloco = []
            j = i - 1
            while j >= 0 and (i - j) <= 12:
                ln = linhas[j]
                if RE_QUANDO.search(ln):
                    hora = ln
                    break
                if not eh_ruido(ln) and not RE_ODD.match(ln) and ln not in ("1", "X", "2"):
                    bloco.append(ln)
                j -= 1
            bloco.reverse()

            # dentro do bloco: os dois PRIMEIROS sao os times; o que sobra e
            # competicao/observacao (ex.: "Primeiro jogo: 2-2")
            if len(bloco) >= 2:
                casa, fora = bloco[0], bloco[1]
                competicao = " | ".join(bloco[2:]) if len(bloco) > 2 else None
            elif len(bloco) == 1:
                casa, fora, competicao = bloco[0], "?", None
            else:
                casa, fora, competicao = "?", "?", None

            eventos.append(dict(casa=casa, fora=fora, competicao=competicao,
                                hora=hora, odds=odds))
            i += 6
            continue
        i += 1
    return eventos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--min-odds", type=float, default=None,
                    help="so mostrar eventos cuja menor odd seja >= este valor")
    args = ap.parse_args()

    if not os.path.exists(args.pdf):
        print(f"ERRO: arquivo nao encontrado: {args.pdf}", file=sys.stderr)
        return 2

    linhas = extrair_linhas(args.pdf)
    eventos = parse_eventos(linhas)

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        from betting_model import devig_power
    except Exception:
        devig_power = None

    print(f"=== {len(eventos)} evento(s) com 1X2 extraido(s) de {os.path.basename(args.pdf)} ===\n")
    mostrados = 0
    for e in eventos:
        if args.min_odds and min(e["odds"]) < args.min_odds:
            continue
        mostrados += 1
        titulo = f"{e['casa']} x {e['fora']}"
        meta = " | ".join(x for x in (e["competicao"], e["hora"]) if x)
        print(f"- {titulo}" + (f"  [{meta}]" if meta else ""))
        linha = f"    1X2: {e['odds']}"
        if devig_power:
            try:
                justo = devig_power(e["odds"])
                linha += "  -> justo: " + ", ".join(f"{p:.1%}" for p in justo)
            except Exception as ex:
                linha += f"  (devig recusou: {ex})"
        print(linha)

    if not eventos:
        print("Nenhum bloco 1X2 reconhecido. O layout do export pode ter mudado -")
        print("rode com o PDF em maos e ajuste parse_eventos(). Nunca inventar odds.")
    else:
        print(f"\n{mostrados} evento(s) exibido(s). Use como CATALOGO de triagem:")
        print("cruzar com scripts/league_calendar.py --prioridade para escolher")
        print("os 2-4 jogos de analise profunda (regra 8: priorizar liga menos eficiente).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
