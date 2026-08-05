#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Varredura AMPLA de odds (v15, multi-mercado desde v36). Le um dump JSON
salvo de nimble_extract sobre uma pagina de LISTAGEM da casa (home, hub de
futebol, hub de uma competicao) e extrai TODOS os eventos encontrados, nao
so o do jogo que o dump foi originalmente pedido para.

Uso:
    python3 scripts/scan_odds.py <arquivo_dump.txt> [--liga-menor-kw arquivo.txt]
    python3 scripts/scan_odds.py <arquivo_dump.txt> --csv-jogos data/dumps/AAAA-MM-DD-jogos.csv --data-brt AAAA-MM-DD

Cada evento e pareado com o competition/participants mais proximo ANTES
do bloco de mercado no JSON bruto (heuristica posicional, valida na pratica
porque a API da casa serializa evento->mercados em sequencia). Roda
devig_power() nas odds de cada evento achado e reporta um flag "LIGA MENOR"
quando o nome da competicao bate com uma lista de palavras-chave (regra 8:
valor tende a concentrar em ligas menos eficientes/liquidas).

MULTI-MERCADO (v36): ate 03/08 este script so procurava o bloco 1X2
("Resultado Final"/MRES), embora a MESMA pagina de listagem ja traga, no
mesmo JSON, sem nenhum custo extra de rede: Total de Gols (HCTG), Total de
gols - 1o Tempo (OUH1), Chance Dupla (DBLC), Empate Anula/DNB (DNOB) e
Ambas equipes Marcam/BTTS (BTSC). Medido no dump de 04/08/2026: 182 blocos
de 1X2 contra 191/191/188/186/61 desses outros 5 mercados, todos
IGNORADOS pelo parser ate agora - causa raiz real de "so conseguimos odds
1X2" (ver docs/DAILY_METHODOLOGY.md, decisao pos-v35). `parse_todos_mercados()`
extrai os 6 de uma vez; `parse_mres_blocks()` continua existindo como
wrapper fino do 1X2 (compatibilidade com pe_engine.py e chamadores
existentes).

Escanteios/cartoes NAO aparecem nesta pagina de LISTAGEM (0 blocos reais)
- mas existem, com odds reais, na pagina INDIVIDUAL do evento
(`betano.bet.br/odds/{slug}/{id}/`), confirmado em 04/08/2026 no evento
Boca Juniors x Estudiantes de La Plata: bloco "Escanteios" (type=CNOU) com
13 linhas de handicap (3.5 a 15.5) e "Total de Cartões" (type=TCOU) com 1
linha, todos com `selections`/`price` reais. Diferente dos mercados da
listagem (1 bloco = 1 linha = 2-3 selections), aqui e 1 bloco = VARIAS
linhas dentro do mesmo array de `selections` (26 selections pareadas por
handicap, no exemplo de escanteios) - por isso usa um parser dedicado,
`parse_mercados_evento()`, chamado so nos 2-4 jogos aprofundados do dia
(1 `nimble_extract` extra por jogo, nao escalavel pros ~80 elegiveis).

