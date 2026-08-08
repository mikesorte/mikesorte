#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Calendario de ligas e triagem de candidatos (v17).

MOTIVACAO (falha real de 31/07/2026): a execucao diaria declarou "dia fraco,
1 jogo elegivel" numa sexta-feira em que existiam DEZENAS de jogos (Eliteserien,
Meistriliiga estoniana, Ykkosliiga finlandesa, Welsh Premier, Equador,
El Salvador, MLS, Scottish Premiership, qualificatorias UEFA). Causa raiz: a
descoberta de jogos era feita por WebSearch em portugues ("jogos de futebol
hoje"), que retorna NOTICIA brasileira - e noticia brasileira so cobre
Brasileirao/grandes ligas. As ligas que a propria regra 8 diz serem as mais
promissoras (menos eficientes) sao justamente as que nunca aparecem em
manchete: escandinavas, balticas, irlandesa, islandesa.

Este modulo resolve a parte do problema que NAO depende de rede: saber
o que PROCURAR. O conhecimento de quais ligas estao em temporada em cada mes,
o quao eficiente e cada mercado, a qualidade de dado disponivel e se as casas
brasileiras licenciadas costumam precificar aquela liga fica codificado aqui,
versionado e testavel - em vez de depender da memoria da execucao do dia.

Uso:
    python3 scripts/league_calendar.py                 # ligas ativas hoje
    python3 scripts/league_calendar.py --mes 7         # ligas ativas em julho
    python3 scripts/league_calendar.py --prioridade    # ordenado por prioridade de busca
"""
import argparse
import sys
from datetime import datetime, timedelta, timezone

BRT = timezone(timedelta(hours=-3))


def _mes_hoje_brt():
    """Mes atual em BRT, nunca no fuso do servidor/UTC (achado de auditoria,
    08/08 - a mesma classe do bug real cometido ao vivo nesta sessao: perto
    da meia-noite UTC, 'hoje' em BRT ainda e o dia anterior, e ~3h por dia
    o MES tambem pode divergir perto da virada do mes)."""
    return datetime.now(BRT).month

# ---------------------------------------------------------------- constantes
# eficiencia: quanto MAIOR, mais eficiente o mercado (mais dificil achar edge).
# A regra 8 da metodologia diz que o valor tende a viver nos mercados MENOS
# eficientes - entao eficiencia baixa e um PONTO POSITIVO na triagem, desde
# que haja dado confiavel e a casa licenciada precifique o jogo.
EFICIENCIA_ALTA = 3      # top-5 europeu, UCL, Brasileirao A
EFICIENCIA_MEDIA = 2     # Brasileirao B, MLS, Liga MX, Libertadores, J/K-League
EFICIENCIA_BAIXA = 1     # escandinavas, balticas, irlandesa, islandesa, 3as divisoes

# dado: qualidade/disponibilidade de xG e estatistica granular publica
DADO_BOM = 3
DADO_MEDIO = 2
DADO_FRACO = 1

# casa_br: com que frequencia as 9 casas licenciadas SPA/MF precificam a liga.
# Critico: liga sem preco em casa licenciada e inutil para Aposta de Valor
# (regra 9), por mais ineficiente que seja.
CASA_SEMPRE = 3
CASA_FREQUENTE = 2
CASA_RARA = 1


def _m(*meses):
    return set(meses)


# meses = meses do ano em que a liga tipicamente TEM RODADAS (nao pre-temporada)
LIGAS = [
    # ---------------------------------------------------- America do Sul
    dict(nome="Brasileirao Serie A", regiao="AmSul", meses=_m(3, 4, 5, 6, 7, 8, 9, 10, 11, 12),
         eficiencia=EFICIENCIA_ALTA, dado=DADO_BOM, casa_br=CASA_SEMPRE),
    dict(nome="Brasileirao Serie B", regiao="AmSul", meses=_m(3, 4, 5, 6, 7, 8, 9, 10, 11),
         eficiencia=EFICIENCIA_MEDIA, dado=DADO_MEDIO, casa_br=CASA_SEMPRE),
    dict(nome="Brasileirao Serie C", regiao="AmSul", meses=_m(4, 5, 6, 7, 8, 9, 10),
         eficiencia=EFICIENCIA_BAIXA, dado=DADO_FRACO, casa_br=CASA_FREQUENTE),
    dict(nome="Copa Libertadores", regiao="AmSul", meses=_m(2, 3, 4, 5, 6, 7, 8, 9, 10, 11),
         eficiencia=EFICIENCIA_MEDIA, dado=DADO_BOM, casa_br=CASA_SEMPRE),
    dict(nome="Copa Sul-Americana", regiao="AmSul", meses=_m(3, 4, 5, 6, 7, 8, 9, 10, 11),
         eficiencia=EFICIENCIA_MEDIA, dado=DADO_MEDIO, casa_br=CASA_SEMPRE),
    dict(nome="Argentina Liga Profesional", regiao="AmSul", meses=_m(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12),
         eficiencia=EFICIENCIA_MEDIA, dado=DADO_MEDIO, casa_br=CASA_SEMPRE),
    dict(nome="Chile Primera Division", regiao="AmSul", meses=_m(2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12),
         eficiencia=EFICIENCIA_BAIXA, dado=DADO_FRACO, casa_br=CASA_FREQUENTE),
    dict(nome="Colombia Primera A", regiao="AmSul", meses=_m(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12),
         eficiencia=EFICIENCIA_BAIXA, dado=DADO_FRACO, casa_br=CASA_FREQUENTE),
    dict(nome="Equador Serie A", regiao="AmSul", meses=_m(2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12),
         eficiencia=EFICIENCIA_BAIXA, dado=DADO_FRACO, casa_br=CASA_FREQUENTE),

    # ---------------------------------------------------- America do Norte
    dict(nome="MLS", regiao="AmNorte", meses=_m(2, 3, 4, 5, 6, 7, 8, 9, 10),
         eficiencia=EFICIENCIA_MEDIA, dado=DADO_BOM, casa_br=CASA_SEMPRE),
    dict(nome="Liga MX", regiao="AmNorte", meses=_m(1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12),
         eficiencia=EFICIENCIA_MEDIA, dado=DADO_MEDIO, casa_br=CASA_SEMPRE),
    dict(nome="USL Championship", regiao="AmNorte", meses=_m(3, 4, 5, 6, 7, 8, 9, 10),
         eficiencia=EFICIENCIA_BAIXA, dado=DADO_FRACO, casa_br=CASA_FREQUENTE),

    # ---------------------------------------------------- Europa (Ago-Mai)
    # Em JULHO estas ligas estao em PRE-TEMPORADA - amistosos devem ser evitados
    # (metodologia item 0). Por isso os meses excluem julho.
    dict(nome="Premier League", regiao="Europa", meses=_m(8, 9, 10, 11, 12, 1, 2, 3, 4, 5),
         eficiencia=EFICIENCIA_ALTA, dado=DADO_BOM, casa_br=CASA_SEMPRE),
    dict(nome="LaLiga", regiao="Europa", meses=_m(8, 9, 10, 11, 12, 1, 2, 3, 4, 5),
         eficiencia=EFICIENCIA_ALTA, dado=DADO_BOM, casa_br=CASA_SEMPRE),
    dict(nome="Serie A (Italia)", regiao="Europa", meses=_m(8, 9, 10, 11, 12, 1, 2, 3, 4, 5),
         eficiencia=EFICIENCIA_ALTA, dado=DADO_BOM, casa_br=CASA_SEMPRE),
    dict(nome="Bundesliga", regiao="Europa", meses=_m(8, 9, 10, 11, 12, 1, 2, 3, 4, 5),
         eficiencia=EFICIENCIA_ALTA, dado=DADO_BOM, casa_br=CASA_SEMPRE),
    dict(nome="Ligue 1", regiao="Europa", meses=_m(8, 9, 10, 11, 12, 1, 2, 3, 4, 5),
         eficiencia=EFICIENCIA_ALTA, dado=DADO_BOM, casa_br=CASA_SEMPRE),
    dict(nome="Championship (Inglaterra)", regiao="Europa", meses=_m(8, 9, 10, 11, 12, 1, 2, 3, 4, 5),
         eficiencia=EFICIENCIA_MEDIA, dado=DADO_MEDIO, casa_br=CASA_SEMPRE),
    dict(nome="Primeira Liga (Portugal)", regiao="Europa", meses=_m(8, 9, 10, 11, 12, 1, 2, 3, 4, 5),
         eficiencia=EFICIENCIA_MEDIA, dado=DADO_MEDIO, casa_br=CASA_SEMPRE),
    dict(nome="Eredivisie", regiao="Europa", meses=_m(8, 9, 10, 11, 12, 1, 2, 3, 4, 5),
         eficiencia=EFICIENCIA_MEDIA, dado=DADO_MEDIO, casa_br=CASA_SEMPRE),

    # Europa que COMECA em julho / esta em temporada no verao
    dict(nome="Scottish Premiership", regiao="Europa", meses=_m(7, 8, 9, 10, 11, 12, 1, 2, 3, 4, 5),
         eficiencia=EFICIENCIA_MEDIA, dado=DADO_MEDIO, casa_br=CASA_SEMPRE),
    dict(nome="Welsh Premier League", regiao="Europa", meses=_m(7, 8, 9, 10, 11, 12, 1, 2, 3, 4),
         eficiencia=EFICIENCIA_BAIXA, dado=DADO_FRACO, casa_br=CASA_RARA),
    dict(nome="Qualificatorias UEFA (UCL/UEL/UECL)", regiao="Europa", meses=_m(7, 8),
         eficiencia=EFICIENCIA_MEDIA, dado=DADO_MEDIO, casa_br=CASA_SEMPRE),

    # ---------------------------------------------------- Escandinavia/Nordicos
    # ATENCAO: temporada de VERAO - julho e PICO. Foram justamente estas que
    # a execucao de 31/07 nao viu. Eficiencia baixa + casa BR precifica =
    # exatamente onde a regra 8 manda procurar.
    dict(nome="Allsvenskan (Suecia)", regiao="Nordicos", meses=_m(3, 4, 5, 6, 7, 8, 9, 10, 11),
         eficiencia=EFICIENCIA_BAIXA, dado=DADO_MEDIO, casa_br=CASA_SEMPRE),
    dict(nome="Superettan (Suecia 2a)", regiao="Nordicos", meses=_m(4, 5, 6, 7, 8, 9, 10, 11),
         eficiencia=EFICIENCIA_BAIXA, dado=DADO_FRACO, casa_br=CASA_FREQUENTE),
    dict(nome="Eliteserien (Noruega)", regiao="Nordicos", meses=_m(3, 4, 5, 6, 7, 8, 9, 10, 11, 12),
         eficiencia=EFICIENCIA_BAIXA, dado=DADO_MEDIO, casa_br=CASA_SEMPRE),
    dict(nome="Veikkausliiga (Finlandia)", regiao="Nordicos", meses=_m(4, 5, 6, 7, 8, 9, 10),
         eficiencia=EFICIENCIA_BAIXA, dado=DADO_MEDIO, casa_br=CASA_FREQUENTE),
    dict(nome="Ykkosliiga (Finlandia 2a)", regiao="Nordicos", meses=_m(4, 5, 6, 7, 8, 9, 10),
         eficiencia=EFICIENCIA_BAIXA, dado=DADO_FRACO, casa_br=CASA_FREQUENTE),
    dict(nome="Besta deild (Islandia)", regiao="Nordicos", meses=_m(4, 5, 6, 7, 8, 9),
         eficiencia=EFICIENCIA_BAIXA, dado=DADO_FRACO, casa_br=CASA_FREQUENTE),
    dict(nome="Superliga (Dinamarca)", regiao="Nordicos", meses=_m(7, 8, 9, 10, 11, 12, 1, 2, 3, 4, 5),
         eficiencia=EFICIENCIA_MEDIA, dado=DADO_MEDIO, casa_br=CASA_SEMPRE),

    # ---------------------------------------------------- Balticos / Leste
    dict(nome="Meistriliiga (Estonia)", regiao="Balticos", meses=_m(3, 4, 5, 6, 7, 8, 9, 10, 11),
         eficiencia=EFICIENCIA_BAIXA, dado=DADO_FRACO, casa_br=CASA_FREQUENTE),
    dict(nome="Virsliga (Letonia)", regiao="Balticos", meses=_m(3, 4, 5, 6, 7, 8, 9, 10, 11),
         eficiencia=EFICIENCIA_BAIXA, dado=DADO_FRACO, casa_br=CASA_FREQUENTE),
    dict(nome="A Lyga (Lituania)", regiao="Balticos", meses=_m(3, 4, 5, 6, 7, 8, 9, 10, 11),
         eficiencia=EFICIENCIA_BAIXA, dado=DADO_FRACO, casa_br=CASA_FREQUENTE),

    # ---------------------------------------------------- Irlanda
    dict(nome="Premier Division (Irlanda)", regiao="Europa", meses=_m(2, 3, 4, 5, 6, 7, 8, 9, 10, 11),
         eficiencia=EFICIENCIA_BAIXA, dado=DADO_MEDIO, casa_br=CASA_FREQUENTE),

    # ---------------------------------------------------- Asia
    dict(nome="J-League", regiao="Asia", meses=_m(2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12),
         eficiencia=EFICIENCIA_MEDIA, dado=DADO_MEDIO, casa_br=CASA_SEMPRE),
    dict(nome="K-League", regiao="Asia", meses=_m(2, 3, 4, 5, 6, 7, 8, 9, 10, 11),
         eficiencia=EFICIENCIA_MEDIA, dado=DADO_MEDIO, casa_br=CASA_FREQUENTE),
    dict(nome="Chinese Super League", regiao="Asia", meses=_m(3, 4, 5, 6, 7, 8, 9, 10, 11),
         eficiencia=EFICIENCIA_BAIXA, dado=DADO_FRACO, casa_br=CASA_FREQUENTE),
]


def ligas_ativas(mes=None):
    """Ligas com rodadas tipicamente acontecendo no mes dado (default: hoje
    em BRT). 'mes' explicito e usado tal como veio - so o DEFAULT usa o
    relogio."""
    mes = mes if mes is not None else _mes_hoje_brt()
    if not 1 <= mes <= 12:
        raise ValueError(f"mes tem que estar entre 1 e 12, recebido {mes}")
    return [lg for lg in LIGAS if mes in lg["meses"]]


def prioridade_busca(liga):
    """Score de prioridade para a varredura diaria.

    Logica (regra 8 + regra 9 da metodologia):
    - eficiencia BAIXA e o que mais interessa -> inverter o sinal
    - mas so serve se a casa licenciada precificar (casa_br) e se houver
      dado suficiente para modelar (dado) - senao vira PE fraco ou nada.

    Maior score = deve ser varrido primeiro.
    """
    ineficiencia = (EFICIENCIA_ALTA + 1) - liga["eficiencia"]  # 1..3, maior = menos eficiente
    return ineficiencia * 2 + liga["casa_br"] * 2 + liga["dado"]


def ligas_por_prioridade(mes=None):
    return sorted(ligas_ativas(mes), key=lambda lg: (-prioridade_busca(lg), lg["nome"]))


def _rotulo(lg):
    ef = {3: "alta", 2: "media", 1: "BAIXA"}[lg["eficiencia"]]
    dd = {3: "bom", 2: "medio", 1: "fraco"}[lg["dado"]]
    cb = {3: "sempre", 2: "frequente", 1: "rara"}[lg["casa_br"]]
    return f"eficiencia={ef} dado={dd} casa_br={cb}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mes", type=int, default=None)
    ap.add_argument("--prioridade", action="store_true")
    args = ap.parse_args()

    # achado de auditoria (08/08): "args.mes or _mes_hoje_brt()" tratava
    # --mes 0 como falsy (Python) e silenciosamente usava o mes atual em
    # vez do 0 literal ou de um erro - "is not None" e a checagem certa.
    mes = args.mes if args.mes is not None else _mes_hoje_brt()
    try:
        ligas = ligas_por_prioridade(mes) if args.prioridade else ligas_ativas(mes)
    except ValueError as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 1

    print(f"=== LIGAS TIPICAMENTE ATIVAS NO MES {mes:02d} ({len(ligas)}) ===")
    if args.prioridade:
        print("(ordenado por prioridade de varredura: menos eficiente + precificada + com dado)\n")
    por_regiao = {}
    for lg in ligas:
        por_regiao.setdefault(lg["regiao"], []).append(lg)

    if args.prioridade:
        for lg in ligas:
            print(f"[{prioridade_busca(lg):2d}] {lg['nome']:38s} {lg['regiao']:9s} {_rotulo(lg)}")
    else:
        for regiao in sorted(por_regiao):
            print(f"\n-- {regiao} --")
            for lg in sorted(por_regiao[regiao], key=lambda x: x["nome"]):
                print(f"   {lg['nome']:38s} {_rotulo(lg)}")

    print(f"\nLembrete: ligas de eficiencia BAIXA com casa_br sempre/frequente sao o alvo")
    print("preferencial da regra 8 - e sao justamente as que noticia em portugues nao cobre.")


if __name__ == "__main__":
    sys.exit(main())
