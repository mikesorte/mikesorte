#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gerador do relatorio diario (HTML -> PDF). Substitui o "html_to_pdf.js
no scratchpad" que a metodologia citava mas nunca existiu no repo - cada
execucao reinventava o HTML a mao, o que e por isso a regra do
quadro-resumo (decisao 16, v6) se perdia na pratica.

Fontes de dado (nenhuma inventada aqui - so leitura e formatacao):
  data/dumps/YYYY-MM-DD-jogos.csv   -> quadro-resumo (todos os jogos do dia)
  data/apostas_ledger.csv           -> Apostas de Valor testadas/emitidas
  data/pe_ledger.csv                -> Palpites Estatisticos emitidos
  scripts/ledger_stats.py (stdout)  -> numeros oficiais

Uso:
    python3 scripts/generate_report.py --data 2026-08-03
    python3 scripts/generate_report.py --data 2026-08-03 --no-pdf   # so HTML, mais rapido p/ iterar
"""
import argparse
import csv
import glob
import html
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAKE_BRL_POR_UNIDADE = 20  # fase B1 - stake fixo, ver docs/DAILY_METHODOLOGY.md


def esc(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def read_csv(path):
    full = os.path.join(ROOT, path)
    if not os.path.exists(full):
        return []
    with open(full, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def casa_curta(casa):
    """'Betano (odds reais, mesma casa 3 lados)' -> 'Betano'."""
    if not casa:
        return "-"
    return re.split(r"\s*\(", casa.strip(), maxsplit=1)[0].strip()


def motivo_sem_selecao(selecao):
    """'NENHUMA (testado, sem edge)' -> 'sem edge'."""
    m = re.search(r"\((.*)\)\s*$", selecao or "")
    if not m:
        return "sem detalhe"
    texto = m.group(1)
    return texto.split(",", 1)[1].strip() if "," in texto else texto.strip()


def formatar_pick_valor(row):
    casa = casa_curta(row.get("casa", ""))
    odd = row.get("odd_entrada", "NA")
    stake_u = row.get("stake_unidades", "") or "0"
    try:
        stake_brl = f"R${float(stake_u) * STAKE_BRL_POR_UNIDADE:.0f}"
    except ValueError:
        stake_brl = "NA"
    return {
        "tipo": "Aposta de Valor",
        "linha": f"{row.get('mercado', '')} — {row.get('selecao', '')} no jogo "
                 f"{row.get('confronto', '')} (Casa: {casa}, odd: {odd})",
        "stake": f"Stake: {stake_brl} ({stake_u}u)",
        "extra": row.get("edge_declarado", ""),
    }


def formatar_pick_pe(row):
    casa = casa_curta(row.get("melhor_casa", ""))
    odd = row.get("odd_referencia", "NA")
    return {
        "tipo": f"Palpite Estatistico ({row.get('patamar', '')})",
        "linha": f"{row.get('mercado', '')} no jogo {row.get('confronto', '')} "
                 f"(Casa: {casa}, odd de referencia: {odd})",
        "stake": "PE NAO leva stake - nao e aposta de valor calculada",
        "extra": f"confianca {row.get('confianca', '')} | Wilson inf. {row.get('wilson_inferior', '')}",
    }


def montar_bloco_picks(apostas_hoje, pe_hoje):
    picks_valor = [formatar_pick_valor(r) for r in apostas_hoje
                   if not (r.get("selecao") or "").startswith("NENHUMA")]
    picks_pe = [formatar_pick_pe(r) for r in pe_hoje]
    picks = picks_valor + picks_pe

    if picks:
        itens = "\n".join(
            f"""<li class="pick">
                  <span class="pick-tag">{esc(p['tipo'])}</span>
                  <div class="pick-linha">{esc(p['linha'])}</div>
                  <div class="pick-meta">{esc(p['stake'])} &middot; {esc(p['extra'])}</div>
                </li>"""
            for p in picks
        )
        return f'<ol class="picks-list">{itens}</ol>'

    motivos = "\n".join(
        f"""<li class="no-pick-row">
              <span class="no-pick-jogo">{esc(r.get('confronto', ''))}</span>
              <span class="no-pick-motivo">{esc(motivo_sem_selecao(r.get('selecao', '')))}</span>
            </li>"""
        for r in apostas_hoje
    ) or '<li class="no-pick-row"><span class="no-pick-motivo">Nenhum jogo testado hoje.</span></li>'

    return f"""
    <div class="banner-sem-palpites">
      <div class="banner-titulo">SEM PALPITES HOJE</div>
      <p class="banner-sub">Nenhuma Aposta de Valor nem Palpite Estatistico passou nos
      criterios (ver detalhe completo de cada jogo abaixo). Motivo resumido por jogo testado:</p>
      <ul class="no-pick-list">{motivos}</ul>
    </div>"""


def _fmt_mercado_ou(j, prefixo, rotulo_over="Mais", rotulo_under="Menos"):
    """v36: formata um mercado over/under do CSV multi-mercado
    (scan_odds.escreve_csv_jogos) pra exibicao curta - "-" quando o
    mercado nao apareceu nesse jogo especifico (mercado ausente e normal,
    nem toda casa oferece todo mercado pra todo jogo)."""
    odd0 = (j.get(f"odd_{prefixo}_0") or "").strip()
    odd1 = (j.get(f"odd_{prefixo}_1") or "").strip()
    if not odd0 or not odd1:
        return "-"
    linha = (j.get(f"linha_{prefixo}") or "").strip()
    sufixo = f" {linha}" if linha else ""
    return f"{rotulo_over}{sufixo} @{odd0} / {rotulo_under}{sufixo} @{odd1}"


def montar_quadro_resumo(jogos):
    if not jogos:
        return "<p class=\"aviso\">Nenhum jogo do dia registrado em data/dumps/*-jogos.csv.</p>"
    linhas = "\n".join(
        f"""<tr>
              <td class="td-jogo">{esc(j['confronto'])}</td>
              <td>{esc(j['competicao'])}</td>
              <td class="td-num">{esc(j['horario_brt'])}</td>
              <td>{esc(casa_curta(j['casa']))}</td>
              <td class="td-num">{esc(j['odd_1'])}</td>
              <td class="td-num">{esc(j['odd_x'])}</td>
              <td class="td-num">{esc(j['odd_2'])}</td>
              <td class="td-num">{esc(_fmt_mercado_ou(j, 'total_gols'))}</td>
              <td class="td-num">{esc(_fmt_mercado_ou(j, 'btts', 'Sim', 'Não'))}</td>
              <td class="td-nota">{esc(j.get('nota', ''))}</td>
            </tr>"""
        for j in jogos
    )
    return f"""
    <table class="tabela-resumo">
      <thead><tr>
        <th>Confronto</th><th>Competição</th><th>Horário (BRT)</th>
        <th>Casa</th><th>1</th><th>X</th><th>2</th>
        <th>Total de Gols</th><th>Ambas Marcam</th><th>Nota</th>
      </tr></thead>
      <tbody>{linhas}</tbody>
    </table>"""


def montar_cards_jogos(jogos, apostas_hoje):
    por_confronto = {r["confronto"]: r for r in apostas_hoje}
    cards = []
    for j in jogos:
        row = por_confronto.get(j["confronto"])
        odds = f"{j['odd_1']} / {j['odd_x']} / {j['odd_2']}"
        if row:
            eh_palpite = not (row.get("selecao") or "").startswith("NENHUMA")
            status = "PALPITE" if eh_palpite else "sem selecao"
            status_cls = " chip-ok" if eh_palpite else ""
            chips = f"""
              <div class="chip"><span>Odds Betano (1/X/2)</span><b>{esc(odds)}</b></div>
              <div class="chip"><span>Justa (de-vig)</span><b>{esc(row.get('prob_justa_novig', 'NA'))}</b></div>
              <div class="chip"><span>Edge declarado</span><b>{esc(row.get('edge_declarado', 'NA'))}</b></div>
              <div class="chip{status_cls}"><span>Status</span><b>{esc(status)}</b></div>"""
            nota = f'<details class="nota-detalhe"><summary>Raciocínio completo (auditoria)</summary><p>{esc(row.get("nota_processo", ""))}</p></details>'
        else:
            chips = f"""
              <div class="chip"><span>Odds Betano (1/X/2)</span><b>{esc(odds)}</b></div>
              <div class="chip"><span>Status</span><b>não aprofundado</b></div>"""
            nota = f'<p class="nota-simples">{esc(j.get("nota", "") or "Fora do escopo de aprofundamento desta rodada.")}</p>'
        cards.append(f"""
        <div class="card-jogo">
          <h3>{esc(j['confronto'])}</h3>
          <p class="card-sub">{esc(j['competicao'])} &middot; {esc(j['horario_brt'])} BRT</p>
          <div class="chips">{chips}</div>
          {nota}
        </div>""")
    return "\n".join(cards)


def rodar_ledger_stats():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "ledger_stats.py")],
                        capture_output=True, text=True, cwd=ROOT)
    return r.stdout


def montar_html(data_str, jogos, apostas_hoje, pe_hoje, stats_txt):
    casas_hoje = sorted({casa_curta(j["casa"]) for j in jogos}) or ["-"]
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>Relatório Diário - Sistema de Apostas - {esc(data_str)}</title>
<style>
  :root {{
    --azul: #0f2942; --azul2: #163a5c; --verde: #0f9d58; --ambar: #b7791f;
    --cinza-bg: #f6f7f9; --borda: #dfe3e8; --texto: #1c1f24; --texto-suave: #5b6472;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: var(--texto); max-width: 850px; margin: 0 auto; padding: 0 0 40px 0;
    background: #fff; font-size: 13px;
  }}
  header.topo {{
    background: linear-gradient(135deg, var(--azul), var(--azul2));
    color: #fff; padding: 28px 32px 22px 32px; margin-bottom: 22px;
  }}
  header.topo h1 {{ margin: 0 0 4px 0; font-size: 21px; font-weight: 700; }}
  header.topo .sub {{ font-size: 12.5px; opacity: 0.85; }}
  .pills {{ margin-top: 12px; display: flex; gap: 8px; flex-wrap: wrap; }}
  .pill {{
    background: rgba(255,255,255,0.14); border: 1px solid rgba(255,255,255,0.25);
    border-radius: 20px; padding: 4px 12px; font-size: 11px;
  }}
  main {{ padding: 0 32px; }}
  h2.secao {{
    font-size: 14px; text-transform: uppercase; letter-spacing: 0.04em;
    color: var(--azul); border-bottom: 2px solid var(--azul); padding-bottom: 6px;
    margin: 30px 0 12px 0;
  }}
  table.tabela-resumo {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  table.tabela-resumo th {{
    background: var(--azul); color: #fff; text-align: left; padding: 8px 10px;
    font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.03em;
  }}
  table.tabela-resumo td {{ padding: 7px 10px; border-bottom: 1px solid var(--borda); }}
  table.tabela-resumo tbody tr:nth-child(even) {{ background: var(--cinza-bg); }}
  .td-jogo {{ font-weight: 600; }}
  .td-num {{ text-align: center; font-variant-numeric: tabular-nums; }}
  .td-nota {{ color: var(--ambar); font-size: 11px; }}

  .banner-sem-palpites {{
    background: #fdf6ec; border: 1.5px solid var(--ambar); border-radius: 8px; padding: 16px 20px;
  }}
  .banner-titulo {{ font-size: 16px; font-weight: 800; color: var(--ambar); letter-spacing: 0.03em; }}
  .banner-sub {{ margin: 6px 0 10px 0; color: var(--texto-suave); font-size: 12px; }}
  ul.no-pick-list {{ list-style: none; margin: 0; padding: 0; }}
  li.no-pick-row {{
    display: flex; justify-content: space-between; gap: 12px;
    padding: 6px 0; border-top: 1px dashed #e6d3b3; font-size: 12px;
  }}
  li.no-pick-row:first-child {{ border-top: none; }}
  .no-pick-jogo {{ font-weight: 600; }}
  .no-pick-motivo {{ color: var(--texto-suave); }}

  ol.picks-list {{ list-style: none; margin: 0; padding: 0; counter-reset: pick; }}
  li.pick {{
    counter-increment: pick; position: relative; background: #eefaf2;
    border: 1.5px solid var(--verde); border-radius: 8px; padding: 12px 16px 12px 42px;
    margin-bottom: 10px;
  }}
  li.pick::before {{
    content: counter(pick); position: absolute; left: 12px; top: 12px;
    width: 20px; height: 20px; border-radius: 50%; background: var(--verde); color: #fff;
    font-size: 11px; font-weight: 700; display: flex; align-items: center; justify-content: center;
  }}
  .pick-tag {{
    display: inline-block; background: var(--verde); color: #fff; font-size: 10px;
    font-weight: 700; text-transform: uppercase; letter-spacing: 0.03em;
    border-radius: 4px; padding: 2px 7px; margin-bottom: 5px;
  }}
  .pick-linha {{ font-size: 13.5px; font-weight: 600; }}
  .pick-meta {{ font-size: 11px; color: var(--texto-suave); margin-top: 3px; }}

  .card-jogo {{
    border: 1px solid var(--borda); border-radius: 8px; padding: 14px 18px;
    margin-bottom: 12px; background: #fff;
  }}
  .card-jogo h3 {{ margin: 0 0 2px 0; font-size: 13.5px; }}
  .card-sub {{ margin: 0 0 10px 0; color: var(--texto-suave); font-size: 11px; }}
  .chips {{ display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 4px; }}
  .chip {{
    background: var(--cinza-bg); border: 1px solid var(--borda); border-radius: 6px;
    padding: 5px 10px; font-size: 11px; min-width: 120px;
  }}
  .chip span {{ display: block; color: var(--texto-suave); font-size: 9.5px; text-transform: uppercase; }}
  .chip b {{ font-size: 12px; }}
  details.nota-detalhe {{ margin-top: 8px; font-size: 11px; color: var(--texto-suave); }}
  details.nota-detalhe summary {{ cursor: pointer; color: var(--azul2); font-weight: 600; }}
  .nota-simples {{ margin-top: 6px; font-size: 11px; color: var(--texto-suave); }}

  pre.stats {{
    background: #0f172a; color: #d6e4f0; font-family: "SF Mono", Menlo, monospace;
    font-size: 11.5px; padding: 16px 18px; border-radius: 8px; overflow-x: auto; white-space: pre-wrap;
  }}
  .chip.chip-ok {{ background: #eefaf2; border-color: var(--verde); }}
  .chip.chip-ok b {{ color: var(--verde); }}

  footer {{
    margin: 30px 32px 0 32px; padding-top: 14px; border-top: 1px solid var(--borda);
    font-size: 10.5px; color: var(--texto-suave);
  }}

  @page {{ margin: 14mm 12mm; }}
  @media print {{
    .card-jogo, li.pick, .banner-sem-palpites, tr {{ break-inside: avoid; page-break-inside: avoid; }}
    h2.secao {{ break-after: avoid; page-break-after: avoid; }}
  }}
</style>
</head>
<body>

<header class="topo">
  <h1>Sistema de Análise Quantitativa de Apostas Esportivas</h1>
  <div class="sub">Relatório diário &middot; {esc(data_str)}</div>
  <div class="pills">
    <span class="pill">Fase B1 &middot; validacão</span>
    <span class="pill">Bankroll R$10.000</span>
    <span class="pill">Stake fixo R${STAKE_BRL_POR_UNIDADE}/aposta</span>
    <span class="pill">Casa(s) consultada(s): {esc(", ".join(casas_hoje))}</span>
  </div>
</header>

<main>
  <h2 class="secao">Jogos de hoje</h2>
  {montar_quadro_resumo(jogos)}

  <h2 class="secao">Palpites do dia</h2>
  {montar_bloco_picks(apostas_hoje, pe_hoje)}

  <h2 class="secao">Detalhe por jogo</h2>
  {montar_cards_jogos(jogos, apostas_hoje)}

  <h2 class="secao">Números oficiais (ledger_stats.py)</h2>
  <pre class="stats">{esc(stats_txt.strip())}</pre>
</main>

<footer>
  Gerado automaticamente por scripts/generate_report.py a partir dos dados versionados em
  data/apostas_ledger.csv, data/pe_ledger.csv e data/dumps/. Não constitui garantia de
  resultado nem recomendação financeira. Palpites Estatísticos (PE) nunca levam stake.
  Aposte com responsabilidade.
</footer>

</body>
</html>
"""


