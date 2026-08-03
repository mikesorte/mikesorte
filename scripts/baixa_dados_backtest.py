#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Expande o dataset real de backtest (Fase 0, v32).

O QUE ISTO RESOLVE
-------------------
data/backtest/*.csv tinha 13 ligas mas só 5 delas trazem escanteios/chutes/
cartoes (HC/AC/HS/AS/HST/AST/HY/AY): france_F1, germany_D1, italy_I1,
scotland_SC0, spain_SP1. Juntas, essas 5 somam so 697 jogos de MEIA
temporada de 2013 - pouco para calibrar um modelo novo com confianca (o
proprio precedente v28->v29 mostrou o custo de decidir modelo com dado
insuficiente/simulado).

Canal usado: raw.githubusercontent.com (mesmo host ja validado em
backtest_real.py - responde 200 quando football-data.co.uk direto da 403).
Repositorio: jokecamp/FootballData, que espelha o CSV BRUTO da
football-data.co.uk (todas as colunas de estatistica e das 8 casas, sem
reformatar) - confirmado por bater byte-a-byte com o spain_SP1.csv que ja
tinhamos. Cada liga tem varios arquivos numerados "DIV.csv", "DIV (1).csv",
"DIV (2).csv"... cada um cobrindo uma temporada (~380 jogos, liga de 20
times, turno e returno).

LIMITACAO DECLARADA: os arquivos numerados disponiveis vao ate ~1993-2013
(nao ha temporada recente aqui) - futebol mudou (VAR, pressing) desde entao.
Isso fica registrado no relatorio de calibracao, nao escondido.

Uso:
    python3 scripts/baixa_dados_backtest.py
    python3 scripts/baixa_dados_backtest.py --max-por-liga 8   # menos download
"""
import argparse
import csv
import io
import os
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(ROOT, "data", "backtest")
BASE_URL = "https://raw.githubusercontent.com/jokecamp/FootballData/master/football-data.co.uk"

# as 5 ligas que tem HC/AC/HS/AS/HST/AST/HY/AY - so essas valem a pena expandir
LIGAS = {
    "france_F1": ("france", "F1"),
    "germany_D1": ("germany", "D1"),
    "italy_I1": ("italy", "I1"),
    "scotland_SC0": ("scotland", "SC0"),
    "spain_SP1": ("spain", "SP1"),
}

COLUNAS_OBRIGATORIAS = {"HC", "AC", "HS", "AS", "HST", "AST", "HY", "AY", "FTHG", "FTAG", "Date"}


def _url(pais, div, indice):
    nome = div if indice == 0 else f"{div} ({indice})"
    from urllib.parse import quote
    return f"{BASE_URL}/{pais}/{quote(nome)}.csv"


def baixa(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def valido(conteudo_bytes):
    """Confere que o CSV baixado tem as colunas que precisamos - nunca
    persistir um arquivo incompleto/renomeado silenciosamente."""
    try:
        texto = conteudo_bytes.decode("utf-8", errors="replace")
        header = next(csv.reader(io.StringIO(texto)))
    except Exception:
        return False
    return COLUNAS_OBRIGATORIAS.issubset(set(header)) and len(texto.splitlines()) > 10


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-por-liga", type=int, default=25,
                     help="quantos indices numerados tentar por liga (default 25)")
    args = ap.parse_args()

    os.makedirs(DEST, exist_ok=True)
    antes = sum(1 for f in os.listdir(DEST) if f.endswith(".csv"))

    total_novos = 0
    total_jogos_novos = 0
    for prefixo, (pais, div) in LIGAS.items():
        for indice in range(1, args.max_por_liga + 1):
            destino = os.path.join(DEST, f"{prefixo}_s{indice}.csv")
            if os.path.exists(destino):
                continue
            url = _url(pais, div, indice)
            try:
                conteudo = baixa(url)
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    continue
                print(f"  [{prefixo} s{indice}] erro HTTP {e.code} - {url}")
                continue
            except Exception as e:
                print(f"  [{prefixo} s{indice}] falhou ({e}) - {url}")
                continue
            if not valido(conteudo):
                print(f"  [{prefixo} s{indice}] baixado mas sem colunas esperadas - descartado")
                continue
            with open(destino, "wb") as f:
                f.write(conteudo)
            n_linhas = conteudo.decode("utf-8", errors="replace").count("\n")
            total_novos += 1
            total_jogos_novos += max(0, n_linhas - 1)
            print(f"  [{prefixo} s{indice}] ok, ~{n_linhas - 1} jogos -> {os.path.basename(destino)}")

    depois = sum(1 for f in os.listdir(DEST) if f.endswith(".csv"))
    print(f"\nArquivos de backtest: {antes} -> {depois} "
          f"({total_novos} novos, ~{total_jogos_novos} jogos novos nas 5 ligas com stats).")
    print("LIMITACAO: dado vai ate ~2013, sem temporada recente disponivel neste canal.")


if __name__ == "__main__":
    main()
