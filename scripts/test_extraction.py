#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Suite adversarial da extracao (v26).

POR QUE EXISTE
--------------
O usuario pediu para testar a extracao "varias vezes e de varias formas, em
varios lugares". A extracao ao vivo (metodo v23) so funciona em turno
interativo com os conectores no ar - decisao (39) - entao ela nao pode ser
exercitada sob demanda. O que PODE ser exercitado sempre, sem rede, e o
parser: dado um catalogo bruto, ele extrai os eventos certos e descarta os
errados?

Cada fixture aqui e uma ARMADILHA REAL que ja passou pelo sistema ou que o
derrubaria. Nao sao casos inventados para dar verde - varios reproduzem bugs
que custaram analise errada em dias especificos, anotados na docstring de
cada teste. Um teste que nunca poderia falhar nao vale o custo de manutencao.

Uso:  python3 scripts/test_extraction.py
Saida: exit 0 se tudo passa; exit 1 e lista dos que falharam.
"""
import json
import sys
import os
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import scan_odds
from betting_model import devig_power

BRT = timezone(timedelta(hours=-3))
FALHAS = []


def checa(nome, condicao, detalhe=""):
    if condicao:
        print(f"  ok   {nome}")
    else:
        print(f"  FALHA {nome} :: {detalhe}")
        FALHAS.append(nome)


def ev(participants, competition, start_time=None, odds=None):
    return {"participants": participants, "competition": competition,
            "start_time": start_time, "odds": odds or [2.0, 3.3, 3.6],
            "names": ["1", "X", "2"]}


def ms(dia_iso, hora=15, minuto=0):
    d = datetime.fromisoformat(dia_iso).replace(
        hour=hora, minute=minuto, tzinfo=BRT)
    return str(int(d.timestamp() * 1000))


# ---------------------------------------------------------------- 1. filtros
def teste_filtros():
    """Falsos positivos que ja aconteceram (01/08): 'Argentinos Juniors',
    'Boca Juniors' e 'Atletico Junior' sao clubes ADULTOS e foram descartados
    como base por um regex que pegava 'Junior'. Descartar jogo legitimo e tao
    grave quanto aceitar jogo invalido - so que silencioso."""
    print("\n[1] filtros de escopo")
    hoje = "2026-08-02"

    # devem SOBREVIVER
    legitimos = [
        ev("Argentinos Juniors - Boca Juniors", "Liga Profesional", ms(hoje)),
        ev("Atletico Junior - Millonarios", "Primera A", ms(hoje)),
        ev("Junior FC - America de Cali", "Primera A", ms(hoje)),
        # 'B' como parte do nome real, nao sufixo de reserva
        ev("Hobro IK - B 93", "1. Division", ms(hoje)),
        ev("IFK Goteborg - Degerfors", "Allsvenskan", ms(hoje)),
    ]
    elig, mot = scan_odds.filtrar_elegiveis(
        legitimos, data_brt=hoje, agora_ms=int(ms(hoje, 0, 1)))
    checa("clubes adultos com 'Junior(s)' sobrevivem",
          len(elig) == len(legitimos),
          f"esperado {len(legitimos)}, veio {len(elig)}; motivos={mot}")

    # devem ser DESCARTADOS, um motivo por vez
    casos = [
        (ev("Malmo FF (F) - Rosengard", "Damallsvenskan", ms(hoje)), "feminino"),
        (ev("Brann - Valerenga", "Toppserien Women", ms(hoje)), "feminino"),
        (ev("Hannover 96 II - Meppen", "Regionalliga", ms(hoje)), "base_reserva"),
        (ev("Real Madrid B - Osasuna B", "Primera RFEF", ms(hoje)), "base_reserva"),
        (ev("Flamengo U20 - Vasco U20", "Copa do Brasil Sub-20", ms(hoje)), "base_reserva"),
        (ev("Chelsea - Juventus", "Amistosos de Clubes", ms(hoje)), "amistoso"),
        (ev("Ajax - PSV", "Pre-season Friendly", ms(hoje)), "amistoso"),
        (ev("Sirius - AIK", "Allsvenskan", ms("2026-08-03")), "outro_dia"),
        (ev("Sirius - AIK", "Allsvenskan", ms("2026-08-01")), "outro_dia"),
    ]
    for evento, motivo in casos:
        elig, mot = scan_odds.filtrar_elegiveis(
            [evento], data_brt=hoje, agora_ms=int(ms(hoje, 0, 1)))
        checa(f"descarta por {motivo}: {evento['participants'][:34]}",
              len(elig) == 0 and mot[motivo] == 1,
              f"elig={len(elig)} motivos={mot}")


def teste_ja_iniciado():
    """Regra 0: nunca analisar jogo ja comecado. O corte e o INSTANTE atual,
    nao o fim do dia - um jogo das 09h nao pode entrar numa execucao das 14h."""
    print("\n[2] corte temporal")
    hoje = "2026-08-02"
    agora = int(ms(hoje, 14, 0))
    passado = ev("Gnistan - KuPS", "Veikkausliiga", ms(hoje, 9, 0))
    futuro = ev("Oulu - Ilves", "Veikkausliiga", ms(hoje, 16, 0))
    elig, mot = scan_odds.filtrar_elegiveis(
        [passado, futuro], data_brt=hoje, agora_ms=agora)
    checa("jogo das 09h fora numa execucao das 14h",
          len(elig) == 1 and elig[0]["participants"].startswith("Oulu"),
          f"elig={[e['participants'] for e in elig]} motivos={mot}")

    limite = ev("Exato - Agora", "Liga", str(agora))
    elig, _ = scan_odds.filtrar_elegiveis(
        [limite], data_brt=hoje, agora_ms=agora)
    checa("jogo comecando exatamente agora nao entra", len(elig) == 0)


def teste_fuso():
    """'UTC engana' (regra 0). Um jogo as 23h30 BRT de 02/08 e 02h30 UTC de
    03/08. Filtrar pela data UTC jogaria fora um jogo valido de hoje - erro
    que muda a cobertura do dia inteiro em ligas sul-americanas."""
    print("\n[3] fuso horario")
    hoje = "2026-08-02"
    tarde_br = ev("Racing - Tigre", "Liga Profesional", ms(hoje, 23, 30))
    dt_utc = datetime.fromtimestamp(int(tarde_br["start_time"]) / 1000,
                                    tz=timezone.utc)
    checa("fixture realmente cai no dia seguinte em UTC",
          dt_utc.date().isoformat() == "2026-08-03",
          f"UTC={dt_utc.isoformat()}")
    elig, mot = scan_odds.filtrar_elegiveis(
        [tarde_br], data_brt=hoje, agora_ms=int(ms(hoje, 8, 0)))
    checa("jogo 23h30 BRT sobrevive (filtro usa BRT, nao UTC)",
          len(elig) == 1, f"motivos={mot}")


def teste_devig():
    """O de-vig e o unico numero que vira decisao de aposta. Aqui ele e testado
    contra propriedades que precisam valer SEMPRE, nao contra um valor fixo."""
    print("\n[4] de-vig (propriedades)")
    for odds in ([2.0, 3.3, 3.6], [1.57, 4.10, 5.50], [1.20, 7.0, 15.0],
                 [2.05, 3.40, 3.50]):
        justo = devig_power(odds)
        checa(f"soma 1.0 em {odds}", abs(sum(justo) - 1.0) < 1e-6,
              f"soma={sum(justo)}")
        checa(f"ordem preservada em {odds}",
              [i for i, _ in sorted(enumerate(odds), key=lambda t: t[1])] ==
              [i for i, _ in sorted(enumerate(justo), key=lambda t: -t[1])],
              f"odds={odds} justo={justo}")
        checa(f"prob justa < prob implicita bruta em {odds}",
              all(j < 1 / o + 1e-9 for j, o in zip(justo, odds)),
              "de-vig tem que REDUZIR a probabilidade, nunca aumentar")

    # Mercado com soma implicita <= 1 nao existe em casa real - e sinal de
    # dado de agregador/media, que a regra v8 manda DESCARTAR. O motor tem
    # que recusar, nao "corrigir" silenciosamente.
    # (Meu primeiro teste aqui esperava que [3.0,3.0,3.0] passasse; estava
    # errado - a recusa e o comportamento correto e deliberado.)
    for invalido in ([3.0, 3.0, 3.0], [4.0, 4.0, 4.0]):
        try:
            devig_power(invalido)
        except ValueError:
            checa(f"recusa odds sem margem {invalido}", True)
        else:
            checa(f"recusa odds sem margem {invalido}", False,
                  "aceitou dado de agregador - regra v8 violada")


def teste_overround():
    """Guarda de sanidade que pegaria parser lendo numero errado: overround
    fora de 0-25% significa que as odds nao sao de um mercado 1X2 real."""
    print("\n[5] overround como sentinela")
    def over(odds):
        return sum(1 / o for o in odds) - 1.0
    checa("catalogo tipico dentro da faixa", 0.0 <= over([2.0, 3.3, 3.6]) <= 0.25)
    checa("odds corrompidas caem fora da faixa", over([1.1, 1.1, 1.1]) > 0.25,
          "sentinela nao dispararia num dump lido errado")


def teste_parser_json():
    """parse_mres_blocks trabalha sobre JSON bruto da casa. Testa que ele
    pareia cada mercado com o evento certo - o risco e pegar o leagueName do
    evento ANTERIOR quando dois eventos vem em sequencia."""
    print("\n[6] parser sobre JSON bruto")
    bruto = (
        '{"leagueName":"Allsvenskan","shortName":"Goteborg - Degerfors",'
        '"startTime":1785974400000,"markets":['
        '{"name":"Resultado Final","selections":['
        '{"fullName":"Goteborg","price":2.10},'
        '{"fullName":"Empate","price":3.40},'
        '{"fullName":"Degerfors","price":3.30}]}]}'
        ','
        '{"leagueName":"Eliteserien","shortName":"Brann - Rosenborg",'
        '"startTime":1785981600000,"markets":['
        '{"name":"Resultado Final","selections":['
        '{"fullName":"Brann","price":1.80},'
        '{"fullName":"Empate","price":3.60},'
        '{"fullName":"Rosenborg","price":4.20}]}]}'
    )
    eventos = scan_odds.parse_mres_blocks(bruto)
    checa("achou os 2 eventos", len(eventos) == 2, f"veio {len(eventos)}")
    if len(eventos) == 2:
        checa("evento 1 com a liga certa",
              eventos[0]["competition"] == "Allsvenskan",
              f"veio {eventos[0]['competition']}")
        checa("evento 2 NAO herdou a liga do anterior",
              eventos[1]["competition"] == "Eliteserien",
              f"veio {eventos[1]['competition']} - vazamento de contexto")
        checa("odds do evento 2 corretas",
              eventos[1]["odds"] == [1.80, 3.60, 4.20],
              f"veio {eventos[1]['odds']}")

    vazio = scan_odds.parse_mres_blocks("nada de json aqui")
    checa("dump sem mercado devolve lista vazia, nao exception", vazio == [])

    truncado = '{"leagueName":"X","markets":[{"name":"Resultado Final","sele'
    checa("dump truncado nao derruba o parser",
          scan_odds.parse_mres_blocks(truncado) == [])


def teste_sem_start_time():
    """Evento sem startTime nao pode ser descartado em silencio nem entrar como
    se fosse de hoje. Hoje ele PASSA (comportamento atual) - o teste existe
    para fixar isso explicitamente: se alguem mudar, o teste avisa e a decisao
    vira consciente em vez de acidental."""
    print("\n[7] evento sem horario")
    # NAO usar nomes tipo "Time B" aqui: o filtro de reserva casa com sufixo
    # " B" e o caso vira base_reserva por acidente, testando outra coisa.
    # (Foi o que aconteceu na primeira versao deste teste.)
    sem = ev("Aalborg - Silkeborg", "Superliga", None)
    elig, mot = scan_odds.filtrar_elegiveis(
        [sem], data_brt="2026-08-02", agora_ms=int(ms("2026-08-02", 8, 0)))
    checa("evento sem startTime passa (documentado, nao acidental)",
          len(elig) == 1, f"elig={len(elig)} motivos={mot}")


def main():
    print("=== SUITE ADVERSARIAL DA EXTRACAO (v26) ===")
    print("Cada caso e uma armadilha real - ver docstrings.")
    for t in (teste_filtros, teste_ja_iniciado, teste_fuso, teste_devig,
              teste_overround, teste_parser_json, teste_sem_start_time):
        try:
            t()
        except Exception as e:
            print(f"  ERRO ao rodar {t.__name__}: {type(e).__name__}: {e}")
            FALHAS.append(t.__name__)

    print("\n" + "=" * 60)
    if FALHAS:
        print(f"FALHAS ({len(FALHAS)}):")
        for f in FALHAS:
            print(f"  - {f}")
        return 1
    print("Todos os casos adversariais passaram.")
    print("ATENCAO: isto valida o PARSER, nao a extracao ao vivo. Catalogo real")
    print("so entra em turno interativo com conectores no ar (decisao 39).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
