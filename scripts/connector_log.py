#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Log de disponibilidade dos conectores MCP (v26).

O QUE ESTE LOG DESCOBRIU - e por que a hipotese original estava errada
---------------------------------------------------------------------
Hipotese original (v22): "os conectores oscilam ao longo do dia; existe uma
hora boa; achar essa hora e mover a trigger para la". O log foi construido
para achar essa hora.

Em 02/08, com 11 checagens acumuladas, o log refutou a propria hipotese que
motivou sua criacao. Cruzando cada checagem com o CONTEXTO de execucao:

    dentro de disparo de trigger (sessao agendada): 0/7 com conector no ar
    em turno interativo:                            2/4 com conector no ar

Teste decisivo, que controla a hora: 31/07 as 09h40 (interativo) = OK;
01/08 as 09h46 (trigger) = fora. Mesma hora do dia, resultado oposto.
A hora nao explica nada. O CONTEXTO explica tudo.

MECANISMO (confirmado, nao inferido): o job_config de toda trigger tem
`session_context.allowed_tools` sem NENHUMA entrada `mcp__*`. Sessoes
agendadas nascem sem ferramenta de conector. Nao ha oscilacao a cronometrar -
os conectores nunca estiveram disponiveis para execucao agendada, em hora
nenhuma. Tentar anexa-los via create_trigger(connectors=[...]) retorna
"not available for this organization".

CONSEQUENCIA PRATICA: mover o horario da trigger nao resolveria nada, e a
extracao de odds (metodo v23) so funciona em turno interativo. A correcao
depende de o usuario anexar os conectores as Routines pela UI do claude.ai -
nao ha caminho por API a partir daqui.

LICAO DE METODO (segunda vez na mesma semana, ver decisao 36): construi
maquinaria elaborada - log, janelas, recomendacao de horario, cadeia de
send_later reamostrando horas - em cima de uma hipotese que nunca testei
contra a alternativa obvia. O dado que refutou tudo ja estava no log desde
a primeira semana; faltou cruza-lo com o contexto. Antes de otimizar uma
variavel, verificar se ela e a variavel.

Este log continua util por dois motivos: (1) ele e a prova da refutacao, e
(2) serve de sentinela - se o usuario anexar os conectores pela UI, a
primeira linha `trigger,ok` avisa que a automacao completa foi destravada.

Uso:
    python3 scripts/connector_log.py --registrar nimble=fora tavily=fora exa=fora contexto=trigger
    python3 scripts/connector_log.py --janelas
    python3 scripts/connector_log.py --contexto
