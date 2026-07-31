#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Registro de fontes de odds das casas licenciadas + log de tentativas (v21).

PROBLEMA QUE ISTO RESOLVE
-------------------------
Ate v20 o sistema so tentava a Betano, e so uma vez, no inicio da execucao.
Duas fragilidades reais, ambas medidas em 31/07:

1. CONECTORES OSCILAM. Nimble/Tavily/Exa estavam FORA as 05h (execucao
   diaria), VOLTARAM as 09h40 (Tavily leu worldfootball, 188 jogos), e
   CAIRAM de novo as 10h. Uma checagem unica no passo 2 do fluxo perde o
   dia inteiro por azar de timing, mesmo com os conectores disponiveis
   horas depois.

2. FONTE UNICA. betano.bet.br e um SPA pesado e geo-protegido: o
   nimble_extract sincrono estoura 60s, o async ficou pendente >5min, o
   Exa devolve so a casca e o Tavily falha. Mas o usuario tem NOVE casas
   licenciadas - nao ha razao para depender de uma. Algumas podem ser
   server-rendered (mais faceis) e nunca foram testadas.

ESTRATEGIA
----------
Em vez de eu chutar qual casa e mais extraivel, o sistema TESTA e APRENDE:
cada tentativa (casa x ferramenta x resultado) vai para
data/extraction_log.csv. Depois de alguns dias, `ranking()` mostra qual
combinacao realmente funciona, e a execucao passa a tentar primeiro o que
tem melhor historico - decisao por dado, nao por suposicao.

Uso:
    python3 scripts/odds_sources.py --plano        # ordem de tentativa de hoje
    python3 scripts/odds_sources.py --ranking      # o que funciona historicamente
    python3 scripts/odds_sources.py --registrar casa=betano ferramenta=nimble_async \\
            resultado=timeout jogo="Bodo/Glimt x Lillestrom"
