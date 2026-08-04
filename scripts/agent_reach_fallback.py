#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fallback de ULTIMA INSTANCIA via Agent Reach (v35).

REGRA DE USO (pedido explicito do usuario): para qualquer site/busca que
ja funciona pelos metodos normais (Nimble/Tavily/Exa MCP/WebSearch), a
ferramenta comum continua sendo usada, SEMPRE. Este modulo so entra
quando um desses metodos falhar, for negado ou der erro de acesso - em
QUALQUER tarefa do fluxo diario (odds, forma recente de time, noticias,
H2H), nao so numa cascata especifica.

O QUE E AGENT REACH, DE VERDADE (nao o que o material de instalacao
resumia)
---------------------------------------------------------------------
Instalado a partir do codigo-fonte (github.com/Panniantong/agent-reach,
clonado e auditado manualmente - o pacote "agent-reach" no PyPI e de OUTRO
autor, nome coincidente, nunca usar `pip install agent-reach` por nome).
Escopo instalado: so a infraestrutura base (gh CLI, mcporter+Exa, leitura
de pagina via Jina Reader). NAO configurados: cookies de Twitter/Xueqiu/
Xiaohongshu nem API key da Groq - sem relacao com o pedido (odds/
estatisticas/analises de apostas), e extracao de cookie de navegador nao
funciona neste ambiente headless de qualquer forma.

Mecanismo real (sem CLI dedicado de "fetch" - o pacote so tem
setup/install/doctor; a leitura/busca em si e feita chamando os backends
direto, exatamente como agent_reach/channels/web.py faz):
  - leitura de pagina: `curl https://r.jina.ai/<url>` (Jina Reader)
  - busca: `mcporter call 'exa.web_search_exa(query: "...", numResults: N)'`

RESULTADO REAL DE TESTE (v35, nao suposicao) - ver decisao no doc:
  - le_pagina(): funciona para bloqueio LEVE de bot/anti-scraping
    (ex.: whoscored.com deu 403 direto, passou via Jina). NAO funciona
    pra geo-block DURO de casa de apostas (Sportingbet: o proprio Jina
    bate no mesmo bloqueio geografico) nem quando o proprio Jina anonimo
    esta com reputacao de IP ruim (football-data.co.uk deu erro do
    JINA, nao do alvo). Tratar como "vale tentar", nunca como garantia.
  - busca(): funciona bem - achou dado real de forma recente (ultimos 10
    jogos, escanteios por partida) pra um time de teste via Exa.

Uso:
    from agent_reach_fallback import disponivel, le_pagina, busca
"""
import shutil
import subprocess
import urllib.error
import urllib.request

_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def disponivel():
    """Best-effort: o binario 'mcporter' esta no PATH? (leitura de pagina
    via Jina nao depende de binario nenhum, so rede - sempre 'tentavel'.)
    Nunca usar isto pra bloquear o fluxo - a Routine agendada pode rodar
    num ambiente sem Agent Reach instalado, o sistema tem que continuar
    funcionando sem ele."""
    return shutil.which("mcporter") is not None


def _e_erro_autenticacao_jina(texto):
    """Separado em funcao pura pra dar pra testar sem rede (validate_system.py)."""
    return '"code":401' in texto[:200] or "AuthenticationRequiredError" in texto[:400]


def le_pagina(url, timeout=30):
    """Le uma URL via Jina Reader (o mesmo mecanismo que
    agent_reach.channels.web.WebChannel.read() usa). So chamar DEPOIS que
    o metodo normal (Nimble/Tavily/Exa MCP/WebSearch/WebFetch) falhar
    nessa URL especifica - nunca substituir o metodo que ja funciona.

    Retorna o texto/markdown extraido, ou levanta RuntimeError com o
    motivo (nunca falha silenciosa - quem chama decide o que fazer com a
    falha, ex. tentar a proxima fonte da cascata)."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    jina_url = f"https://r.jina.ai/{url}"
    req = urllib.request.Request(jina_url, headers={"User-Agent": _UA, "Accept": "text/plain"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            texto = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, OSError) as e:
        raise RuntimeError(f"agent_reach.le_pagina falhou (rede): {e}") from e
    if _e_erro_autenticacao_jina(texto):
        raise RuntimeError(
            "agent_reach.le_pagina: Jina Reader anonimo recusou (reputacao de IP "
            "compartilhado) - nao e bloqueio do alvo, e do proprio Jina sem auth")
    return texto


def busca(query, n=5, timeout=30):
    """Busca via Exa (configurado pelo Agent Reach via mcporter). So
    chamar DEPOIS que WebSearch/Tavily/Exa MCP falharem/estiverem
    indisponiveis - mesma regra de ultimo recurso.

    Retorna a saida bruta (texto) do mcporter - titulos/URLs/highlights.
    Levanta RuntimeError se mcporter nao estiver disponivel ou a chamada falhar.
    """
    if not disponivel():
        raise RuntimeError("agent_reach.busca: mcporter nao encontrado no PATH")
    query_escapada = query.replace('"', '\\"')
    cmd = ["mcporter", "call", f'exa.web_search_exa(query: "{query_escapada}", numResults: {n})']
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"agent_reach.busca: timeout apos {timeout}s") from e
    if r.returncode != 0:
        raise RuntimeError(f"agent_reach.busca falhou (codigo {r.returncode}): {r.stderr[:300]}")
    return r.stdout
