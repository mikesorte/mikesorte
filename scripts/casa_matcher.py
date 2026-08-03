#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cruzamento de fixture entre casas (Fase 4, v32).

O PROBLEMA QUE ISTO RESOLVE
----------------------------
scan_odds.py sempre processou UM dump de UMA casa por vez. odds_sources.py
so decide qual casa TENTAR primeiro (por confiabilidade de extracao) - o
sistema parava na primeira que funcionava (decisao v23, "Betano basta"),
nunca comparou preco entre casas pro MESMO jogo. Isso contraria a regra 9
("line-shopping sempre") desde que ela foi escrita.

Este modulo nao busca odds em lugar nenhum - so recebe listas de eventos ja
extraidas (scan_odds.parse_mres_blocks(), uma lista por casa, cada uma com
o campo "casa" preenchido) e cruza qual evento de uma casa corresponde a
qual evento de outra, para permitir comparar preco no MESMO jogo.

REGRA DURA QUE NAO MUDA (docs/DAILY_METHODOLOGY.md v32, regra 9.1): o
teste no-vig SEMPRE usa odds dos dois lados da MESMA casa - este modulo
so ajuda a escolher, DEPOIS que o edge ja foi decidido com uma casa so,
qual casa da o MELHOR PRECO DE EXECUCAO para a selecao vencedora. Nunca
misturar casas no calculo da probabilidade justa.

Uso:
    from casa_matcher import normaliza_time, cruza_fixtures
    pares = cruza_fixtures({"Betano": eventos_betano, "Bet365": eventos_bet365})
"""
import re
import unicodedata

# Sufixos/ruido comuns que casas diferentes incluem ou nao no nome do time -
# remover para nao quebrar o match por diferenca cosmetica.
_RUIDO = re.compile(
    r"\b(fc|cf|sc|ac|afc|cd|ud|se|ec|esporte clube|clube|futebol clube|"
    r"club|calcio|futbol|de futebol)\b", re.I)
_ESPACOS = re.compile(r"\s+")
_NAO_ALFANUM = re.compile(r"[^a-z0-9 ]")


def normaliza_time(nome):
    """Normaliza um nome de time pra comparacao entre casas: minusculo,
    sem acento, sem sufixo de clube generico (FC/SC/CD/...), sem pontuacao.

    NAO tenta resolver apelidos completamente diferentes (ex. "Man Utd" vs
    "Manchester United") - isso exigiria um dicionario de aliases por liga,
    fora de escopo aqui. Cobre o caso comum: mesma raiz do nome, sufixo/
    acentuacao/caixa diferentes entre casas.
    """
    if not nome:
        return ""
    s = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = _NAO_ALFANUM.sub(" ", s)
    s = _RUIDO.sub(" ", s)
    s = _ESPACOS.sub(" ", s).strip()
    return s


def normaliza_confronto(participants):
    """'Time A - Time B' -> (nome_a_normalizado, nome_b_normalizado).
    None se nao conseguir separar em duas partes."""
    if not participants:
        return None
    partes = [p.strip() for p in participants.split(" - ")]
    if len(partes) != 2:
        return None
    return normaliza_time(partes[0]), normaliza_time(partes[1])


def _chave_evento(ev, janela_ms=3 * 60 * 60 * 1000):
    """Chave de match: (times normalizados, horario arredondado pra janela
    de 3h). Casas divergem em minutos por causa de fuso/atraso de sync -
    arredondar evita perder o match por diferenca de poucos minutos, sem
    juntar jogos de horarios claramente diferentes."""
    conf = normaliza_confronto(ev.get("participants"))
    if not conf:
        return None
    ts = ev.get("start_time")
    janela = int(ts) // janela_ms if ts else None
    return (conf, janela)


def cruza_fixtures(eventos_por_casa):
    """eventos_por_casa: {"Betano": [eventos...], "Bet365": [eventos...], ...}
    (cada evento com "participants"/"start_time"/"odds", tipicamente saida
    de scan_odds.parse_mres_blocks()).

    Devolve lista de dicts {"participants": ..., "por_casa": {casa: evento}}
    - um item por fixture que apareceu em 1+ casas. Fixtures com 2+ casas
    sao os candidatos reais a line-shopping; fixtures com 1 so casa ficam
    na lista tambem (uteis para o fluxo continuar funcionando com 1 casa
    so, como hoje - line-shopping nao pode ser um requisito rigido que
    quebra o sistema quando so uma casa esta no ar).
    """
    agrupado = {}
    for casa, eventos in eventos_por_casa.items():
        for ev in eventos:
            chave = _chave_evento(ev)
            if chave is None:
                continue
            grupo = agrupado.setdefault(chave, {"participants": ev.get("participants"),
                                                "por_casa": {}})
            grupo["por_casa"][casa] = ev
    return list(agrupado.values())


def melhor_preco(fixture, indice_selecao):
    """Dado um item de cruza_fixtures() e o INDICE da selecao (0=casa/1/
    2=fora no 1X2), devolve (casa_com_melhor_odd, odd) entre as casas que
    tem esse fixture. Uso: DEPOIS que o edge ja foi decidido com uma casa
    (teste 9.1), escolher onde EXECUTAR a aposta pelo melhor preco.

    Nunca usar isto pra decidir edge - so pra escolher preco de execucao
    de uma selecao ja definida (regra dura, ver docstring do modulo)."""
    melhor_casa, melhor_odd = None, None
    for casa, ev in fixture["por_casa"].items():
        odds = ev.get("odds")
        if not odds or indice_selecao >= len(odds):
            continue
        odd = odds[indice_selecao]
        if odd is None:
            continue
        if melhor_odd is None or odd > melhor_odd:
            melhor_casa, melhor_odd = casa, odd
    return melhor_casa, melhor_odd


def casa_do_edge(fixture, casas_com_1x2_completo=None):
    """Escolhe qual casa usar para o TESTE 9.1 (probabilidade justa) deste
    fixture - regra dura: precisa ter odds dos DOIS/TRES lados completos
    na MESMA casa. Se a casa de melhor preco (ver melhor_preco) nao tiver
    o 1X2 completo extraivel, este fixture usa outra casa para o edge e so
    troca para a de melhor preco na hora de registrar a odd de entrada -
    nunca perde a validade do teste 9.1 por causa do preco (achado da
    validacao estatistica do plano v32, Fase 4).

    casas_com_1x2_completo: se None, considera qualquer casa cujo evento
    tenha odds de 3 valores nao-None como "completa".
    """
    for casa, ev in fixture["por_casa"].items():
        if casas_com_1x2_completo is not None and casa not in casas_com_1x2_completo:
            continue
        odds = ev.get("odds")
        if odds and len(odds) == 3 and all(o is not None for o in odds):
            return casa
    return None