"""
import argparse
import csv
import os
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "data/extraction_log.csv")
COLUNAS = ["data", "casa", "ferramenta", "resultado", "jogo", "nota"]

# resultados possiveis (vocabulario fechado para o ranking funcionar)
OK = "ok"                    # trouxe odds utilizaveis dos dois lados
PARCIAL = "parcial"          # trouxe algo, mas insuficiente para o teste 9.1
TIMEOUT = "timeout"
BLOQUEIO = "bloqueio"        # 403 / failed to fetch / geo
CASCA = "casca"              # devolveu a pagina sem o conteudo dinamico
RESULTADOS = (OK, PARCIAL, TIMEOUT, BLOQUEIO, CASCA)

# As 9 casas licenciadas SPA/MF. 'padrao_url' so e preenchido onde houve
# EVIDENCIA real (visto em resultado de busca ou extracao). Onde nao houve,
# fica None de proposito - inventar URL de casa e exatamente o tipo de dado
# fabricado que a metodologia proibe. O campo se preenche conforme o sistema
# descobre, via nimble_search.
CASAS = [
    dict(nome="Betano", dominio="betano.bet.br",
         padrao_url="https://www.betano.bet.br/odds/{slug}/{id}/",
         tipo="SPA pesado (window['initial_state'])",
         evidencia="confirmado 29/07 e 31/07"),
    dict(nome="Superbet", dominio="superbet.bet.br",
         padrao_url="https://superbet.bet.br/apostas/futebol/{pais}/{liga}/todos",
         tipo="desconhecido",
         evidencia="URL de listagem vista em busca 31/07; extracao NAO testada"),
    dict(nome="Betfair", dominio="betfair.bet.br",
         padrao_url="https://apostas.betfair.bet.br/sports/futebol/{liga}/",
         tipo="desconhecido",
         evidencia="URL de conteudo vista em busca 28/07 e 31/07; extracao NAO testada"),
    dict(nome="Bet365", dominio="bet365.bet.br", padrao_url=None,
         tipo="SPA pesado, anti-bot agressivo",
         evidencia="odds obtidas via pagina de NOTICIA (news.bet365.bet.br) em 30/07"),
    dict(nome="KTO", dominio="kto.bet.br",
         padrao_url="https://www.kto.bet.br/palpites/",
         tipo="desconhecido",
         evidencia="pagina de palpites/odds vista em busca 31/07; extracao NAO testada"),
    dict(nome="Novibet", dominio="novibet.bet.br",
         padrao_url="https://www.novibet.bet.br/apostas-esportivas/futebol/4372606/{pais}/{liga}/{liga_id}",
         tipo="desconhecido",
         evidencia=("URL REAL de liga vista em busca 31/07 (Eliteserien: "
                    ".../norway/eliteserien/4377419). Tem tambem "
                    "/eventos-do-dia, candidato a CATALOGO do dia. NAO testada")),
    dict(nome="EstrelaBet", dominio="estrelabet.bet.br",
         padrao_url="https://www.estrelabet.bet.br/aposta-esportiva",
         tipo="desconhecido",
         evidencia="hub de apostas visto em busca 31/07; extracao NAO testada"),
    dict(nome="Bet Nacional", dominio="betnacional.bet.br",
         padrao_url="https://betnacional.bet.br/sport-event/{esporte_id}/{liga_id}",
         tipo="desconhecido",
         evidencia=("URLs REAIS de listagem vistas em busca 31/07 "
                    "(/sport-event/1/2 e /sport-event/137/1). NAO testada")),
    dict(nome="Sportingbet", dominio="sportingbet.bet.br",
         padrao_url="https://www.sportingbet.bet.br/pt-br/sports/futebol-4/aposta/{pais}-{id}",
         tipo="desconhecido",
         evidencia=("URL REAL de pais vista em busca 31/07 "
                    "(futebol-4/aposta/brasil-33). NAO testada")),
]

# Ferramentas de extracao, com o que ja foi MEDIDO sobre cada uma (31/07).
FERRAMENTAS = [
    dict(nome="nimble_search", serve_para="descobrir a URL exata da pagina de odds",
         medido="funciona"),
    dict(nome="nimble_extract_async", serve_para="SPA pesado; nao bloqueia a execucao",
         medido="aceita a task; na Betano seguia pendente >5min"),
    dict(nome="nimble_extract", serve_para="paginas leves",
         medido="timeout de 60s na Betano (limite do cliente MCP)"),
    dict(nome="tavily_extract", serve_para="paginas server-rendered (fixtures/estatistica)",
         medido="OK em worldfootball (141k chars); FALHA em betano.bet.br"),
    dict(nome="exa_web_fetch", serve_para="paginas estaticas",
         medido="devolve so a casca; nao renderiza JS"),
    dict(nome="pdf_export", serve_para="ultimo recurso, exige acao do usuario",
         medido="funciona (31 jogos extraidos do export de 29/07)"),
]


def _garantir_log():
    if not os.path.exists(LOG):
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(COLUNAS)


def registrar(casa, ferramenta, resultado, jogo="", nota=""):
    if resultado not in RESULTADOS:
        raise ValueError(f"resultado invalido: {resultado}. Use um de {RESULTADOS}")
    _garantir_log()
    with open(LOG, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([date.today().isoformat(), casa, ferramenta,
                                resultado, jogo, nota])


def ler_log():
    if not os.path.exists(LOG):
        return []
    with open(LOG, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def ranking():
    """Taxa de sucesso por (casa, ferramenta), do melhor para o pior."""
    agreg = {}
    for r in ler_log():
        chave = (r["casa"], r["ferramenta"])
        d = agreg.setdefault(chave, {"ok": 0, "total": 0})
        d["total"] += 1
        if r["resultado"] == OK:
            d["ok"] += 1
    saida = []
    for (casa, ferr), d in agreg.items():
        taxa = d["ok"] / d["total"] if d["total"] else 0.0
        saida.append((taxa, d["ok"], d["total"], casa, ferr))
    return sorted(saida, reverse=True)


def plano_de_tentativa():
    """Ordem de tentativa do dia: o que tem melhor historico primeiro, depois
    o que nunca foi testado (para descobrir), depois o que ja falhou."""
    rk = {(c, f): (taxa, ok, tot) for taxa, ok, tot, c, f in ranking()}
    plano = []
    for casa in CASAS:
        for ferr in ("nimble_extract_async", "tavily_extract", "exa_web_fetch"):
            hist = rk.get((casa["nome"], ferr))
            if hist is None:
                # nunca testado fica ACIMA do que ja falhou: pode funcionar,
                # e so descobrimos testando. (bug pego em 31/07: a versao
                # inicial punha 0/1 acima de nunca-testado.)
                prioridade = 2.0
                rotulo = "nunca testado"
            else:
                taxa, ok, tot = hist
                if taxa > 0:
                    prioridade = 3.0 + taxa      # sucesso comprovado: topo
                else:
                    prioridade = 1.0 - min(tot, 9) / 10  # falhou: fundo,
                    # e quanto mais vezes falhou, mais para o fundo
                rotulo = f"{ok}/{tot} ok"
            # casa sem padrao_url conhecido precisa de nimble_search antes
            precisa_descobrir = casa["padrao_url"] is None
            plano.append(dict(casa=casa["nome"], ferramenta=ferr,
                              prioridade=prioridade, historico=rotulo,
                              precisa_descobrir_url=precisa_descobrir))
    return sorted(plano, key=lambda p: -p["prioridade"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plano", action="store_true")
    ap.add_argument("--ranking", action="store_true")
    ap.add_argument("--registrar", nargs="*", metavar="chave=valor")
    args = ap.parse_args()

    if args.registrar is not None and args.registrar:
        kv = dict(p.split("=", 1) for p in args.registrar)
        registrar(kv["casa"], kv["ferramenta"], kv["resultado"],
                  kv.get("jogo", ""), kv.get("nota", ""))
        print(f"registrado: {kv}")
        return 0

    if args.ranking:
        rk = ranking()
        print("=== RANKING DE EXTRACAO (fonte: data/extraction_log.csv) ===")
        if not rk:
            print("Sem tentativas registradas ainda. Registre cada tentativa da")
            print("execucao diaria - e assim que o sistema aprende qual casa serve.")
        for taxa, ok, tot, casa, ferr in rk:
            print(f"  {taxa:5.0%}  ({ok}/{tot})  {casa:14s} via {ferr}")
        return 0

    if args.plano:
        print("=== PLANO DE TENTATIVA DE HOJE ===")
        print("(historico primeiro; nunca-testado em seguida, para descobrir)\n")
        for p in plano_de_tentativa()[:12]:
            marca = " [precisa nimble_search p/ achar a URL]" if p["precisa_descobrir_url"] else ""
            print(f"  {p['casa']:14s} via {p['ferramenta']:20s} [{p['historico']}]{marca}")
        return 0

    print("=== CASAS LICENCIADAS E O QUE SE SABE DE CADA UMA ===")
    for c in CASAS:
        url = c["padrao_url"] or "(padrao de URL ainda desconhecido)"
        print(f"\n{c['nome']} ({c['dominio']})")
        print(f"   tipo: {c['tipo']}")
        print(f"   url : {url}")
        print(f"   evid: {c['evidencia']}")
    print("\n=== FERRAMENTAS (medido em 31/07) ===")
    for f in FERRAMENTAS:
        print(f"  {f['nome']:22s} {f['medido']}")
        print(f"  {'':22s} serve para: {f['serve_para']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
