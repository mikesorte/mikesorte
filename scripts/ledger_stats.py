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
from pe_engine import PISO_ALTA, PISO_MODERADA  # noqa: E402


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
    # Achado de auditoria (08/08): o denominador era sum(contagem.values()),
    # que soma um HIT POR FAMILIA batida - uma linha de mercado combinado
    # (ex. id=8 "1X2/Total gols/BTTS/DNB/Escanteios") contava 5 vezes no
    # denominador mas so 1 vez no numerador de cada familia que bateu,
    # DILUINDO a concentracao real. Medido no ledger real: reportava "1X2:
    # 53% das linhas" quando na verdade 76,9% das linhas (10 de 13) TESTAM
    # 1X2 (mesmo que tambem testem outros mercados na mesma linha). O
    # denominador correto pro rotulo "% das linhas" e o numero de LINHAS
    # (len(detail)), nao a soma de hits - uma linha que testa 5 mercados
    # contribui pro numerador de ate 5 familias, entao os percentuais
    # legitimamente NAO somam 100% (cada um e "% das linhas que incluiram
    # este mercado", nao uma particao mutuamente exclusiva).
    contagem = {k: 0 for k in FAMILIAS}
    for r in detail:
        merc = (r.get("mercado") or "").lower()
        for fam, chaves in FAMILIAS.items():
            if any(c in merc for c in chaves):
                contagem[fam] += 1

    testados = len(detail)
    print("\n=== COBERTURA POR FAMILIA DE MERCADO (regra 8) ===")
    if testados:
        for fam, qtd in sorted(contagem.items(), key=lambda kv: -kv[1]):
            if qtd:
                print(f"{fam}: {qtd} ({qtd/testados:.0%} das linhas testaram este mercado)")
        p1x2 = contagem["1X2"] / testados
        if p1x2 > 0.5:
            print(f"\nALERTA: {p1x2:.0%} das linhas testaram 1X2 - o mercado MAIS eficiente.")
            print("A regra 8 diz que o valor tende a viver nos MENOS eficientes")
            print("(escanteios, cartoes, faltas, props, totais por equipe).")
            print("Testar so 1X2 e competir com a casa onde ela e mais forte.")
    else:
        print("(nenhuma linha de detalhe ainda)")

    print("\n=== PALPITES ESTATISTICOS (fonte: data/pe_ledger.csv) ===")
    PISO_AMOSTRA_PEQUENA = 10  # abaixo disso, so contexto - nunca conclusao
    for faixa in ("Alta", "Moderada", "Baixa"):
        rows = [r for r in pes if r.get("confianca") == faixa]
        if not rows:
            continue
        occ = sum(1 for r in rows if r.get("ocorreu") == "sim")
        nao = sum(1 for r in rows if r.get("ocorreu") == "nao")
        other = len(rows) - occ - nao
        res = occ + nao
        line = f"{faixa}: {occ}/{res} ocorreram" if res else f"{faixa}: 0 resolvidos"
        # achado de auditoria (08/08): este bloco nao avisava amostra
        # pequena, ao contrario do bloco de calibracao por familia logo
        # abaixo - inconsistencia de honestidade estatistica dentro do
        # mesmo script (o proprio N ja e visivel, mas sem o mesmo alerta
        # textual que o resto do relatorio usa).
        aviso_amostra = "" if res >= PISO_AMOSTRA_PEQUENA else f" (amostra < {PISO_AMOSTRA_PEQUENA} - so contexto, nenhuma conclusao valida)"
        print(f"{line}{aviso_amostra} (arquivado/retirado/pendente: {other}, total emitido: {len(rows)})")

    # CALIBRACAO POR MERCADO x CONFIANCA (v28) - o corte que a faixa esconde.
    # O estudo de ma-especificacao mostrou que a calibracao AGREGADA por faixa
    # pode parecer otima enquanto os mercados erram muito em direcoes OPOSTAS
    # e se cancelam: no mundo controle a faixa dava +1.8pp de vies enquanto
    # Over 2.5 estava +7.5pp e Under 3.5 estava -10.9pp. Faixa calibrada NAO
    # e evidencia de que o sistema sabe o que esta fazendo.
    #
    # Achado de auditoria (08/08): ate aqui a regra "ALERTA se desvio>5pp com
    # N>=10" so existia como TEXTO impresso, nunca como comparacao real em
    # codigo - nao havia nem um numero de "confianca afirmada" pra comparar
    # contra a taxa observada. Corrigido: agrupa por (mercado, confianca) e
    # compara a taxa observada contra o PISO que aquela confianca promete
    # (PISO_ALTA/PISO_MODERADA de pe_engine.py, a mesma constante usada pra
    # gerar o PE) - dispara ALERTA de verdade quando N>=10 e o desvio>5pp.
    print("\n--- Calibracao por FAMILIA DE MERCADO x CONFIANCA (regra v28) ---")
    piso_por_confianca = {"Alta": PISO_ALTA, "Moderada": PISO_MODERADA}
    grupos = {}
    for r in pes:
        if r.get("ocorreu") not in ("sim", "nao"):
            continue
        fam = (r.get("mercado") or "?").strip()
        conf = (r.get("confianca") or "?").strip()
        grupos.setdefault((fam, conf), []).append(r.get("ocorreu") == "sim")
    if not grupos:
        print("  Nenhum PE resolvido ainda - nada a calibrar por mercado.")
        print(f"  Este corte so vira ALERTA de verdade quando houver >={PISO_AMOSTRA_PEQUENA} por grupo.")
    else:
        algum_alerta = False
        for (fam, conf), occs in sorted(grupos.items(), key=lambda t: -len(t[1])):
            qtd = len(occs)
            taxa = sum(occs) / qtd
            piso = piso_por_confianca.get(conf)
            rotulo = f"{fam} [{conf}]"
            if qtd < PISO_AMOSTRA_PEQUENA:
                print(f"  {rotulo:<40} {sum(occs)}/{qtd} = {taxa:.0%}  (amostra < {PISO_AMOSTRA_PEQUENA} - so contexto)")
                continue
            if piso is None:
                print(f"  {rotulo:<40} {sum(occs)}/{qtd} = {taxa:.0%}  (sem piso numerico p/ '{conf}' - so contexto)")
                continue
            desvio = taxa - piso
            if abs(desvio) > 0.05:
                algum_alerta = True
                print(f"  {rotulo:<40} {sum(occs)}/{qtd} = {taxa:.0%}  *** ALERTA: desvio {desvio:+.1%} "
                      f"vs piso {conf} ({piso:.0%}), N={qtd}>={PISO_AMOSTRA_PEQUENA} ***")
            else:
                print(f"  {rotulo:<40} {sum(occs)}/{qtd} = {taxa:.0%}  (dentro de 5pp do piso {conf} {piso:.0%})")
        if not algum_alerta:
            print("  Nenhum grupo com N>=10 e desvio>5pp ainda (amostra geral pequena demais pra maioria).")

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