def encontrar_chrome():
    env = os.environ.get("CHROME_BIN")
    if env and os.path.exists(env):
        return env
    for pattern in ("/opt/pw-browsers/chromium-*/chrome-linux/chrome",):
        found = sorted(glob.glob(pattern))
        if found:
            return found[-1]
    for nome in ("google-chrome", "chromium-browser", "chromium", "chrome"):
        p = shutil.which(nome)
        if p:
            return p
    return None


def gerar_pdf(html_path, pdf_path):
    chrome = encontrar_chrome()
    if not chrome:
        print("AVISO: nenhum binario Chromium encontrado - PDF nao gerado, so o HTML.", file=sys.stderr)
        return False
    cmd = [
        chrome, "--headless", "--disable-gpu", "--no-sandbox",
        f"--print-to-pdf={pdf_path}", "--no-pdf-header-footer",
        f"file://{html_path}",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="YYYY-MM-DD")
    ap.add_argument("--out-dir", default=None, help="diretorio de saida (default: scratchpad se definido, senao /tmp)")
    ap.add_argument("--no-pdf", action="store_true", help="gera so o HTML, pula a conversao para PDF")
    args = ap.parse_args()

    jogos = read_csv(f"data/dumps/{args.data}-jogos.csv")
    apostas = [r for r in read_csv("data/apostas_ledger.csv") if r.get("data") == args.data]
    pes = [r for r in read_csv("data/pe_ledger.csv") if r.get("data") == args.data]
    stats_txt = rodar_ledger_stats()

    out_dir = args.out_dir or os.environ.get("REPORT_OUT_DIR") or "/tmp"
    os.makedirs(out_dir, exist_ok=True)
    html_path = os.path.join(out_dir, f"relatorio_{args.data}.html")
    pdf_path = os.path.join(out_dir, f"Relatorio_Apostas_{args.data}.pdf")

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(montar_html(args.data, jogos, apostas, pes, stats_txt))
    print(f"HTML: {html_path}")

    if not args.no_pdf:
        ok = gerar_pdf(html_path, pdf_path)
        print(f"PDF: {pdf_path}" if ok else "PDF: FALHOU")


if __name__ == "__main__":
    main()
