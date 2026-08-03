#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BACKTEST COM DADO REAL - mercado de escanteios (Fase 1, v32).

Mesma disciplina do precedente v28->v29 (scripts/backtest_real.py): so
aceitar um modelo novo com validacao em dado REAL, nunca em simulacao
propria ("mundo" inventado vira overfitting a fantasia).

ALGORITMO WALK-FORWARD, SEM VAZAMENTO (ver docs/DAILY_METHODOLOGY.md v32)
--------------------------------------------------------------------------
1. Todos os jogos das 5 ligas com stats (HC/AC), de TODOS os arquivos de
   temporada, ordenados por DATA explicita (nao pela ordem do arquivo).
2. Para cada jogo, NESTA ordem: primeiro gerar a previsao usando so o
   historico e a media de liga acumulados ATE ALI; SO DEPOIS anexar este
   jogo ao historico dos dois times e a media expansivel da liga. A media
   da liga tambem tem que ser expansivel (nao a temporada inteira de uma
   vez) - e o vazamento mais comum e mais sutil nesse tipo de backtest.
3. Chave de historico = (liga, nome_time), nao so nome - evita colisao
   entre ligas.
4. TESTE DE SANIDADE OBRIGATORIO - COMPARACAO COM ORACULO: gera uma versao
   deliberadamente trapaceira (usa a media da TEMPORADA INTEIRA de cada
   time, incluindo jogos futuros, como lambda) e compara o Brier dela
   contra o walk-forward honesto. Por definicao, ver o futuro so pode
   ajudar (ou empatar) - se o walk-forward honesto vier IGUAL OU MELHOR
   que o oraculo, isso e prova de bug (vazamento) no pipeline, nao uma boa
   noticia. (Nota de design: uma versao anterior deste teste usava so
   inverter a ordem cronologica como canario, mas isso nao e diagnostico
   aqui - as duas direcoes sao causalmente consistentes dentro de si
   mesmas, entao inverter testa sensibilidade a ordem, nao vazamento real
   de informacao futura. A comparacao com oraculo e o teste que realmente
   isola o efeito.)

LIMITACOES DECLARADAS (nao escondidas no relatorio):
  - Validacao e so AGREGADA/POOLED (bins de calibracao, Brier, IC de
    Wilson) - a amostra por time e pequena demais pra validar "o lambda do
    time X esta certo".
  - Dado vai ate ~2013 (ver scripts/baixa_dados_backtest.py) - futebol
    mudou desde entao (VAR, pressing).
  - lambda_total estimado como media dos dois lambdas de "pace" por time
    (EWMA+shrinkage do total de escanteios nos jogos de cada time) - e uma
    heuristica simples de v1, nao um modelo de interacao entre os times.

Uso:
    python3 scripts/backtest_escanteios.py
    python3 scripts/backtest_escanteios.py --detalhe
