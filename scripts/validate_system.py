#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auto-diagnostico do sistema (v13). Rodar NO INICIO de toda execucao diaria:
    python3 scripts/validate_system.py
Sai com codigo 0 (saudavel) ou 1 (problema encontrado - listado no stdout).
Blindagem contra: corrupcao de ledger, regressao no motor de calculo,
resultados esquecidos sem resolver, CLV esquecido sem preencher.
"""
import csv
import os
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ERRORS, WARNINGS = [], []


def err(msg):
    ERRORS.append(msg)


def warn(msg):
    WARNINGS.append(msg)


def check_csv(path, required_cols, id_col="id"):
    full = os.path.join(ROOT, path)
    if not os.path.exists(full):
        err(f"{path}: ARQUIVO AUSENTE")
        return []
    with open(full, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        warn(f"{path}: vazio")
        return rows
    missing = [c for c in required_cols if c not in rows[0]]
    if missing:
        err(f"{path}: colunas ausentes {missing}")
    ids = [r.get(id_col) for r in rows]
    if len(ids) != len(set(ids)):
        err(f"{path}: IDs duplicados")
    return rows


def main():
    # 1) ledgers integros
    apostas = check_csv("data/apostas_ledger.csv",
                        ["id", "data", "confronto", "mercado", "odd_entrada",
                         "odd_fechamento", "clv", "resultado", "acerto_erro"])
    pes = check_csv("data/pe_ledger.csv",
                    ["id", "data", "confronto", "mercado", "confianca",
                     "resultado", "ocorreu"])

    # 2) pendencias esquecidas (resultado/CLV de jogos passados)
    today = date.today().isoformat()  # YYYY-MM-DD compara lexicograficamente
    for r in apostas:
        d = r.get("data", "")
        if len(d) == 10 and d < today:
            if r.get("acerto_erro") in ("", "pendente"):
                warn(f"apostas_ledger id={r['id']}: resultado PENDENTE de jogo passado ({d})")
            if r.get("odd_entrada") not in ("", "NA") and r.get("clv") in ("", "NA") \
                    and r.get("acerto_erro") not in ("agregado",):
                warn(f"apostas_ledger id={r['id']}: CLV nao preenchido ({d}) - buscar odd de fechamento")
    for r in pes:
        d = r.get("data", "")
        if len(d) == 10 and d < today and r.get("ocorreu") in ("", "pendente"):
            warn(f"pe_ledger id={r['id']}: PE pendente de resolucao ({d})")

    # 3) regressao no motor de calculo
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    try:
        from betting_model import devig_power, poisson_dixon_coles, wilson_ci, ev_unitario, clv
        f = devig_power([1.50, 4.20, 7.10])
        assert abs(sum(f) - 1) < 1e-6, "devig nao soma 1"
        assert 0.60 < f[0] < 0.70, f"devig favorito fora da faixa esperada: {f[0]}"
        m = poisson_dixon_coles(1.9, 0.8)
        assert abs(m["p_home"] + m["p_draw"] + m["p_away"] - 1) < 1e-9, "DC nao soma 1"
        p, lo, hi = wilson_ci(6, 16)
        assert lo < p < hi and 0 <= lo and hi <= 1, "wilson invalido"
        assert abs(ev_unitario(0.5, 2.0)) < 1e-9, "EV(0.5,2.0) deveria ser 0"
        assert abs(clv(2.0, 2.0)) < 1e-9, "CLV(x,x) deveria ser 0"
        try:
            devig_power([2.10, 2.10])  # soma implicita < 1 => deve rejeitar
            err("motor: devig aceitou odds sem margem (deveria rejeitar, regra v8)")
        except ValueError:
            pass
    except AssertionError as e:
        err(f"motor: REGRESSAO DETECTADA - {e}")
    except Exception as e:
        err(f"motor: falha ao carregar/testar - {e}")

    # relatorio
    print("=== AUTO-DIAGNOSTICO DO SISTEMA ===")
    print(f"apostas_ledger: {len(apostas)} linhas | pe_ledger: {len(pes)} linhas")
    for w in WARNINGS:
        print(f"[PENDENCIA] {w}")
    for e in ERRORS:
        print(f"[ERRO] {e}")
    if not ERRORS and not WARNINGS:
        print("OK: nenhum erro, nenhuma pendencia.")
    elif not ERRORS:
        print(f"OK com {len(WARNINGS)} pendencia(s) a resolver nesta execucao.")
    else:
        print(f"FALHA: {len(ERRORS)} erro(s) - corrigir ANTES de analisar jogos.")
    return 1 if ERRORS else 0


if __name__ == "__main__":
    sys.exit(main())