Isto NAO substitui a analise profunda (xG, Dixon-Coles, H2H, noticias) -
e uma TRIAGEM barata para decidir quais jogos, entre dezenas visiveis na
casa, merecem a analise profunda do dia (2-4 jogos). O objetivo e parar
de escolher jogos so pelas manchetes de noticia (que so cobrem Brasileirao/
grandes ligas) e comecar a olhar o catalogo real da casa, onde ligas
menores (Financas, Europa qualif., Argentina, etc.) aparecem mas nunca
apareceriam numa busca de noticias em portugues.
"""
import argparse
import csv
import json
import re
import sys

# v36: nomes literais confirmados campo a campo no dump real
# (data/dumps/2026-08-04-betano.json) - nao adivinhados. A chave e o rotulo
# curto usado em --csv-jogos e no restante do sistema; o valor e o "name"
# exato do bloco de mercado no JSON da Betano.
MERCADOS = {
    "1x2": "Resultado Final",
    "total_gols": "Total de Gols",
    "total_gols_1t": "Total de gols - 1° Tempo",
    "dupla_chance": "Chance Dupla",
    "dnb": "Empate Anula",
    "btts": "Ambas equipes Marcam",
}

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


def parse_market_blocks(content, market_name, casa=None):
    """Extrai todos os blocos de UM mercado (por "name" literal, ex.
    "Resultado Final", "Total de Gols" - ver dict MERCADOS) de um dump de
    pagina de LISTAGEM. Generalizado em v36 a partir do antigo
    `parse_mres_blocks` (que so sabia extrair 1X2) - mesma heuristica de
    pareamento evento<->mercado, parametrizada pelo nome do mercado.

    casa (v32, Fase 4): nome da casa de onde este dump veio (ex.
    "Betano"). Opcional (default None, mantem compatibilidade com
    chamadores existentes que nao sabem/nao precisam da casa) - mas
    OBRIGATORIO para casa_matcher.py conseguir cruzar fixtures entre dumps
    de casas diferentes (line-shopping real, ver docs/DAILY_METHODOLOGY.md
    v32 regra 9)."""
    events = []
    for idx in find_all(content, f'"name":"{market_name}"'):
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
            "handicap": market.get("handicap"),
            "competition": league_m[-1] if league_m else None,
            "participants": evname_m[-1] if evname_m else None,
            "start_time": time_m[-1] if time_m else None,
            "casa": casa,
        })
    return events


def parse_mres_blocks(content, casa=None):
    """Wrapper fino de compatibilidade - so 1X2. Chamadores existentes
    (pe_engine.py, etc.) continuam funcionando sem mudanca nenhuma."""
    return parse_market_blocks(content, MERCADOS["1x2"], casa=casa)


def parse_todos_mercados(content, casa=None):
    """v36: extrai os 6 mercados conhecidos de uma vez (dict MERCADOS).
    Devolve {chave_mercado: [eventos]} - cada lista de eventos tem o mesmo
    formato de parse_market_blocks(). Pareamento entre mercados do MESMO
    jogo e feito por quem consome isto, casando (participants, start_time)
    - todos os mercados de um evento compartilham essa metadata porque sao
    extraidos com a mesma janela de contexto."""
    return {chave: parse_market_blocks(content, nome, casa=casa)
            for chave, nome in MERCADOS.items()}


# v36 (Tier 3) - mercados de LINHA MULTIPLA, so na pagina INDIVIDUAL do
# evento (betano.bet.br/odds/{slug}/{id}/), nao na listagem. Formato
# diferente do resto: 1 bloco = VARIAS linhas de handicap dentro do MESMO
# array de selections (ex.: "Mais de 8.5"/"Menos de 8.5"/"Mais de
# 9.5"/... tudo junto), em vez de 1 bloco por linha como Total de Gols.
# Confirmado em 04/08/2026 (Boca Juniors x Estudiantes de La Plata):
# "Escanteios" (type=CNOU) com 13 linhas reais (3.5 a 15.5), "Total de
# Cartões" (type=TCOU) com 1 linha (6.5). Nomes literais:
MERCADOS_EVENTO = {
    "escanteios": "Escanteios",
    "cartoes": "Total de Cartões",
}

RE_LINHA_OU = re.compile(r"^(Mais|Menos) de (\d+(?:\.\d+)?)$")


def parse_mercados_evento(content, market_name, casa=None):
    """Extrai um mercado de linha multipla de uma pagina INDIVIDUAL de
    evento (uma pagina = um jogo so, entao nao precisa da heuristica de
    'objeto mais proximo antes do bloco' - a competicao/participantes/
    horario valem pra pagina inteira). Devolve UM dict (nao lista, so ha
    um evento na pagina):
        {"linhas": [{"handicap": 8.5, "odd_mais": 1.65, "odd_menos": 2.15}, ...],
         "competition":..., "participants":..., "start_time":..., "casa":...}
    ou None se o mercado nao apareceu (bloco de categoria sem selections
    reais tambem conta como ausente - ex. o "Cartões" tipo="cards" que so
    e uma aba de navegacao, sem odds)."""
    linhas_por_handicap = {}
    for idx in find_all(content, f'"name":"{market_name}"'):
        obj_start = content.rfind("{", 0, idx)
        blob = extract_json_obj(content, obj_start)
        if not blob:
            continue
        try:
            market = json.loads(blob)
        except json.JSONDecodeError:
            continue
        for s in market.get("selections", []):
            nome_sel = s.get("name") or ""
            preco = s.get("price")
            m = RE_LINHA_OU.match(nome_sel)
            if not m or preco is None:
                continue
            direcao, valor = m.group(1), float(m.group(2))
            entry = linhas_por_handicap.setdefault(valor, {"handicap": valor, "odd_mais": None, "odd_menos": None})
            if direcao == "Mais":
                entry["odd_mais"] = preco
            else:
                entry["odd_menos"] = preco

    linhas = [v for v in linhas_por_handicap.values() if v["odd_mais"] and v["odd_menos"]]
    if not linhas:
        return None
    linhas.sort(key=lambda v: v["handicap"])

    league_m = re.findall(r'"leagueName":"([^"]+)"', content)
    evname_m = re.findall(r'"shortName":"([^"]+)","startTime"', content) or \
        re.findall(r'"name":"([^"]+)","startTime"', content)
    time_m = re.findall(r'"startTime":(\d+)', content)
    return {
        "linhas": linhas,
        "competition": league_m[0] if league_m else None,
        "participants": evname_m[0] if evname_m else None,
        "start_time": time_m[0] if time_m else None,
        "casa": casa,
    }


def parse_todos_mercados_evento(content, casa=None):
    """v36: os 2 mercados de linha multipla conhecidos (MERCADOS_EVENTO)
    de uma pagina individual de evento. Devolve {chave: dict_ou_None}."""
    return {chave: parse_mercados_evento(content, nome, casa=casa)
            for chave, nome in MERCADOS_EVENTO.items()}


def chave_evento(ev):
    """Chave de pareamento entre mercados do mesmo jogo (v36)."""
    return (ev.get("participants"), ev.get("start_time"))


def is_liga_menor(competition, keywords):
    if not competition:
        return False
    c = competition.lower()
    return any(kw in c for kw in keywords)


# ---------------------------------------------------------------- filtros v24
# A extracao bruta da casa traz MUITA coisa fora de escopo. Auditoria de
# 01/08 sobre 542 eventos reais: 64 femininos (decisao 9 do usuario exclui),
# 43 base/reserva, 64 de outro dia BRT, 92 ja iniciados. So 325 (60%) eram
# elegiveis de verdade. Sem estes filtros o "catalogo" engana: parece
# cobertura, mas 40% nao pode virar aposta.

RE_FEMININO = re.compile(r"\(F\)|femin|\bwomen\b|\bladies\b|\bfem\b", re.I)

# CUIDADO: "Junior"/"Juniors" NAO entra aqui - Argentinos Juniors e Atletico
# Junior sao clubes ADULTOS. Filtro inicial os pegava por engano e teria
# descartado jogos legitimos. Marcadores confiaveis de base/reserva:
RE_BASE = re.compile(
    r"\bU\s?1[5-9]\b|\bU\s?2[0-3]\b|\bsub[- ]?\d{2}\b|\byouth\b|\bjuvenil\b"
    r"|\breserve[s]?\b|\bacademy\b|\bfuerzas basicas\b",
    re.I)
# sufixo de time reserva ("Hannover 96 II", "Real Madrid B") - precisa ser
# testado em CADA time isoladamente. Testar na string concatenada
# (participants + competition) quebra a ancora de fim, bug pego em 01/08.
RE_SUFIXO_RESERVA = re.compile(r"\s(?:II|B)$", re.I)

# regra 0 manda evitar amistoso de pre-temporada: escalacao imprevisivel,
# rotacao pesada, motivacao baixa - o modelo nao tem como capturar isso.
# Em 01/08 eram 49 dos 542 eventos (9%), quase 12% dos elegiveis.
RE_AMISTOSO = re.compile(r"\bamistos|\bfriendly|\bfriendlies|pre-?season|pre-?temporada", re.I)


def eh_amistoso(ev):
    return bool(RE_AMISTOSO.search(ev.get("competition") or ""))


def eh_feminino(ev):
    txt = f"{ev.get('participants') or ''} {ev.get('competition') or ''}"
    return bool(RE_FEMININO.search(txt))


def eh_base_ou_reserva(ev):
    part = ev.get("participants") or ""
    txt = f"{part} {ev.get('competition') or ''}"
    if RE_BASE.search(txt):
        return True
    # sufixo II/B avaliado por TIME, nao na string inteira
    for time in part.split(" - "):
        if RE_SUFIXO_RESERVA.search(time.strip()):
            return True
    return False


def filtrar_elegiveis(eventos, data_brt=None, agora_ms=None):
    """Aplica as regras de escopo do usuario sobre o catalogo bruto.

    Descarta: feminino (decisao 9), base/reserva (dado fraco), jogo de outro
    dia em horario de BRASILIA (regra 0 - 'UTC engana') e jogo ja iniciado
    (regra 0 - 'nunca analisar jogo encerrado').

    Devolve (elegiveis, motivos) onde motivos e um dict com as contagens.
    """
    from datetime import datetime, timedelta, timezone
    BRT = timezone(timedelta(hours=-3))
    hoje = data_brt or datetime.now(BRT).date().isoformat()
    corte = agora_ms if agora_ms is not None else datetime.now(BRT).timestamp() * 1000

    elegiveis, motivos = [], {"feminino": 0, "base_reserva": 0, "amistoso": 0,
                              "outro_dia": 0, "ja_iniciado": 0}
    for ev in eventos:
        if eh_feminino(ev):
            motivos["feminino"] += 1
            continue
        if eh_base_ou_reserva(ev):
            motivos["base_reserva"] += 1
            continue
        if eh_amistoso(ev):
            motivos["amistoso"] += 1
            continue
        ts = ev.get("start_time")
        if ts:
            dt = datetime.fromtimestamp(int(ts) / 1000, tz=BRT)
            if dt.date().isoformat() != hoje:
                motivos["outro_dia"] += 1
                continue
            # <= e nao < : jogo comecando EXATAMENTE agora tambem esta fora.
            # Nao da para entrar pre-jogo no instante do apito, e a regra 0
            # ("nunca analisar jogo encerrado") vale desde o inicio da partida.
            # Bug encontrado pela suite adversarial (test_extraction.py, v26).
            if int(ts) <= corte:
                motivos["ja_iniciado"] += 1
                continue
        elegiveis.append(ev)
    return elegiveis, motivos


def _devig_seguro(devig_power, odds):
    try:
        return devig_power(odds)
    except Exception:
        return None


def _quando_fmt(start_time):
    if not start_time:
        return "?"
    import datetime
    return datetime.datetime.fromtimestamp(int(start_time) / 1000, tz=datetime.timezone.utc).strftime("%d/%m %H:%M UTC")


# v36: nomes de coluna do 1X2 no --csv-jogos ficam com o rotulo LEGADO
# (odd_1/odd_x/odd_2, ja usado por scripts/generate_report.py desde v31)
# em vez do prefixo generico "odd_1x2_N" - evita quebrar o consumidor
# existente do quadro-resumo. Mercados novos usam o prefixo generico.
_COLUNAS_1X2_LEGADO = ["odd_1", "odd_x", "odd_2", "justo_1", "justo_x", "justo_2"]


def escreve_csv_jogos(caminho, eleg_1x2, indices_outros, devig_power):
    """v36: persiste o CSV de jogos elegiveis com odds+justo dos 6
    mercados (antes disto, essa montagem era feita a mao, turno a turno,
    num script solto - o mesmo erro que a decisao v26 ja tinha corrigido
    pra dumps brutos, so que pro CSV derivado)."""
    campos = ["confronto", "competicao", "horario_brt", "casa"] + _COLUNAS_1X2_LEGADO
    for chave in MERCADOS:
        if chave == "1x2":
            continue
        campos.append(f"linha_{chave}")
        campos += [f"odd_{chave}_{i}" for i in range(3)] + [f"justo_{chave}_{i}" for i in range(3)]

    linhas = []
    for e in eleg_1x2:
        row = {c: "" for c in campos}
        row["confronto"] = e["participants"] or ""
        row["competicao"] = e["competition"] or ""
        row["horario_brt"] = _quando_fmt_brt(e["start_time"])
        row["casa"] = e.get("casa") or ""

        fair_1x2 = _devig_seguro(devig_power, e["odds"])
        for i, nome in enumerate(("odd_1", "odd_x", "odd_2")):
            if i < len(e["odds"]):
                row[nome] = e["odds"][i]
        if fair_1x2:
            for i, nome in enumerate(("justo_1", "justo_x", "justo_2")):
                if i < len(fair_1x2):
                    row[nome] = f"{fair_1x2[i]:.3f}"

        chv = chave_evento(e)
        for chave in MERCADOS:
            if chave == "1x2":
                continue
            ev_mercado = indices_outros.get(chave, {}).get(chv)
            if not ev_mercado:
                continue
            if ev_mercado.get("handicap"):
                row[f"linha_{chave}"] = ev_mercado["handicap"]
            fair = _devig_seguro(devig_power, ev_mercado["odds"])
            for i, odd in enumerate(ev_mercado["odds"][:3]):
                row[f"odd_{chave}_{i}"] = odd
            if fair:
                for i, p in enumerate(fair[:3]):
                    row[f"justo_{chave}_{i}"] = f"{p:.3f}"
        linhas.append(row)

    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(linhas)
    return len(linhas)


def _quando_fmt_brt(start_time):
    if not start_time:
        return ""
    import datetime
    dt = datetime.datetime.fromtimestamp(int(start_time) / 1000, tz=datetime.timezone.utc) - datetime.timedelta(hours=3)
    return dt.strftime("%d/%m %H:%M")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dump_file")
    ap.add_argument("--liga-menor-kw", default=None)
    ap.add_argument("--casa", default=None,
                    help="nome da casa de origem do dump (v32, p/ line-shopping)")
    ap.add_argument("--csv-jogos", default=None,
                    help="v36: grava o CSV de jogos elegiveis (6 mercados) neste caminho, em vez de so imprimir")
    ap.add_argument("--data-brt", default=None,
                    help="data (AAAA-MM-DD) usada por filtrar_elegiveis/--csv-jogos; default hoje BRT")
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
    import datetime

    todos = parse_todos_mercados(content, casa=args.casa)
    events = todos["1x2"]

    # indices para achar rapido o bloco de cada mercado secundario do MESMO
    # jogo, casando por (participants, start_time) - v36
    indices_outros = {
        chave: {chave_evento(ev): ev for ev in lista}
        for chave, lista in todos.items() if chave != "1x2"
    }

    print(f"=== VARREDURA AMPLA: {len(events)} evento(s) com 1X2 encontrado(s) no dump "
          f"({args.casa or 'casa nao informada'}) ===")
    for chave, lista in todos.items():
        if chave != "1x2":
            print(f"    (+ {len(lista)} bloco(s) de {MERCADOS[chave]})")
    print()
    for e in events:
        fair = _devig_seguro(devig_power, e["odds"])
        tag = "LIGA MENOR" if is_liga_menor(e["competition"], keywords) else ""
        label = e["participants"] or "?"
        when = _quando_fmt(e["start_time"])
        print(f"- {label} | {e['competition'] or '?'} | {when} {tag}")
        print(f"  1X2: {e['odds']}", end="")
        if fair:
            print(f" -> justo: {[f'{p:.1%}' for p in fair]}")
        else:
            print(" -> devig falhou (dado suspeito)")
        chv = chave_evento(e)
        for chave, idx in indices_outros.items():
            ev2 = idx.get(chv)
            if not ev2:
                continue
            fair2 = _devig_seguro(devig_power, ev2["odds"])
            rotulo = MERCADOS[chave]
            linha_odds = " / ".join(f"{n}={o}" for n, o in zip(ev2["names"], ev2["odds"]))
            print(f"  {rotulo}: {linha_odds}", end="")
            if fair2:
                print(f" -> justo: {[f'{p:.1%}' for p in fair2]}")
            else:
                print()

    if args.csv_jogos:
        data_brt = args.data_brt
        eleg, motivos = filtrar_elegiveis(events, data_brt=data_brt)
        n = escreve_csv_jogos(args.csv_jogos, eleg, indices_outros, devig_power)
        print(f"\n=== --csv-jogos: {n} jogo(s) elegivel(is) gravado(s) em {args.csv_jogos} "
              f"(motivos de descarte: {motivos}) ===")

    return 0


if __name__ == "__main__":
    sys.exit(main())
