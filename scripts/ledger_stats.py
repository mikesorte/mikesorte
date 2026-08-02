#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Estatisticas oficiais do sistema, calculadas DIRETO do ledger (v13).
    python3 scripts/ledger_stats.py
Elimina erro de transcricao: todo numero de relatorio/PDF sai daqui,
nunca de tabela copiada a mao.
"""
import csv
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from betting_model import wilson_ci  # noqa: E402


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def main():
    with open(os.path.join(ROOT, "data/apostas_ledger.csv"), newline="", encoding="utf-8") as f:
        apostas = list(csv.DictReader(f))
    with open(os.path.join(ROOT, "data/pe_ledger.csv"), newline="", encoding="utf-8") as f:
        pes = list(csv.DictReader(f))

    # --- agregados historicos (linhas 'agregado' preservam semanas pre-ledger)
    agg_a = agg_e = agg_nv = 0
    detail = []
    for r in apostas:
        if r.get("acerto_erro") == "agregado":
            # formato "3A/3E/1NV" ou "2A/3E"
            for part in r.get("resultado", "").split("/"):
                part = part.strip().upper()
                if part.endswith("NV"):
                    agg_nv += int(part[:-2])
                elif part.endswith("A"):
                    agg_a += int(part[:-1])
                elif part.endswith("E"):
                    agg_e += int(part[:-1])
        else:
            detail.append(r)

    det_a = sum(1 for r in detail if r.get("acerto_erro") == "acerto")
    det_e = sum(1 for r in detail if r.get("acerto_erro") == "erro")
    det_pend = sum(1 for r in detail if r.get("acerto_erro") in ("", "pendente"))

    wins, n = agg_a + det_a, agg_a + agg_e + det_a + det_e
    p, lo, hi = wilson_ci(wins, n) if n else (0, 0, 0)

    # P&L so das linhas com odd conhecida e resolvidas
    pl = units = 0.0
    for r in detail:
        o = _f(r.get("odd_entrada"))
        if o is None or r.get("acerto_erro") not in ("acerto", "erro"):
            continue
        units += 1
        pl += (o - 1) if r["acerto_erro"] == "acerto" else -1

    clvs = [c for r in detail if (c := _f(r.get("clv"))) is not None]

    print("=== APOSTAS DE VALOR (fonte: data/apostas_ledger.csv) ===")
    print(f"N resolvido: {n} | acertos {wins} | erros {agg_e + det_e} | nao-verif. {agg_nv} | pendentes {det_pend}")
    print(f"Taxa: {p:.1%} [Wilson 95%: {lo:.1%} - {hi:.1%}]")
    print(f"P&L (apostas com odd conhecida, N={units:.0f}): {pl:+.2f}u = R$ {pl*20:+.2f}")
    if clvs:
        print(f"CLV medio (N={len(clvs)}): {sum(clvs)/len(clvs):+.2%}")
    else:
        print("CLV medio: SEM DADOS (nenhuma odd de fechamento registrada ainda)")

    # --- concentracao por familia de mercado (v17)
    # Achado de 31/07: os ultimos dias testaram 1X2 QUASE EXCLUSIVAMENTE - o
    # mercado MAIS eficiente e liquido - usando lambdas proxy (a entrada mais
    # fraca). A regra 8 e a 6.2-f dizem o oposto: 1X2 nao e default, o valor
    # tende a viver nos mercados menos eficientes. Isto fica visivel aqui para
    # nao voltar a acontecer silenciosamente.
    FAMILIAS = {
        "1X2": ("1x2",),
        "Gols/Totais": ("total de gols", "over", "under", "gols"),
        "BTTS": ("btts", "ambas"),
        "Escanteios": ("escanteio", "cantos"),
        "Cartoes/Faltas": ("cartao", "cartoes", "falta"),
        "DNB/AH/DC": ("dnb", "handicap", "dupla chance", "empate anula"),
        "Props": ("prop", "finalizac", "desarme", "chutes"),
    }
    contagem = {k: 0 for k in FAMILIAS}
    for r in detail:
        merc = (r.get("mercado") or "").lower()
        for fam, chaves in FAMILIAS.items():
            if any(c in merc for c in chaves):
                contagem[fam] += 1

    testados = sum(contagem.values())
    print("\n=== COBERTURA POR FAMILIA DE MERCADO (regra 8) ===")
    if testados:
        for fam, qtd in sorted(contagem.items(), key=lambda kv: -kv[1]):
            if qtd:
                print(f"{fam}: {qtd} ({qtd/testados:.0%} das linhas)")
        p1x2 = contagem["1X2"] / testados
        if p1x2 > 0.5:
            print(f"\nALERTA: {p1x2:.0%} das linhas sao 1X2 - o mercado MAIS eficiente.")
            print("A regra 8 diz que o valor tende a viver nos MENOS eficientes")
            print("(escanteios, cartoes, faltas, props, totais por equipe).")
            print("Testar so 1X2 e competir com a casa onde ela e mais forte.")
    else:
        print("(nenhuma linha de detalhe ainda)")

    print("\n=== PALPITES ESTATISTICOS (fonte: data/pe_ledger.csv) ===")
    for faixa in ("Alta", "Moderada", "Baixa"):
        rows = [r for r in pes if r.get("confianca") == faixa]
        if not rows:
            continue
        occ = sum(1 for r in rows if r.get("ocorreu") == "sim")
        nao = sum(1 for r in rows if r.get("ocorreu") == "nao")
        other = len(rows) - occ - nao
        res = occ + nao
        line = f"{faixa}: {occ}/{res} ocorreram" if res else f"{faixa}: 0 resolvidos"
        print(f"{line} (arquivado/retirado/pendente: {other}, total emitido: {len(rows)})")

    # CALIBRACAO POR MERCADO (v28) - o corte que a faixa esconde.
    # O estudo de ma-especificacao mostrou que a calibracao AGREGADA por faixa
    # pode parecer otima enquanto os mercados erram muito em direcoes OPOSTAS
    # e se cancelam: no mundo controle a faixa dava +1.8pp de vies enquanto
    # Over 2.5 estava +7.5pp e Under 3.5 estava -10.9pp. Faixa calibrada NAO
    # e evidencia de que o sistema sabe o que esta fazendo.
    print("\n--- Calibracao por FAMILIA DE MERCADO (regra v28) ---")
    familias = {}
    for r in pes:
        if r.get("ocorreu") not in ("sim", "nao"):
            continue
        fam = (r.get("mercado") or "?").strip()
        familias.setdefault(fam, []).append(r.get("ocorreu") == "sim")
    if not familias:
        print("  Nenhum PE resolvido ainda - nada a calibrar por mercado.")
        print("  Este corte so passa a valer quando houver >=10 por familia.")
    else:
        for fam, occs in sorted(familias.items(), key=lambda t: -len(t[1])):
            qtd = len(occs)
            taxa = sum(occs) / qtd
            aviso = "" if qtd >= 10 else "  (amostra < 10 - so contexto)"
            print(f"  {fam:<28} {sum(occs)}/{qtd} = {taxa:.0%}{aviso}")
        print("  ALERTA se, com N>=10 numa familia, o desvio entre a confianca")
        print("  afirmada e a taxa observada passar de 5pp - mesmo que a faixa")
        print("  agregada esteja calibrada.")

    # guarda contra shadowing acidental de 'n' por blocos inseridos acima
    # (bug real introduzido e pego em 31/07: um 'for fam, n in ...' sobrescreveu
    # o N do ledger e o aviso final passou a imprimir N=0)
    assert n == agg_a + agg_e + det_a + det_e, \
        f"N corrompido antes do aviso final ({n}) - variavel sobrescrita?"

    if n < 50:
        print(f"\nAviso: N={n} < 50 (primeiro checkpoint). Nenhuma conclusao estatistica valida ainda.")
    elif n < 300:
        print(f"\nAviso: N={n} < 300. CLV comeca a ser informativo ~300; ROI confiavel ~500-1000.")


if __name__ == "__main__":
    main()
