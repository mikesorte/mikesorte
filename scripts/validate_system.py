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

    # (v17) contagem de campos por linha ANTES de qualquer DictReader.
    # Bug real de 30-31/07: virgula nao escapada dentro do campo 'casa'
    # (ex.: Superbet (odds reais, mesma casa 3 lados)) gerou linhas com 18-19
    # campos num CSV de 17 colunas. O DictReader engole o excedente na chave
    # None e desloca TODAS as colunas seguintes - o resultado do jogo foi
    # parar na coluna acerto_erro. O diagnostico passava limpo porque so
    # checava presenca de coluna no header e unicidade de id.
    with open(full, newline="", encoding="utf-8") as f:
        raw = list(csv.reader(f))
    if raw:
        ncols = len(raw[0])
        for i, row in enumerate(raw[1:], start=2):
            if not row:
                continue
            if len(row) != ncols:
                err(f"{path}: linha {i} com {len(row)} campos (esperado {ncols}) "
                    f"- provavel virgula nao escapada; campo com virgula PRECISA de aspas")

    with open(full, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        warn(f"{path}: vazio")
        return rows
    missing = [c for c in required_cols if c not in rows[0]]
    if missing:
        err(f"{path}: colunas ausentes {missing}")
    # campo extra capturado pelo DictReader = linha malformada
    for r in rows:
        if None in r:
            err(f"{path}: id={r.get(id_col)} tem campos alem do header (linha malformada)")
    ids = [r.get(id_col) for r in rows]
    if len(ids) != len(set(ids)):
        err(f"{path}: IDs duplicados")
    return rows


def check_doc(path, min_bytes=500):
    full = os.path.join(ROOT, path)
    if not os.path.exists(full):
        err(f"{path}: ARQUIVO AUSENTE - metodologia inacessivel (v16, ponto critico)")
        return
    size = os.path.getsize(full)
    if size < min_bytes:
        err(f"{path}: suspeito de truncamento/corrupcao ({size} bytes, esperado >={min_bytes})")


def main():
    # 0) metodologia versionada em git (v16) - fonte da verdade da trigger
    check_doc("docs/DAILY_METHODOLOGY.md")
    check_doc("docs/WEEKLY_METHODOLOGY.md")

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
        from betting_model import devig_power, poisson_dixon_coles, wilson_ci, ev_unitario, clv, win_by_margin
        f = devig_power([1.50, 4.20, 7.10])
        assert abs(sum(f) - 1) < 1e-6, "devig nao soma 1"
        assert 0.60 < f[0] < 0.70, f"devig favorito fora da faixa esperada: {f[0]}"
        m = poisson_dixon_coles(1.9, 0.8)
        assert abs(m["p_home"] + m["p_draw"] + m["p_away"] - 1) < 1e-9, "DC nao soma 1"
        assert abs(sum(m["margins"].values()) - 1) < 1e-6, "margins nao soma 1"
        assert abs(win_by_margin(m, 1) - m["p_home"]) < 1e-9, "win_by_margin(margem>=1) deveria bater com p_home (qualquer vitoria)"
        assert abs(win_by_margin(m, 0) - (m["p_home"] + m["p_draw"])) < 1e-9, "win_by_margin(margem>=0) deveria incluir empates"
        assert win_by_margin(m, 99) == 0, "win_by_margin com margem impossivel deveria ser 0"
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

    # 3b) regressao no parser de varredura ampla (v15) - schema sintetico da casa
    try:
        from scan_odds import parse_mres_blocks, is_liga_menor, LIGA_MENOR_DEFAULT
        synthetic = (
            '{"data":{"event":{"leagueName":"Liga Teste - Qualif.","name":"Time A - Time B","startTime":1785364200000,'
            '"markets":[{"id":"1","name":"Resultado Final","type":"MRES","selections":['
            '{"id":"1","name":"1","fullName":"Time A","price":2.0},'
            '{"id":"2","name":"X","fullName":"Empate","price":3.4},'
            '{"id":"3","name":"2","fullName":"Time B","price":4.0}]}]}}}'
        )
        evs = parse_mres_blocks(synthetic)
        assert len(evs) == 1, f"parser deveria achar 1 evento, achou {len(evs)}"
        e = evs[0]
        assert e["odds"] == [2.0, 3.4, 4.0], f"odds extraidas erradas: {e['odds']}"
        assert e["competition"] == "Liga Teste - Qualif.", f"competition errada: {e['competition']}"
        assert e["participants"] == "Time A - Time B", f"participants errado: {e['participants']}"
        assert is_liga_menor("Champions League - Qualificação", LIGA_MENOR_DEFAULT), "liga menor nao detectada (qualif)"
        assert not is_liga_menor("Brasileirao Serie A", LIGA_MENOR_DEFAULT), "falso positivo de liga menor"
    except AssertionError as e:
        err(f"scan_odds: REGRESSAO DETECTADA - {e}")
    except Exception as e:
        err(f"scan_odds: falha ao carregar/testar - {e}")

    # 3c) regressao no calendario de ligas (v17) - conhecimento de temporada
    try:
        from league_calendar import (ligas_ativas, ligas_por_prioridade,
                                     prioridade_busca, LIGAS)
        nomes = [lg["nome"] for lg in LIGAS]
        assert len(nomes) == len(set(nomes)), "league_calendar: liga duplicada"
        for lg in LIGAS:
            assert lg["meses"], f"league_calendar: {lg['nome']} sem meses"
            assert all(1 <= m <= 12 for m in lg["meses"]), f"league_calendar: mes invalido em {lg['nome']}"

        # A falha real de 31/07: nordicas em temporada em julho nao foram vistas.
        jul = {lg["nome"] for lg in ligas_ativas(7)}
        for obrigatoria in ("Allsvenskan (Suecia)", "Eliteserien (Noruega)",
                            "Veikkausliiga (Finlandia)", "Meistriliiga (Estonia)"):
            assert obrigatoria in jul, f"league_calendar: {obrigatoria} deveria estar ativa em julho"

        # Top-5 europeu esta em PRE-TEMPORADA em julho - nao deve aparecer como ativa
        for fora in ("Premier League", "LaLiga", "Bundesliga"):
            assert fora not in jul, f"league_calendar: {fora} nao deveria estar ativa em julho (pre-temporada)"

        # regra 8: liga menos eficiente e precificada deve ter prioridade MAIOR
        # que liga muito eficiente - senao a varredura volta a priorizar manchete
        elite = next(lg for lg in LIGAS if lg["nome"] == "Eliteserien (Noruega)")
        bra_a = next(lg for lg in LIGAS if lg["nome"] == "Brasileirao Serie A")
        assert prioridade_busca(elite) > prioridade_busca(bra_a), \
            "league_calendar: liga ineficiente precificada deveria ter prioridade > Brasileirao A (regra 8)"

        ordenadas = ligas_por_prioridade(7)
        assert len(ordenadas) == len(ligas_ativas(7)), "league_calendar: ordenacao perdeu ligas"
    except AssertionError as e:
        err(f"league_calendar: REGRESSAO DETECTADA - {e}")
    except Exception as e:
        err(f"league_calendar: falha ao carregar/testar - {e}")

    # 3d) regressao no parser de PDF da casa (v19) - canal de ultimo recurso
    # quando todos os conectores estao fora. Validado contra o export real da
    # Betano de 29/07 (31 eventos, nomes/odds corretos).
    try:
        from parse_odds_pdf import parse_eventos
        amostra = [
            "29/07 19:30", "Internacional", "Flamengo",
            "Brasil - Brasileirão - Série A Betano", "CA TURBINADA",
            "1", "3.90", "X", "3.50", "2", "2.07",
            "29/07 19:00", "Vasco da Gama", "Independiente Medellin",
            "Copa Sul-americana", "Primeiro jogo: 2-2",
            "1", "1.60", "X", "4.35", "2", "6.00",
        ]
        evs = parse_eventos(amostra)
        assert len(evs) == 2, f"parser de PDF deveria achar 2 eventos, achou {len(evs)}"
        assert evs[0]["casa"] == "Internacional", f"casa errada: {evs[0]['casa']}"
        assert evs[0]["fora"] == "Flamengo", f"fora errado: {evs[0]['fora']}"
        assert evs[0]["odds"] == [3.90, 3.50, 2.07], f"odds erradas: {evs[0]['odds']}"
        assert evs[1]["casa"] == "Vasco da Gama", f"casa errada: {evs[1]['casa']}"
        assert evs[1]["odds"] == [1.60, 4.35, 6.00], f"odds erradas: {evs[1]['odds']}"
        # selo promocional nao pode virar nome de time (bug real da 1a versao)
        assert "TURBINADA" not in evs[0]["fora"], "selo promocional virou nome de time"
    except AssertionError as e:
        err(f"parse_odds_pdf: REGRESSAO DETECTADA - {e}")
    except Exception as e:
        err(f"parse_odds_pdf: falha ao carregar/testar - {e}")

    # 3e) regressao no parser de fixtures globais (v20). Canal PROVADO em
    # 31/07: tavily_extract le worldfootball.net (server-rendered) e rendeu
    # 188 jogos em 75 competicoes no dia em que a execucao havia declarado
    # "1 jogo elegivel". Ancora = URL do match-report, que carrega competicao
    # e times de forma estruturada.
    try:
        from parse_fixtures import parse_dump
        amostra = (
            "Vålerenga IF\nVIF\n19:00\n[-:-](https://www.worldfootball.net/match-report/"
            "co129/norway-eliteserien/ma11796943/valerenga-if_hamarkameratene/)\n"
            "ART\n00:00\n[0:1](https://www.worldfootball.net/match-report/"
            "co1458/nicaragua-liga-primera/ma12288979/art-municipal-jalapa_real-esteli-fc/)\n"
        )
        js = parse_dump(amostra)
        assert len(js) == 2, f"parse_fixtures deveria achar 2 jogos, achou {len(js)}"
        assert js[0]["casa"] == "Valerenga If", f"casa errada: {js[0]['casa']}"
        assert js[0]["fora"] == "Hamarkameratene", f"fora errado: {js[0]['fora']}"
        assert js[0]["competicao"] == "Norway Eliteserien", f"competicao errada: {js[0]['competicao']}"
        assert js[0]["hora"] == "19:00", f"hora errada: {js[0]['hora']}"
        # jogo encerrado precisa ser distinguivel de agendado
        assert js[1]["placar"] == "0:1", f"placar nao capturado: {js[1]['placar']}"
        assert js[0]["placar"] in (None, "-:-"), "jogo agendado nao deveria ter placar"

        # (v21-c) data explicita da pagina TEM que ser capturada. Bug real de
        # 31/07: paginas de classificacao trazem jogos de outras datas
        # ("01.08.2026 16:00") e, fundidas ao dump de matches-today, faziam
        # jogo de AMANHA ser reportado como de HOJE - erro de identidade
        # (regra 0). Fredrikstad x Sandefjord entrou como 31/07 sendo 01/08.
        com_data = (
            "01.08.2026 16:00\nFredrikstad FK\n"
            "[-:-](https://www.worldfootball.net/match-report/"
            "co129/norway-eliteserien/ma999/fredrikstad-fk_sandefjord-fotball/)\n"
        )
        jd = parse_dump(com_data)
        assert len(jd) == 1, f"deveria achar 1 jogo, achou {len(jd)}"
        assert jd[0]["data"] == "2026-08-01", (
            f"data explicita da pagina nao capturada: {jd[0]['data']} "
            "- jogo de outra data vazaria como se fosse de hoje")
    except AssertionError as e:
        err(f"parse_fixtures: REGRESSAO DETECTADA - {e}")
    except Exception as e:
        err(f"parse_fixtures: falha ao carregar/testar - {e}")

    # 3f) regressao no registro de fontes de odds (v21). O ranking decide a
    # ordem de tentativa da execucao, entao a logica de prioridade precisa
    # estar certa: sucesso comprovado > nunca testado > ja falhou. A primeira
    # versao punha 0/1 ACIMA de nunca-testado, o que faria o sistema insistir
    # eternamente no que nao funciona em vez de descobrir alternativa.
    try:
        from odds_sources import plano_de_tentativa, CASAS, RESULTADOS, OK
        assert len(CASAS) == 9, f"deveriam ser as 9 casas licenciadas, ha {len(CASAS)}"
        assert OK in RESULTADOS, "vocabulario de resultado quebrado"
        plano = plano_de_tentativa()
        assert plano, "plano de tentativa vazio"
        rotulos = [p["historico"] for p in plano]
        if "nunca testado" in rotulos:
            i_novo = rotulos.index("nunca testado")
            falhados = [i for i, r in enumerate(rotulos)
                        if r.startswith("0/")]
            if falhados:
                assert i_novo < min(falhados), (
                    "prioridade invertida: combinacao que ja FALHOU esta acima "
                    "de uma nunca testada - o sistema pararia de descobrir")
    except AssertionError as e:
        err(f"odds_sources: REGRESSAO DETECTADA - {e}")
    except Exception as e:
        err(f"odds_sources: falha ao carregar/testar - {e}")

    # 4) a metodologia precisa manter a cascata de extracao explicita (v18).
    # Bug de processo real: por semanas o doc definia "metodo v9 = Nimble" e
    # caia direto para WebSearch, sem nunca citar Exa/Tavily - que estavam
    # instalados o tempo todo. Se alguem resumir o doc e apagar a cascata, o
    # sistema volta a ignorar dois conectores disponiveis.
    meth = os.path.join(ROOT, "docs/DAILY_METHODOLOGY.md")
    if os.path.exists(meth):
        with open(meth, encoding="utf-8") as f:
            txt = f.read().lower()
        for termo in ("exa", "tavily", "cascata"):
            if termo not in txt:
                err(f"docs/DAILY_METHODOLOGY.md: perdeu referencia a '{termo}' "
                    f"- a cascata de extracao (v18) precisa citar os 3 conectores")

    # relatorio
    # Banner de rota (v17-d): a trigger agendada ainda carrega um prompt
    # EMBUTIDO e desatualizado (v13) porque o servidor Claude_Code_Remote esta
    # fora ha dias e update_trigger nao pode ser aplicado. Este script roda no
    # passo 1 de QUALQUER versao do fluxo - entao e o ponto mais confiavel para
    # redirecionar a execucao para a metodologia real, versionada em git.
    print("=" * 68)
    print("ROTA OBRIGATORIA: a fonte da verdade da metodologia e")
    print("  docs/DAILY_METHODOLOGY.md  (git, atualmente v21)")
    print("Se o prompt desta execucao veio embutido na trigger agendada, ele")
    print("esta DESATUALIZADO - leia o arquivo acima e siga o fluxo de la.")
    print("Diferencas que o texto embutido antigo NAO tem: varredura por")
    print("catalogo e nao por manchete (v17), PE-first sem odds (v17),")
    print("nao competir com a casa no 1X2 (v17-b).")
    print("=" * 68)
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