"""
import argparse
import csv
import glob
import os
import sys
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from betting_model import poisson_total, negbin_total, ewma_shrinkage, wilson_ci, brier

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DADOS = os.path.join(ROOT, "data", "backtest")
LINHAS = (8.5, 9.5, 10.5, 11.5)
ALPHA_SHRINKAGE = 3.0
# configs testadas: None = Poisson puro; numero = forma da binomial negativa
# (menor = mais superdisperso). Mesma logica de "cenarios" do backtest_real.py.
CONFIGS = {"poisson": None, "negbin_forma8": 8.0, "negbin_forma4": 4.0}


def _parse_data(s):
    for fmt in ("%d/%m/%y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError(f"data nao reconhecida: {s!r}")


def carrega_jogos_com_stats(colunas_casa=("HC",), colunas_fora=("AC",)):
    """Le todos os CSVs que tenham as colunas pedidas, ordena por data
    explicita. Generico o bastante pra reuso por escanteios (HC/AC),
    cartoes (HY,HR / AY,AR) e chutes-a-gol (HST/AST) - ver
    scripts/backtest_cartoes.py e scripts/backtest_chutes.py.

    Devolve lista de dicts: liga, data, casa, fora, total (soma das
    colunas_casa do mandante + colunas_fora do visitante)."""
    jogos = []
    todas_colunas = list(colunas_casa) + list(colunas_fora)
    for caminho in sorted(glob.glob(os.path.join(DADOS, "*.csv"))):
        liga = os.path.basename(caminho).split("_s")[0].replace(".csv", "")
        with open(caminho, encoding="utf-8", errors="replace") as f:
            for r in csv.DictReader(f):
                try:
                    if any(not r.get(c) for c in todas_colunas):
                        continue
                    v_casa = sum(int(r[c]) for c in colunas_casa)
                    v_fora = sum(int(r[c]) for c in colunas_fora)
                    data = _parse_data(r["Date"])
                    casa, fora = r["HomeTeam"], r["AwayTeam"]
                except (KeyError, ValueError, TypeError):
                    continue
                if not casa or not fora:
                    continue
                jogos.append({"liga": liga, "data": data, "casa": casa,
                              "fora": fora, "total": v_casa + v_fora,
                              "valor_casa": v_casa, "valor_fora": v_fora})
    jogos.sort(key=lambda j: j["data"])
    return jogos


def walk_forward_lambdas(jogos, alpha=ALPHA_SHRINKAGE, forma=None, linhas=None):
    """Gera (jogo, previsao) por jogo, SEM vazamento (ver docstring do
    modulo). forma=None usa Poisson puro; numero usa negbin_total (v32,
    so entra se o backtest validar melhora real - ver main()). linhas=None
    usa o default do modulo (escanteios) - outros mercados (cartoes,
    chutes) passam suas proprias linhas."""
    linhas = linhas if linhas is not None else LINHAS
    historico_time = defaultdict(list)   # (liga, time) -> [totais anteriores]
    liga_expandida = defaultdict(list)   # liga -> [totais anteriores na liga]

    saida = []
    for jogo in jogos:
        liga, casa, fora = jogo["liga"], jogo["casa"], jogo["fora"]
        hist_casa = historico_time[(liga, casa)]
        hist_fora = historico_time[(liga, fora)]
        media_liga = (sum(liga_expandida[liga]) / len(liga_expandida[liga])
                      if liga_expandida[liga] else jogo["total"])  # 1o jogo da liga: sem prior melhor

        lam_casa = ewma_shrinkage(hist_casa, media_liga, alpha=alpha)
        lam_fora = ewma_shrinkage(hist_fora, media_liga, alpha=alpha)
        lam_total = (lam_casa + lam_fora) / 2.0

        previsao = negbin_total(lam_total, forma, linhas=linhas)
        saida.append((jogo, previsao))

        # SO AGORA atualiza o estado - depois de ja ter gerado a previsao
        historico_time[(liga, casa)].append(jogo["total"])
        historico_time[(liga, fora)].append(jogo["total"])
        liga_expandida[liga].append(jogo["total"])
    return saida


def calibracao(pares_por_mercado):
    """{mercado: [(prob_afirmada, ocorreu), ...]} -> resumo por mercado."""
    out = {}
    for mercado, pares in pares_por_mercado.items():
        n = len(pares)
        if not n:
            continue
        af = sum(p for p, _ in pares) / n
        real = sum(1 for _, o in pares if o) / n
        b = brier(pares)
        k = sum(1 for _, o in pares if o)
        _, lo, hi = wilson_ci(k, n)
        out[mercado] = {"n": n, "afirmado": af, "real": real, "vies": af - real,
                         "brier": b, "wilson_lo": lo, "wilson_hi": hi,
                         "dentro_ic": lo <= af <= hi}
    return out


def oraculo_lambdas(jogos, alpha=ALPHA_SHRINKAGE, linhas=None):
    """Versao DELIBERADAMENTE trapaceira: usa a media da temporada/liga
    inteira (passado E futuro) como lambda de cada time, em vez de so o
    historico anterior. Serve unicamente de teto de referencia para o
    teste de sanidade - nunca usar isto como previsao de verdade."""
    linhas = linhas if linhas is not None else LINHAS
    totais_por_time = defaultdict(list)
    totais_por_liga = defaultdict(list)
    for jogo in jogos:
        totais_por_time[(jogo["liga"], jogo["casa"])].append(jogo["total"])
        totais_por_time[(jogo["liga"], jogo["fora"])].append(jogo["total"])
        totais_por_liga[jogo["liga"]].append(jogo["total"])

    medias_time = {k: sum(v) / len(v) for k, v in totais_por_time.items()}
    medias_liga = {k: sum(v) / len(v) for k, v in totais_por_liga.items()}

    saida = []
    for jogo in jogos:
        liga, casa, fora = jogo["liga"], jogo["casa"], jogo["fora"]
        media_liga = medias_liga[liga]
        n_casa = len(totais_por_time[(liga, casa)])
        n_fora = len(totais_por_time[(liga, fora)])
        lam_casa = (alpha * media_liga + n_casa * medias_time[(liga, casa)]) / (alpha + n_casa)
        lam_fora = (alpha * media_liga + n_fora * medias_time[(liga, fora)]) / (alpha + n_fora)
        lam_total = (lam_casa + lam_fora) / 2.0
        saida.append((jogo, poisson_total(lam_total, linhas=linhas)))
    return saida


def teste_embaralhamento(jogos, alpha=ALPHA_SHRINKAGE, forma=None, linhas=None, seed=42):
    """Teste de sanidade SECUNDARIO (v32) - so precisa rodar quando o
    canario do oraculo (ver oraculo_lambdas) "falha", isto e, quando o
    walk-forward honesto bate o oraculo em Brier.

    POR QUE ISSO PODE ACONTECER SEM SER VAZAMENTO: o oraculo usa media
    CHEIA da temporada (sem peso por recencia), enquanto o walk-forward
    honesto usa EWMA (pesa jogos recentes mais). Se o mercado tiver
    tendencia real de curto prazo (forma recente do time muda ao longo da
    temporada), o EWMA pode genuinamente capturar mais sinal que uma media
    plana - mesmo sem nunca olhar o futuro. Ou seja, o oraculo NAO E um
    teto matematico garantido (nao domina estritamente o walk-forward),
    entao "honesto bate oraculo" nao e prova automatica de bug.

    O teste decisivo: embaralhar a ordem dos jogos (destroi qualquer
    estrutura temporal real, mas mantem o pipeline predict-antes-de-
    atualizar identico). Se a vantagem do walk-forward sobre o oraculo
    SOME (ou inverte) quando embaralhado, a vantagem original era sinal
    real de recencia, nao vazamento - um pipeline com vazamento continuaria
    "ganhando" mesmo com a ordem embaralhada, porque o vazamento nao
    depende de ordem cronologica real."""
    import random
    linhas = linhas if linhas is not None else LINHAS
    embaralhados = jogos[:]
    random.Random(seed).shuffle(embaralhados)
    prev_honesto = walk_forward_lambdas(embaralhados, alpha=alpha, forma=forma, linhas=linhas)
    prev_oraculo = oraculo_lambdas(embaralhados, alpha=alpha, linhas=linhas)
    b_honesto = brier([p for m in avalia(prev_honesto, linhas=linhas).values() for p in m])
    b_oraculo = brier([p for m in avalia(prev_oraculo, linhas=linhas).values() for p in m])
    return b_honesto, b_oraculo


def avalia(previsoes, linhas=None):
    """previsoes: [(jogo, previsao), ...] -> {mercado: [(prob, ocorreu)]}"""
    linhas = linhas if linhas is not None else LINHAS
    out = defaultdict(list)
    for jogo, previsao in previsoes:
        total_real = jogo["total"]
        for linha in linhas:
            chave = f"over_{linha}"
            out[chave].append((previsao[chave], total_real > linha))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--detalhe", action="store_true")
    args = ap.parse_args()

    jogos = carrega_jogos_com_stats()
    if not jogos:
        print("Nenhum jogo com HC/AC encontrado - rode baixa_dados_backtest.py primeiro.")
        return 1

    ligas = sorted({j["liga"] for j in jogos})
    print("=== BACKTEST COM DADO REAL - ESCANTEIOS (v32) ===")
    print(f"Jogos: {len(jogos)} | Ligas: {len(ligas)} ({', '.join(ligas)})")
    print(f"Periodo: {jogos[0]['data'].date()} a {jogos[-1]['data'].date()}\n")

    # --- testa Poisson puro vs binomial negativa (varios 'forma') ---
    resultados = {}
    for nome, forma in CONFIGS.items():
        previsoes = walk_forward_lambdas(jogos, forma=forma)
        pares_por_mercado = avalia(previsoes)
        cal = calibracao(pares_por_mercado)
        todos_pares = [p for m in pares_por_mercado.values() for p in m]
        resultados[nome] = {"cal": cal, "brier_global": brier(todos_pares),
                             "previsoes": previsoes}

    print("--- CALIBRACAO GLOBAL por configuracao ---")
    print(f"{'config':<16} {'Brier global':>13} {'maior vies abs':>16} {'mercados fora IC':>18}")
    for nome, r in resultados.items():
        vies_max = max(abs(c["vies"]) for c in r["cal"].values())
        fora = sum(1 for c in r["cal"].values() if not c["dentro_ic"])
        print(f"{nome:<16} {r['brier_global']:>13.5f} {vies_max:>15.1%} {fora:>18}")

    melhor_nome = min(resultados, key=lambda n: resultados[n]["brier_global"])
    print(f"\nMelhor Brier global: {melhor_nome}")

    print(f"\n--- CALIBRACAO POR MERCADO [{melhor_nome}] ---")
    cal = resultados[melhor_nome]["cal"]
    print(f"{'mercado':<12} {'N':>6} {'afirmado':>9} {'real':>8} {'vies':>8} {'Brier':>9} {'IC 95%':>18}")
    for m in sorted(cal):
        c = cal[m]
        ic = f"[{c['wilson_lo']:.1%},{c['wilson_hi']:.1%}]"
        marca = "ok" if c["dentro_ic"] else "FORA"
        print(f"{m:<12} {c['n']:>6} {c['afirmado']:>8.1%} {c['real']:>7.1%} "
              f"{c['vies']:>+7.1%} {c['brier']:>9.5f} {ic:>18} {marca}")

    # --- canario: oraculo (media da temporada inteira, ve o futuro), so no melhor config ---
    previsoes_oraculo = oraculo_lambdas(jogos)
    brier_oraculo = brier([p for m in avalia(previsoes_oraculo) for p in avalia(previsoes_oraculo)[m]])
    brier_melhor = resultados[melhor_nome]["brier_global"]

    print("\n--- TESTE DE SANIDADE (canario: oraculo ve a temporada inteira) ---")
    print(f"Brier walk-forward honesto ({melhor_nome}): {brier_melhor:.5f}")
    print(f"Brier oraculo (ve o futuro):              {brier_oraculo:.5f}")
    if brier_melhor <= brier_oraculo:
        print("Walk-forward honesto bateu o oraculo em Brier - nao e prova automatica de "
              "bug (oraculo usa media plana, sem peso por recencia; ver docstring de "
              "teste_embaralhamento). Rodando teste decisivo: embaralhar a ordem dos jogos.")
        b_honesto_emb, b_oraculo_emb = teste_embaralhamento(jogos, forma=CONFIGS[melhor_nome])
        print(f"  embaralhado: honesto={b_honesto_emb:.5f} oraculo={b_oraculo_emb:.5f}")
        if b_honesto_emb <= b_oraculo_emb:
            print("ALERTA: a vantagem PERSISTE mesmo embaralhado - sinal de vazamento "
                  "(nao depende de ordem cronologica real). NAO aceitar sem investigar.")
            veredito_sanidade = False
        else:
            print("OK: a vantagem SOME quando embaralhado - confirma sinal real de "
                  "recencia via EWMA, nao vazamento.")
            veredito_sanidade = True
    else:
        print(f"OK: oraculo (que trapaceia vendo o futuro) tem Brier "
              f"{(brier_melhor - brier_oraculo) / brier_melhor:.1%} melhor que o "
              "walk-forward honesto, como esperado - nao ha indicio de vazamento.")
        veredito_sanidade = True

    if args.detalhe:
        print("\n--- DETALHE por mercado, todas as configs ---")
        for nome, r in resultados.items():
            print(f"\n  [{nome}]")
            for m in sorted(r["cal"]):
                c = r["cal"][m]
                print(f"    {m}: N={c['n']} afirma {c['afirmado']:.1%} real {c['real']:.1%} "
                      f"[{c['wilson_lo']:.1%},{c['wilson_hi']:.1%}] "
                      f"{'ok' if c['dentro_ic'] else 'FORA do IC'}")

    print("\n--- VEREDITO ---")
    todos_dentro = all(c["dentro_ic"] for c in cal.values())
    vies_max = max(abs(c["vies"]) for c in cal.values())
    print(f"Config escolhida: {melhor_nome}")
    print(f"Todos os mercados dentro do IC de Wilson: {todos_dentro}")
    print(f"Maior vies absoluto entre os mercados: {vies_max:.1%}")
    if not veredito_sanidade:
        print("REJEITADO: teste de sanidade indica vazamento - corrigir o pipeline "
              "antes de reconsiderar.")
    elif todos_dentro:
        print(f"ACEITO ({melhor_nome}): calibracao agregada dentro do IC de Wilson em "
              "todos os mercados, sanidade OK. Liberado para uso como candidato em "
              "pe_engine.py (Fase 3).")
    elif vies_max <= 0.015:
        print(f"ACEITO COM RESSALVA ({melhor_nome}): 1+ mercado(s) levemente fora do IC "
              f"(N muito grande deixa o IC estreito), mas vies maximo de {vies_max:.1%} "
              "e pequeno em termos absolutos - aceitavel para v1, mas declarar a ressalva "
              "sempre que este mercado for usado num palpite.")
    else:
        print("REJEITADO: vies fora do IC e grande o suficiente para nao promover a "
              "producao sem investigar a causa (mesma disciplina do precedente "
              "v28->v29 - nao aceitar so porque 'parece razoavel').")
    print("\nLIMITACOES: validacao agregada/pooled, nao por time; dado ate ~2013; "
          "lambda_total = media de duas tendencias de 'pace' por time (heuristica v1).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
