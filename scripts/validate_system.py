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
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone

BRT = timezone(timedelta(hours=-3))

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
    # BRT explicito, nunca date.today() (fuso do servidor/UTC) - achado de
    # auditoria (08/08), mesma classe do bug real cometido ao vivo nesta
    # sessao (perto da meia-noite UTC, "hoje" em BRT ainda e ontem - um
    # jogo de hoje BRT seria erroneamente marcado "pendente de jogo
    # passado" ou vice-versa, dependendo do lado da virada).
    today = datetime.now(BRT).date().isoformat()  # YYYY-MM-DD compara lexicograficamente
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

        # achado de auditoria (08/08): devig_shin, devig_proporcional, brier
        # e kelly_fraction nunca tinham teste de regressao com valor
        # conhecido, apesar de devig_shin ser o de-vig PADRAO de producao
        # desde a decisao 42 (ligado ao pipeline real em scan_odds.py, v37).
        from betting_model import devig_shin, devig_proporcional, brier, kelly_fraction
        odds_3vias = [1.50, 4.20, 7.10]
        s = devig_shin(odds_3vias)
        assert abs(sum(s) - 1) < 1e-6, "devig_shin nao soma 1"
        pr = devig_proporcional(odds_3vias)
        assert abs(sum(pr) - 1) < 1e-6, "devig_proporcional nao soma 1"
        # correcao do vies favorito-azarao (decisao 42): Shin, comparado ao
        # proporcional (baseline mais simples, sem correcao nenhuma), da
        # MAIS probabilidade ao favorito e MENOS ao azarao - e assim que a
        # literatura (Shin 1992/93) diz que o metodo deveria se comportar.
        # Comparar Shin contra POWER (nao proporcional) NAO testa a mesma
        # coisa - POWER ja e uma correcao mais sofisticada que proporcional,
        # a direcao so fica limpa contra o baseline mais simples.
        assert s[0] > pr[0], f"Shin deveria dar mais prob ao favorito que o proporcional: {s[0]} <= {pr[0]}"
        assert s[-1] < pr[-1], f"Shin deveria dar menos prob ao azarao que o proporcional: {s[-1]} >= {pr[-1]}"
        try:
            devig_shin([2.10, 2.10])
            err("motor: devig_shin aceitou odds sem margem (deveria rejeitar, regra v8)")
        except ValueError:
            pass
        try:
            devig_proporcional([2.10, 2.10])
            err("motor: devig_proporcional aceitou odds sem margem (deveria rejeitar, regra v8)")
        except ValueError:
            pass

        assert abs(brier([(0.7, 1), (0.3, 0), (0.6, 1)]) - 0.11333333333) < 1e-8, \
            "brier([(0.7,1),(0.3,0),(0.6,1)]) deveria ser 0.34/3"
        assert brier([]) is None, "brier([]) deveria devolver None, nao crashar"

        assert abs(kelly_fraction(0.55, 2.0) - 0.025) < 1e-9, "kelly_fraction(0.55,2.0) deveria ser 2.5%"
        assert kelly_fraction(0.30, 2.0) == 0.0, "kelly_fraction com EV negativo deveria ser 0 (nunca negativo)"
        try:
            kelly_fraction(0.55, 1.0)
            err("motor: kelly_fraction aceitou odd=1.0 (deveria rejeitar - ZeroDivisionError antigo, achado de auditoria)")
        except ValueError:
            pass
        try:
            kelly_fraction(0.55, 0.9)
            err("motor: kelly_fraction aceitou odd<1.0 (deveria rejeitar - nao existe em decimal odds)")
        except ValueError:
            pass

        # achado de auditoria (08/08): Dixon-Coles pode gerar probabilidade
        # negativa numa celula em favoritos extremos (lambda alto * rho
        # forte) - clampada em 0 desde o fix; confirma que o grid nunca
        # tem valor negativo mesmo no caso de fronteira que expos o bug.
        m_extremo = poisson_dixon_coles(5.71, 0.5, rho=-0.18)
        assert all(v >= 0 for v in (m_extremo["p_home"], m_extremo["p_draw"], m_extremo["p_away"])), \
            "poisson_dixon_coles com favorito extremo produziu probabilidade negativa"

        # achado de auditoria (08/08): poisson_grid/over_under_time tinha
        # truncamento quebrado - lambda alto perto/acima de max_n dava ~0%
        # de over nao importa o valor real. Fix usa a marginal Poisson
        # direta (tail-safe), independente do grid conjunto truncado.
        from betting_model import poisson_grid, over_under_time
        pg_extremo = poisson_grid(20, 20, max_n=15)
        over_alto = over_under_time(pg_extremo, "a", 15.5)
        assert over_alto > 0.80, \
            f"over_under_time(lambda=20, linha=15.5) deveria ser proximo de 0.84, veio {over_alto}"
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

        # (v24) filtros de escopo sobre o catalogo bruto da casa. Auditoria de
        # 01/08 sobre 542 eventos reais: 64 femininos (decisao 9 exclui), 28
        # base/reserva, 49 amistosos (regra 0), 39 de outro dia BRT. Sem isso
        # o catalogo ENGANA - parece cobertura, mas 33% nao pode virar aposta.
        from scan_odds import eh_feminino, eh_base_ou_reserva, eh_amistoso, filtrar_elegiveis
        def _ev(p, c=""):
            return {"participants": p, "competition": c}
        assert eh_feminino(_ev("Club Tijuana (F) - CF Monterrey (F)", "Liga MX Femenil (F)")), \
            "feminino nao detectado (decisao 9 do usuario)"
        # ARMADILHA REAL: clubes ADULTOS com 'Junior(s)' no nome nao podem ser
        # descartados como base. O filtro inicial os pegava por engano.
        assert not eh_base_ou_reserva(_ev("CA Belgrano - Argentinos Juniors", "Liga Profesional")), \
            "Argentinos Juniors (clube adulto) classificado como base"
        assert not eh_base_ou_reserva(_ev("Boca Juniors - River Plate", "Liga Profesional")), \
            "Boca Juniors (clube adulto) classificado como base"
        assert not eh_base_ou_reserva(_ev("Atlético Junior - Millonarios FC", "Primera A")), \
            "Atletico Junior (clube adulto) classificado como base"
        # reserva de verdade: sufixo II/B avaliado POR TIME (bug real: testar na
        # string concatenada com a competicao quebrava a ancora de fim)
        assert eh_base_ou_reserva(_ev("Bremer SV - Hannover 96 II", "Regionalliga Norte")), \
            "time reserva com sufixo II nao detectado"
        assert eh_base_ou_reserva(_ev("Real Madrid B - Getafe", "Primera Federacion")), \
            "time reserva com sufixo B nao detectado"
        assert eh_amistoso(_ev("Willem II - OFI Creta", "Jogos amistosos em destaque")), \
            "amistoso nao detectado (regra 0)"
        assert not eh_amistoso(_ev("Inter Miami CF - Columbus Crew SC", "MLS")), \
            "falso positivo de amistoso"
        # jogo de outro dia BRT tem que sair (regra 0 - 'UTC engana')
        ontem = {"participants": "A - B", "competition": "X",
                 "start_time": "1785500000000"}
        el, mot = filtrar_elegiveis([ontem], data_brt="2026-08-01",
                                    agora_ms=1785584100000)
        assert mot["outro_dia"] == 1 and not el, "jogo de outro dia BRT nao filtrado"
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

    # 3g) regressao no log de conectores (v22). Bug real: registrar varias
    # observacoes do dia de uma vez carimbava todas com a hora ATUAL, fazendo
    # o log dizer que 21h tinha disponibilidade quando a unica janela foi
    # ~09h40. Log com hora errada e pior que log nenhum - orientaria a trigger
    # para o horario errado.
    try:
        import importlib
        cl = importlib.import_module("connector_log")
        assert hasattr(cl, "registrar"), "connector_log sem registrar()"
        import inspect
        params = inspect.signature(cl.registrar).parameters
        assert "quando" in params, (
            "registrar() perdeu o parametro 'quando' - observacao retroativa "
            "voltaria a ser carimbada com a hora atual")
        dados = cl.por_hora()
        # se ha dados, as horas precisam ser plausiveis
        for h in dados:
            assert 0 <= h <= 23, f"hora invalida no log: {h}"

        # v26: 'contexto' e obrigatorio. Sem ele o log nao separa as duas
        # populacoes (sessao agendada x turno interativo) e volta a sugerir
        # que o problema e a HORA - o erro de diagnostico que custou uma
        # semana. registrar() sem contexto valido tem que levantar erro.
        assert "contexto" in inspect.signature(cl.registrar).parameters, (
            "registrar() perdeu o parametro 'contexto' - o log voltaria a "
            "misturar sessao agendada com turno interativo")
        for ruim in (None, "", "qualquer"):
            try:
                cl.registrar("fora", "fora", "fora", contexto=ruim)
            except ValueError:
                pass
            else:
                raise AssertionError(
                    f"registrar() aceitou contexto={ruim!r} - deveria recusar")
        assert hasattr(cl, "por_contexto"), "connector_log sem por_contexto()"
        for ctx in cl.por_contexto():
            assert ctx in cl.CONTEXTOS, (
                f"contexto '{ctx}' nao reconhecido em data/connector_log.csv - "
                "linha registrada sem marcacao")
    except AssertionError as e:
        err(f"connector_log: REGRESSAO DETECTADA - {e}")
    except Exception as e:
        err(f"connector_log: falha ao carregar/testar - {e}")

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

    # 3h) suite adversarial da extracao (v26). Roda em TODA execucao: e o
    # unico teste da extracao que nao depende de conector no ar, entao e a
    # unica verificacao disponivel numa sessao agendada (decisao 39).
    # Silenciosa quando passa; so fala se algo quebrou.
    try:
        import subprocess
        r = subprocess.run(
            [sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                          "test_extraction.py")],
            capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            ruins = [l.strip() for l in r.stdout.splitlines()
                     if l.strip().startswith(("FALHA", "- ", "ERRO"))]
            err("test_extraction: SUITE ADVERSARIAL FALHOU - "
                + "; ".join(ruins[:6] or ["ver saida completa"]))
    except Exception as e:
        err(f"test_extraction: nao foi possivel rodar a suite - {e}")

    # 3i) regressao nos mercados de contagem + line-shopping (v32). Fase 1-4
    # do plano de evolucao analitica: escanteios/cartoes/chutes e infra de
    # cruzamento de casas. Cartoes e chutes foram REJEITADOS no backtest
    # real (ver scripts/backtest_cartoes.py / backtest_chutes.py) - so
    # escanteios (ACEITO COM RESSALVA) e as funcoes de infraestrutura sao
    # testadas aqui como regressao de codigo, nao como prova de calibracao
    # (isso e feito pelos scripts de backtest, que exigem o dataset baixado
    # e nao rodam em toda execucao).
    try:
        from betting_model import poisson_total, negbin_total, poisson_grid, over_under_time, ewma_shrinkage
        pt = poisson_total(9.8, linhas=(8.5, 9.5, 10.5))
        assert abs(pt["over_9.5"] + pt["under_9.5"] - 1.0) < 1e-9, "poisson_total: over+under nao soma 1"
        assert pt["over_8.5"] > pt["over_9.5"] > pt["over_10.5"], "poisson_total: over deveria cair com a linha"
        assert sum(pt["distribuicao"].values()) > 0.999, "poisson_total: max_n=30 nao cobre massa suficiente em lambda=9.8"
        nb = negbin_total(9.8, forma=8.0, linhas=(9.5,))
        assert abs(nb["over_9.5"] + nb["under_9.5"] - 1.0) < 1e-9, "negbin_total: over+under nao soma 1"
        assert negbin_total(9.8, forma=None, linhas=(9.5,))["over_9.5"] == pt["over_9.5"], \
            "negbin_total(forma=None) deveria bater exatamente com poisson_total"
        pg = poisson_grid(5.2, 4.6)
        assert sum(pg["grid"].values()) > 0.999, "poisson_grid: max_n=15 nao cobre massa suficiente"
        assert 0 < over_under_time(pg, "a", 5.5) < 1, "over_under_time fora de [0,1]"
        assert ewma_shrinkage([], media_liga=9.5) == 9.5, "ewma_shrinkage sem historico deveria devolver a media da liga"
        lam = ewma_shrinkage([6, 8, 5], media_liga=9.5, alpha=3.0)
        assert 6.0 < lam < 9.5, "ewma_shrinkage com historico abaixo da liga deveria ficar entre os dois"
    except AssertionError as e:
        err(f"mercados de contagem: REGRESSAO DETECTADA - {e}")
    except Exception as e:
        err(f"mercados de contagem: falha ao carregar/testar - {e}")

    try:
        from pe_engine import candidato_escanteios, domina_1x2
        cands = candidato_escanteios([10, 8, 11, 9], [7, 6, 8, 5], media_liga=9.5)
        assert all(0 <= c["prob_pior_cenario"] <= 1 for c in cands), \
            "candidato_escanteios: probabilidade fora de [0,1]"
        assert all(c["faixa"] in ("Alta", "Moderada") for c in cands), \
            "candidato_escanteios: faixa fora do vocabulario esperado"
        dominado, melhor = domina_1x2(
            [{"mercado": "X", "prob_pior_cenario": 0.90}], prob_1x2=0.60)
        assert dominado and melhor["mercado"] == "X", \
            "domina_1x2: candidato claramente melhor deveria dominar"
        dominado2, _ = domina_1x2(
            [{"mercado": "X", "prob_pior_cenario": 0.61}], prob_1x2=0.60)
        assert not dominado2, "domina_1x2: diferenca dentro da margem nao deveria dominar"
    except AssertionError as e:
        err(f"pe_engine (gate 1x2/escanteios): REGRESSAO DETECTADA - {e}")
    except Exception as e:
        err(f"pe_engine (gate 1x2/escanteios): falha ao carregar/testar - {e}")

    try:
        from casa_matcher import normaliza_time, cruza_fixtures, melhor_preco, casa_do_edge
        assert normaliza_time("Celtic FC") == normaliza_time("Celtic"), \
            "normaliza_time deveria remover sufixo generico de clube (FC)"
        ev_a = {"participants": "Celtic FC - Dundee", "start_time": "1785000000000", "odds": [1.22, 7.40, 14.00]}
        ev_b = {"participants": "Celtic - Dundee FC", "start_time": "1785000300000", "odds": [1.20, 7.00, 15.00]}
        fixtures = cruza_fixtures({"Betano": [ev_a], "Bet365": [ev_b]})
        assert len(fixtures) == 1, "cruza_fixtures deveria juntar o mesmo confronto de duas casas em 1 fixture"
        assert set(fixtures[0]["por_casa"]) == {"Betano", "Bet365"}, "cruza_fixtures perdeu uma das casas"
        casa, odd = melhor_preco(fixtures[0], 2)
        assert (casa, odd) == ("Bet365", 15.0), f"melhor_preco: esperado (Bet365, 15.0), veio ({casa}, {odd})"
        assert casa_do_edge(fixtures[0]) in ("Betano", "Bet365"), "casa_do_edge nao achou casa com 1X2 completo"
    except AssertionError as e:
        err(f"casa_matcher: REGRESSAO DETECTADA - {e}")
    except Exception as e:
        err(f"casa_matcher: falha ao carregar/testar - {e}")

    try:
        from odds_sources import plano_multi_casa
        plano = plano_multi_casa(3)
        assert len(plano) <= 3, "plano_multi_casa devolveu mais entradas que o pedido"
        casas_no_plano = [p["casa"] for p in plano]
        assert len(casas_no_plano) == len(set(casas_no_plano)), \
            "plano_multi_casa: mesma casa apareceu 2x (deveria ser 1 entrada por casa)"
    except AssertionError as e:
        err(f"odds_sources (multi-casa): REGRESSAO DETECTADA - {e}")
    except Exception as e:
        err(f"odds_sources (multi-casa): falha ao carregar/testar - {e}")

    # 3j) regressao no motor de frequencia empirica + combinadas (v33).
    # Formaliza o metodo manual do usuario (ultimos N jogos, contagem de
    # limiar, Wilson como numero conservador) e as funcoes de combinada
    # (validadas empiricamente contra o dataset de backtest - ver
    # betting_model.prob_combinada).
    try:
        from betting_model import prob_combinada, odd_combinada, ev_combinada
        pernas = [(0.75, "escanteios"), (0.83, "gols")]
        assert abs(odd_combinada([1.30, 1.20]) - 1.56) < 1e-9, "odd_combinada(1.30,1.20) deveria ser 1.56"
        assert abs(prob_combinada(pernas) - 0.6225) < 1e-9, "prob_combinada(pernas) deveria ser 0.6225"
        assert abs(ev_combinada(pernas, [1.30, 1.20])
                   - ev_unitario(prob_combinada(pernas), odd_combinada([1.30, 1.20]))) < 1e-9, \
            "ev_combinada deveria bater com ev_unitario sobre os valores ja combinados"
        try:
            prob_combinada([(0.5, "gols"), (1.5, "escanteios")])
            err("prob_combinada aceitou probabilidade fora de [0,1] (deveria rejeitar)")
        except ValueError:
            pass
        try:
            odd_combinada([1.5, 0.9])
            err("odd_combinada aceitou odd invalida <=1.0 (deveria rejeitar)")
        except ValueError:
            pass
        # achado de auditoria (08/08): pernas mecanicamente ligadas do mesmo
        # jogo (mesma categoria) tem que ser rejeitadas, nunca combinadas
        # como se fossem independentes - cenario real: 1X2 x BTTS do mesmo
        # jogo inflava a prob combinada em ate 31% (EV positivo fabricado).
        try:
            prob_combinada([(0.6, "gols"), (0.55, "gols")])
            err("prob_combinada aceitou duas pernas da MESMA categoria (deveria rejeitar - regra 10)")
        except ValueError:
            pass
    except AssertionError as e:
        err(f"combinadas: REGRESSAO DETECTADA - {e}")
    except Exception as e:
        err(f"combinadas: falha ao carregar/testar - {e}")

    try:
        from forma_recente import (taxa_empirica, taxa_confronto_direto, avaliar_selecao,
                                   avaliar_confronto, AMOSTRA_MIN, AMOSTRA_ALVO)
        ultimos_10 = [10, 9, 10, 11, 9, 8, 9, 7, 10, 9]
        r = taxa_empirica(ultimos_10, limiar=8)
        assert r["k"] == 8 and r["n"] == 10, f"contagem errada: k={r['k']} n={r['n']} (esperado 8/10)"
        assert abs(r["taxa"] - 0.8) < 1e-9, "taxa bruta deveria ser 80%"
        assert r["wilson_lo"] < r["taxa"] < r["wilson_hi"], "wilson_lo/hi deveriam cercar a taxa bruta"
        r_com_none = taxa_empirica([10, None, 9, None, 11], limiar=8)
        assert r_com_none["n"] == 3, "taxa_empirica deveria ignorar valores None, nao contar como amostra"
        r_vazio = taxa_empirica([], limiar=8)
        assert r_vazio["n"] == 0 and r_vazio["taxa"] == 0.0, "amostra vazia deveria dar n=0 sem levantar excecao"
        assert taxa_confronto_direto([1, 2], limiar=1)["n"] == 2, "taxa_confronto_direto deveria reusar taxa_empirica"
        av = avaliar_selecao(r, odd_oferecida=1.65)
        assert av["prob_conservadora"] == r["wilson_lo"], \
            "avaliar_selecao deveria usar o limite inferior de Wilson, nao a taxa bruta"
        assert abs(av["ev"] - ev_unitario(r["wilson_lo"], 1.65)) < 1e-9, "EV de avaliar_selecao inconsistente"

        # v34: janela flexivel (3-10, nao fixa em 10)
        assert AMOSTRA_MIN == 3, "AMOSTRA_MIN deveria ser 3 (v34, pedido do usuario)"
        av_abaixo_min = avaliar_selecao(taxa_empirica([10, 9], limiar=8), odd_oferecida=1.65)
        assert "insuficiente" in av_abaixo_min["veredito"], \
            f"N<{AMOSTRA_MIN} deveria virar veredito de amostra insuficiente"
        av_amostra_parcial = avaliar_selecao(taxa_empirica([10, 9, 11], limiar=8), odd_oferecida=1.65)
        assert "insuficiente" not in av_amostra_parcial["veredito"], \
            f"N={AMOSTRA_MIN} (piso) NAO deveria ser tratado como insuficiente - janela flexivel"
        av_6 = avaliar_selecao(taxa_empirica([10, 9, 11, 8, 12, 9], limiar=8), odd_oferecida=1.65)
        assert str(AMOSTRA_ALVO) in av_6["veredito"], \
            "amostra abaixo do alvo deveria sinalizar isso no veredito, sem rejeitar so por causa disso"

        # v34: confronto com dado assimetrico - so o time dominante disponivel
        taxa_grande = taxa_empirica([11, 10, 12, 9, 13, 10, 11, 9], limiar=8)
        av_dominante = avaliar_confronto(taxa_grande, None, odd_oferecida=1.65, a_e_dominante=True)
        assert "insuficiente" not in av_dominante["veredito"], \
            "time dominante sozinho (marcado explicitamente) deveria bastar para avaliar"
        av_sem_marcar = avaliar_confronto(taxa_grande, None, odd_oferecida=1.65)
        assert "insuficiente" in av_sem_marcar["veredito"], \
            "sem marcar dominancia, 1 time sozinho NAO deveria bastar"
        av_nenhum = avaliar_confronto(None, None, odd_oferecida=1.65)
        assert "insuficiente" in av_nenhum["veredito"], "sem dado de nenhum time deveria ser insuficiente"
        taxa_b = taxa_empirica([9, 8, 10, 9], limiar=8)
        av_dois = avaliar_confronto(taxa_grande, taxa_b, odd_oferecida=1.65)
        assert av_dois["prob_conservadora"] == min(taxa_grande["wilson_lo"], taxa_b["wilson_lo"]), \
            "com os dois times disponiveis, deveria usar o mais conservador dos dois"
    except AssertionError as e:
        err(f"forma_recente: REGRESSAO DETECTADA - {e}")
    except Exception as e:
        err(f"forma_recente: falha ao carregar/testar - {e}")

    # 3k) agent_reach_fallback (v35) - checagem BEST-EFFORT, NUNCA bloqueante.
    # A Routine agendada pode rodar num ambiente sem Agent Reach instalado -
    # o sistema tem que continuar funcionando sem ele (mesmo principio dos
    # conectores MCP em sessao agendada). So testa a logica PURA (sem rede);
    # disponivel()==False e um resultado normal, nao um erro.
    try:
        from agent_reach_fallback import disponivel, _e_erro_autenticacao_jina
        assert isinstance(disponivel(), bool), "disponivel() deveria devolver bool sempre"
        assert _e_erro_autenticacao_jina('{"data":null,"code":401,"name":"AuthenticationRequiredError"}'), \
            "deveria reconhecer o erro de autenticacao do Jina anonimo"
        assert not _e_erro_autenticacao_jina("Title: pagina normal\n\nConteudo real aqui"), \
            "nao deveria marcar conteudo normal como erro de autenticacao"
    except AssertionError as e:
        err(f"agent_reach_fallback: REGRESSAO DETECTADA - {e}")
    except ImportError:
        pass  # modulo/venv nao presente neste ambiente - esperado em sessao agendada, nao e erro
    except Exception as e:
        err(f"agent_reach_fallback: falha ao testar - {e}")

    # 3l) scan_odds multi-mercado (v36). Causa raiz encontrada: o parser so
    # extraia "Resultado Final" (1X2) e IGNORAVA outros 5 mercados que ja
    # estavam no MESMO dump (Total de Gols/1oT/Chance Dupla/DNB/BTTS), alem
    # de nunca ter tentado a pagina individual do evento onde Escanteios e
    # Total de Cartoes tambem tem odds reais. Regressao roda com dado
    # SINTETICO (rapido, sem depender de fixture externo) + confirma contra
    # os dumps REAIS ja commitados quando presentes (best-effort, nao
    # bloqueante - o fixture pode nao existir num clone raso/CI).
    try:
        from scan_odds import (parse_market_blocks, parse_todos_mercados,
                                parse_mercados_evento, parse_todos_mercados_evento,
                                MERCADOS, MERCADOS_EVENTO)

        sint_listagem = (
            '{"data":{"event":{"leagueName":"Liga Teste","name":"Time A - Time B","startTime":1785364200000,'
            '"markets":['
            '{"id":"1","name":"Resultado Final","type":"MRES","selections":['
            '{"id":"1","name":"1","price":2.0},{"id":"2","name":"X","price":3.4},{"id":"3","name":"2","price":4.0}]},'
            '{"id":"2","name":"Total de Gols","type":"HCTG","handicap":2.5,"selections":['
            '{"id":"4","name":"Mais de 2.5","price":1.9},{"id":"5","name":"Menos de 2.5","price":1.9}]},'
            '{"id":"3","name":"Ambas equipes Marcam","type":"BTSC","selections":['
            '{"id":"6","name":"Sim","price":1.8},{"id":"7","name":"Não","price":1.95}]}'
            ']}}}'
        )
        gols = parse_market_blocks(sint_listagem, MERCADOS["total_gols"])
        assert len(gols) == 1, f"total_gols sintetico deveria achar 1 bloco, achou {len(gols)}"
        assert gols[0]["odds"] == [1.9, 1.9], f"odds de total_gols erradas: {gols[0]['odds']}"
        todos_sint = parse_todos_mercados(sint_listagem)
        assert len(todos_sint["1x2"]) == 1 and len(todos_sint["total_gols"]) == 1 and len(todos_sint["btts"]) == 1, \
            "parse_todos_mercados nao achou os 3 mercados sinteticos presentes"
        assert todos_sint["dupla_chance"] == [] and todos_sint["dnb"] == [], \
            "parse_todos_mercados nao deveria inventar mercado ausente"

        sint_evento = (
            '{"data":{"event":{"leagueName":"Liga Teste","name":"Time A - Time B","startTime":1785364200000}},'
            '"markets":[{"id":"9","name":"Escanteios","type":"CNOU","selections":['
            '{"id":"10","name":"Mais de 8.5","price":1.65},{"id":"11","name":"Menos de 8.5","price":2.15},'
            '{"id":"12","name":"Mais de 9.5","price":2.07},{"id":"13","name":"Menos de 9.5","price":1.7}]}]}'
        )
        esc = parse_mercados_evento(sint_evento, MERCADOS_EVENTO["escanteios"])
        assert esc is not None, "parse_mercados_evento nao achou escanteios sinteticos"
        assert [l["handicap"] for l in esc["linhas"]] == [8.5, 9.5], f"linhas de escanteios erradas: {esc['linhas']}"
        assert esc["linhas"][0]["odd_mais"] == 1.65 and esc["linhas"][0]["odd_menos"] == 2.15, \
            f"odds da linha 8.5 erradas: {esc['linhas'][0]}"
        cart = parse_mercados_evento(sint_evento, MERCADOS_EVENTO["cartoes"])
        assert cart is None, "parse_mercados_evento nao deveria inventar mercado ausente (cartoes)"

        # contra dado REAL ja commitado (best-effort - fixture pode faltar
        # num clone raso; nao e erro bloqueante se faltar, so pula). `os` ja
        # importado no topo do modulo - reimportar aqui localmente causaria
        # UnboundLocalError (Python trata 'os' como local na funcao inteira).
        import json
        dump_listagem = os.path.join("data", "dumps", "2026-08-04-betano.json")
        if os.path.exists(dump_listagem):
            with open(dump_listagem, encoding="utf-8") as f:
                real = json.load(f)["content"]
            todos_real = parse_todos_mercados(real, casa="Betano")
            assert len(todos_real["1x2"]) == 182, f"1x2 real esperado 182, achou {len(todos_real['1x2'])}"
            for chave, n_esperado in (("total_gols", 191), ("total_gols_1t", 191),
                                       ("dupla_chance", 187), ("dnb", 186), ("btts", 61)):
                n = len(todos_real[chave])
                assert n == n_esperado, f"{chave} real esperado {n_esperado}, achou {n}"

        dump_evento = os.path.join("data", "dumps", "eventos", "2026-08-04-betano-boca-estudiantes.json")
        if os.path.exists(dump_evento):
            with open(dump_evento, encoding="utf-8") as f:
                real_ev = json.load(f)["content"]
            mercados_ev = parse_todos_mercados_evento(real_ev, casa="Betano")
            assert mercados_ev["escanteios"] is not None and len(mercados_ev["escanteios"]["linhas"]) == 13, \
                "escanteios reais (Boca x Estudiantes) deveriam ter 13 linhas"
            assert mercados_ev["cartoes"] is not None and len(mercados_ev["cartoes"]["linhas"]) == 1, \
                "cartoes reais (Boca x Estudiantes) deveriam ter 1 linha"

        # parse_mres_blocks (compatibilidade, pe_engine.py depende dele) segue
        # identico ao comportamento anterior
        from scan_odds import parse_mres_blocks
        evs = parse_mres_blocks(sint_listagem)
        assert len(evs) == 1 and evs[0]["odds"] == [2.0, 3.4, 4.0], \
            "parse_mres_blocks (compatibilidade) quebrou apos generalizacao do parser"

        # achado de auditoria (08/08): escreve_csv_jogos nunca tinha teste
        # de regressao proprio - validado manualmente contra producao mas
        # nao travado em codigo. Roda ponta-a-ponta contra dado sintetico.
        from scan_odds import escreve_csv_jogos
        import tempfile
        eventos_1x2 = parse_market_blocks(sint_listagem, MERCADOS["1x2"])
        todos_sint2 = parse_todos_mercados(sint_listagem)
        indices_outros = {chave: {(ev.get("participants"), ev.get("start_time")): ev for ev in lista}
                           for chave, lista in todos_sint2.items() if chave != "1x2"}
        with tempfile.TemporaryDirectory() as tmpdir:
            caminho_csv = os.path.join(tmpdir, "teste.csv")
            n = escreve_csv_jogos(caminho_csv, eventos_1x2, indices_outros)
            assert n == 1, f"escreve_csv_jogos deveria gravar 1 linha, gravou {n}"
            with open(caminho_csv, encoding="utf-8") as f:
                linhas_csv = list(csv.DictReader(f))
            assert len(linhas_csv) == 1, "CSV deveria ter 1 linha de dado"
            row = linhas_csv[0]
            assert row["confronto"] == "Time A - Time B", f"confronto errado no CSV: {row['confronto']}"
            assert row["odd_1"] == "2.0" and row["odd_x"] == "3.4" and row["odd_2"] == "4.0", \
                f"odds 1X2 erradas no CSV: {row['odd_1']}/{row['odd_x']}/{row['odd_2']}"
            assert row["odd_total_gols_0"] == "1.9", f"odd total_gols errada no CSV: {row['odd_total_gols_0']}"
            assert row["linha_total_gols"] == "2.5", f"linha total_gols errada no CSV: {row['linha_total_gols']}"
            assert row["justo_1"] != "", "justo_1 deveria estar preenchido (de-vig aplicado)"
            # reescrever de novo tem que substituir, nao acumular (escrita
            # atomica via tempfile+os.replace, achado de auditoria 08/08)
            n2 = escreve_csv_jogos(caminho_csv, eventos_1x2, indices_outros)
            with open(caminho_csv, encoding="utf-8") as f:
                assert len(list(csv.DictReader(f))) == 1, "segunda escrita deveria substituir, nao acumular"

        # achado de auditoria (08/08): find_all/_achar_ocorrencias_mercado
        # quebrava silenciosamente se a fonte escapasse unicode (\uXXXX) -
        # testa o mercado "Total de gols - 1° Tempo" (tem "°") serializado
        # com ensure_ascii=True, como json.dumps produz por padrao.
        nome_1t = MERCADOS["total_gols_1t"]
        sint_unicode = (
            '{"data":{"event":{"leagueName":"Liga Teste","name":"Time A - Time B","startTime":1785364200000,'
            f'"markets":[{{"id":"1","name":{json.dumps(nome_1t)},"type":"OUH1","handicap":1.5,"selections":['
            '{"id":"1","name":"Mais de 1.5","price":2.1},{"id":"2","name":"Menos de 1.5","price":1.75}]}]}}}}'
        )
        gols_1t = parse_market_blocks(sint_unicode, nome_1t)
        assert len(gols_1t) == 1, ("parse_market_blocks nao achou o mercado com unicode escapado "
                                    f"('{nome_1t}') - fallback de find_all quebrado")
        assert gols_1t[0]["odds"] == [2.1, 1.75], f"odds do mercado unicode erradas: {gols_1t[0]['odds']}"

        # achado de auditoria (08/08): colisao de mercado duplicado no mesmo
        # evento tinha que avisar (stderr), nunca descartar em silencio.
        from scan_odds import _indexar_sem_colisao
        eventos_colisao = [
            {"participants": "A - B", "start_time": "100", "odds": [1.5, 2.5]},
            {"participants": "A - B", "start_time": "100", "odds": [1.6, 2.4]},  # mesma chave, colide
        ]
        idx_colisao = _indexar_sem_colisao(eventos_colisao, "teste")
        assert len(idx_colisao) == 1, "colisao deveria manter so 1 entrada (a ultima), nao duplicar"
        assert list(idx_colisao.values())[0]["odds"] == [1.6, 2.4], "colisao deveria manter a ULTIMA entrada"

        # achado de auditoria (08/08): dump truncado tinha que ser detectado
        from scan_odds import dump_parece_truncado
        assert not dump_parece_truncado(sint_listagem), "dump sintetico completo nao deveria parecer truncado"
        assert dump_parece_truncado(sint_listagem[:len(sint_listagem) // 2]), \
            "dump cortado no meio deveria ser detectado como truncado"
    except AssertionError as e:
        err(f"scan_odds multi-mercado: REGRESSAO DETECTADA - {e}")
    except Exception as e:
        err(f"scan_odds multi-mercado: falha ao testar - {e}")

    # 3m) ledger_stats.py (achado de auditoria, 08/08): o script que gera
    # TODOS os numeros oficiais do relatorio/PDF nunca tinha nenhuma
    # regressao - uma quebra silenciosa nele passaria por validate_system.py
    # com exit 0. Smoke-test: roda de verdade contra o ledger REAL (nao tem
    # como fixar valores esperados, o ledger muda todo dia) e confere
    # invariantes estruturais + recomputa "N resolvido" de forma
    # independente pra conferir que o numero impresso bate com uma
    # contagem feita aqui, sem depender do proprio ledger_stats.py.
    try:
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "ledger_stats.py")],
                            capture_output=True, text=True, cwd=ROOT, timeout=30)
        assert r.returncode == 0, f"ledger_stats.py saiu com codigo {r.returncode}: {r.stderr[:500]}"
        saida = r.stdout
        for cabecalho in ("=== APOSTAS DE VALOR", "=== COBERTURA POR FAMILIA DE MERCADO",
                          "=== PALPITES ESTATISTICOS", "Calibracao por FAMILIA DE MERCADO"):
            assert cabecalho in saida, f"ledger_stats.py nao imprimiu a secao esperada: '{cabecalho}'"

        with open(os.path.join(ROOT, "data/apostas_ledger.csv"), newline="", encoding="utf-8") as f:
            linhas_ledger = list(csv.DictReader(f))
        n_esperado_min = sum(1 for r2 in linhas_ledger
                             if r2.get("acerto_erro") in ("acerto", "erro"))
        m = re.search(r"N resolvido:\s*(\d+)", saida)
        assert m, "ledger_stats.py nao imprimiu 'N resolvido: <numero>'"
        n_impresso = int(m.group(1))
        assert n_impresso >= n_esperado_min, (
            f"N resolvido impresso ({n_impresso}) menor que a contagem minima independente "
            f"de acerto/erro no CSV ({n_esperado_min}) - numero pode estar errado")
    except AssertionError as e:
        err(f"ledger_stats: REGRESSAO DETECTADA - {e}")
    except Exception as e:
        err(f"ledger_stats: falha ao testar - {e}")

    # relatorio
    # O banner de rota (v17-d) foi REMOVIDO em 02/08: era uma muleta para o
    # periodo em que o servidor Claude_Code_Remote estava fora e as triggers
    # ainda carregavam o prompt v13 embutido. Em 02/08 o servidor voltou e os
    # stubs foram aplicados nas duas triggers - elas agora fazem git pull e
    # leem docs/DAILY_METHODOLOGY.md por conta propria. Manter o banner seria
    # duplicar a instrucao em dois lugares que podem divergir.
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