"""
import argparse
import csv
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "data/connector_log.csv")
COLUNAS = ["timestamp_utc", "hora_utc", "nimble", "tavily", "exa", "contexto",
           "dispositivo", "nota"]
ESTADOS = ("ok", "fora")
# 'trigger'   = checagem feita dentro de um disparo agendado (sessao sem mcp__*)
# 'interativo' = checagem feita num turno com o usuario presente
CONTEXTOS = ("trigger", "interativo")
# De onde o usuario respondeu. Pergunta aberta em 02/08: os conectores sao
# concedidos por CONTA (e ai tanto faz o aparelho) ou dependem do cliente que
# abriu o turno? As 2 janelas que funcionaram vieram de dispositivo nao
# registrado, entao nao da para responder com o dado atual - vira experimento,
# nao chute. 'na' para checagem em trigger (nao ha usuario/aparelho envolvido).
DISPOSITIVOS = ("pc", "mobile", "desconhecido", "na")


def _garantir():
    if not os.path.exists(LOG):
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(COLUNAS)


def registrar(nimble, tavily, exa, nota="", quando=None, contexto=None,
              dispositivo=None):
    """quando: ISO-8601 UTC para observacao RETROATIVA (ex.: preencher o que
    foi observado mais cedo no dia). Sem isso, usa a hora atual.

    Bug real pego em 31/07: registrar 4 observacoes do dia inteiro de uma vez
    carimbava todas com a hora atual (21h), fazendo o log dizer que 21h tinha
    disponibilidade quando na verdade a unica janela foi ~09h40. Log com hora
    errada e pior que log nenhum - ele orientaria a trigger para a hora errada.

    contexto: OBRIGATORIO ('trigger' ou 'interativo'). E a variavel que de fato
    determina a disponibilidade (ver docstring do modulo). Registrar sem ela
    produz exatamente o log ambiguo que atrasou o diagnostico por uma semana,
    entao aqui e erro, nao default silencioso.
    """
    for nome, v in (("nimble", nimble), ("tavily", tavily), ("exa", exa)):
        if v not in ESTADOS:
            raise ValueError(f"{nome}={v} invalido; use um de {ESTADOS}")
    if contexto not in CONTEXTOS:
        raise ValueError(
            f"contexto={contexto!r} invalido; use um de {CONTEXTOS}. "
            "Sem contexto o log nao distingue as duas populacoes e vira ruido.")
    if dispositivo is None:
        dispositivo = "na" if contexto == "trigger" else "desconhecido"
    if dispositivo not in DISPOSITIVOS:
        raise ValueError(
            f"dispositivo={dispositivo!r} invalido; use um de {DISPOSITIVOS}")
    _garantir()
    if quando:
        ts = datetime.fromisoformat(quando)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
    else:
        ts = datetime.now(timezone.utc)
    with open(LOG, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([ts.isoformat(timespec="seconds"),
                                ts.hour, nimble, tavily, exa, contexto,
                                dispositivo, nota])


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


def por_contexto():
    """{contexto: (checagens_com_algum_ok, total)} - a analise que importa."""
    agreg = defaultdict(lambda: [0, 0])
    for r in ler():
        ctx = (r.get("contexto") or "").strip() or "nao_marcado"
        algum_ok = any(r.get(c) == "ok" for c in ("nimble", "tavily", "exa"))
        agreg[ctx][1] += 1
        if algum_ok:
            agreg[ctx][0] += 1
    return {c: tuple(v) for c, v in sorted(agreg.items())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--registrar", nargs="*", metavar="chave=valor")
    ap.add_argument("--janelas", action="store_true")
    ap.add_argument("--contexto", action="store_true")
    args = ap.parse_args()

    if args.registrar:
        kv = dict(p.split("=", 1) for p in args.registrar)
        registrar(kv.get("nimble", "fora"), kv.get("tavily", "fora"),
                  kv.get("exa", "fora"), kv.get("nota", ""),
                  kv.get("quando"), kv.get("contexto"),
                  kv.get("dispositivo"))
        print("registrado")
        return 0

    if not ler():
        print("Sem checagens registradas ainda.")
        return 0

    if args.janelas:
        print("=== DISPONIBILIDADE POR HORA UTC ===")
        print("ATENCAO: este corte e o que ENGANOU o diagnostico por uma semana.")
        print("A hora nao e a variavel explicativa - use --contexto.\n")
        for h, (ok, tot) in por_hora().items():
            barra = "#" * int(round(10 * ok / tot)) if tot else ""
            print(f"  {h:02d}:00 UTC ({(h-3) % 24:02d}h BRT)  {ok}/{tot}  {barra}")
        return 0

    if args.contexto:
        dados = por_contexto()
        print("=== DISPONIBILIDADE POR CONTEXTO DE EXECUCAO ===")
        print("(fonte: data/connector_log.csv - esta e a variavel que explica)\n")
        for ctx, (ok, tot) in dados.items():
            print(f"  {ctx:<12} {ok}/{tot} com algum conector no ar")
        # corte por dispositivo - so faz sentido dentro dos turnos interativos
        inter = [r for r in ler() if r.get("contexto") == "interativo"]
        if inter:
            print("\n--- dentro dos turnos interativos, por dispositivo ---")
            agreg = defaultdict(lambda: [0, 0])
            for r in inter:
                d = (r.get("dispositivo") or "desconhecido").strip() or "desconhecido"
                agreg[d][1] += 1
                if any(r.get(c) == "ok" for c in ("nimble", "tavily", "exa")):
                    agreg[d][0] += 1
            for d, (ok, tot) in sorted(agreg.items()):
                print(f"  {d:<13} {ok}/{tot}")
            if set(agreg) <= {"desconhecido"}:
                print("  (nenhum dispositivo registrado ainda - a pergunta")
                print("   'PC ou celular funciona?' segue SEM RESPOSTA. Registrar")
                print("   dispositivo=pc|mobile nas proximas execucoes resolve.)")

        trig = dados.get("trigger", (0, 0))
        if trig[1] and trig[0] == 0:
            print(f"\nSessoes agendadas: {trig[0]}/{trig[1]}. Consistente com o")
            print("mecanismo confirmado - allowed_tools da trigger nao tem mcp__*.")
            print("Extracao de odds so funciona em turno interativo ate que os")
            print("conectores sejam anexados as Routines pela UI do claude.ai.")
        elif trig[0]:
            print(f"\n*** MUDANCA DE ESTADO: {trig[0]}/{trig[1]} checagens em trigger")
            print("com conector no ar. Se isso e novo, os conectores foram")
            print("anexados as Routines - a automacao completa foi destravada.")
            print("Revisar docs/DAILY_METHODOLOGY.md decisao (39).")
        return 0

    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
