#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Motor quantitativo do sistema de analise de apostas (v12).

Substitui as estimativas qualitativas ("~55-58%") por calculo numerico real.
Uso pelas execucoes diarias:
    python3 scripts/betting_model.py demo          # auto-teste com dados reais de 26/07
    (ou importar as funcoes num bloco python3 << EOF durante a execucao)

Modelos implementados, todos com fonte na metodologia ja aprovada (itens 1, 4, 6.2, 9.1, 9.3, 14.1):
  - poisson_dixon_coles: probabilidades 1X2/totais/BTTS a partir de gols esperados
  - devig_power: probabilidade justa (metodo POWER) a partir das odds dos dois+ lados
  - wilson_ci: intervalo de Wilson 95% para proporcoes de amostra pequena
  - kelly_fraction: fracao de Kelly (para uso FUTURO pos-validacao; quarter-Kelly)
  - ev_unitario: valor esperado por unidade apostada
  - clv: closing line value
  - poisson_total / poisson_grid / ewma_shrinkage (v32): mercados de
    contagem (escanteios/cartoes/chutes) - ver scripts/backtest_escanteios.py
    para o veredito de calibracao real antes de usar em producao
"""
import math
import sys


# ---------------------------------------------------------------- goals model
def _pois(lmbda, k):
    return math.exp(-lmbda) * lmbda ** k / math.factorial(k)


def poisson_dixon_coles(lambda_home, lambda_away, rho=-0.11, max_goals=10):
    """Matriz de placares Poisson com correcao Dixon-Coles (tau) nos placares
    baixos (0-0, 1-0, 0-1, 1-1). rho tipico da literatura: ~-0.1.

    Retorna dict com p_home, p_draw, p_away, over/under 1.5/2.5/3.5, btts.
    """
    def tau(x, y):
        if x == 0 and y == 0:
            return 1 - lambda_home * lambda_away * rho
        if x == 0 and y == 1:
            return 1 + lambda_home * rho
        if x == 1 and y == 0:
            return 1 + lambda_away * rho
        if x == 1 and y == 1:
            return 1 - rho
        return 1.0

    grid = {}
    total = 0.0
    for h in range(max_goals + 1):
        for a in range(max_goals + 1):
            p = _pois(lambda_home, h) * _pois(lambda_away, a) * tau(h, a)
            grid[(h, a)] = p
            total += p
    # renormaliza (tau distorce levemente a soma)
    for k in grid:
        grid[k] /= total

    out = {"p_home": 0.0, "p_draw": 0.0, "p_away": 0.0, "btts": 0.0}
    overs = {1.5: 0.0, 2.5: 0.0, 3.5: 0.0}
    margins = {}  # margem de gols (h - a) -> probabilidade, uso em mata-mata (agregado)
    for (h, a), p in grid.items():
        if h > a:
            out["p_home"] += p
        elif h == a:
            out["p_draw"] += p
        else:
            out["p_away"] += p
        if h >= 1 and a >= 1:
            out["btts"] += p
        for line in overs:
            if h + a > line:
                overs[line] += p
        margins[h - a] = margins.get(h - a, 0.0) + p
    for line, p in overs.items():
        out[f"over_{line}"] = p
        out[f"under_{line}"] = 1 - p
    out["margins"] = margins
    return out


def _negbin(mu, k, forma):
    """P(K=k) numa binomial negativa com media 'mu' e parametro de forma
    'forma' (mistura Poisson-gama). forma -> infinito recupera Poisson.

    Variancia = mu + mu^2/forma, ou seja SEMPRE maior que a media.
    """
    p = forma / (forma + mu)
    # lgamma evita estouro em k grande
    log_p = (math.lgamma(k + forma) - math.lgamma(k + 1) - math.lgamma(forma)
             + forma * math.log(p) + k * math.log(1 - p))
    return math.exp(log_p)


def gols_dixon_coles(lambda_home, lambda_away, rho=-0.11, max_goals=10,
                     forma=None):
    """Igual a poisson_dixon_coles, mas com marginais SUPERDISPERSAS quando
    'forma' e finito.

    POR QUE (v28): o estudo de ma-especificacao mostrou que assumir Poisson
    puro produz vies SISTEMATICO e direcional nos mercados de gols - Over 2.5
    +17pp, BTTS +20pp, com os Under indo para o outro lado. Nao e ruido: gols
    de futebol tem variancia maior que a media, o que concentra mais massa no
    zero do que Poisson preve. Subestimar P(0 gols) infla exatamente "ambas
    marcam" e "over".

    'forma' baixo = mais superdisperso. A literatura de futebol sugere
    superdispersao leve; usamos a faixa como CENARIO de robustez, nao como
    valor unico chutado.
    """
    if forma is None:
        return poisson_dixon_coles(lambda_home, lambda_away, rho, max_goals)

    def tau(x, y):
        if x == 0 and y == 0:
            return 1 - lambda_home * lambda_away * rho
        if x == 0 and y == 1:
            return 1 + lambda_home * rho
        if x == 1 and y == 0:
            return 1 + lambda_away * rho
        if x == 1 and y == 1:
            return 1 - rho
        return 1.0

    grid, total = {}, 0.0
    for h in range(max_goals + 1):
        ph = _negbin(lambda_home, h, forma)
        for a in range(max_goals + 1):
            p = ph * _negbin(lambda_away, a, forma) * tau(h, a)
            grid[(h, a)] = p
            total += p
    for k in grid:
        grid[k] /= total

    out = {"p_home": 0.0, "p_draw": 0.0, "p_away": 0.0, "btts": 0.0}
    overs = {1.5: 0.0, 2.5: 0.0, 3.5: 0.0}
    margins = {}
    for (h, a), p in grid.items():
        if h > a:
            out["p_home"] += p
        elif h == a:
            out["p_draw"] += p
        else:
            out["p_away"] += p
        if h >= 1 and a >= 1:
            out["btts"] += p
        for line in overs:
            if h + a > line:
                overs[line] += p
        margins[h - a] = margins.get(h - a, 0.0) + p
    for line, p in overs.items():
        out[f"over_{line}"] = p
        out[f"under_{line}"] = 1 - p
    out["margins"] = margins
    return out


def win_by_margin(model_out, min_margin):
    """P(mandante vence por >= min_margin gols de diferenca), a partir do
    dict retornado por poisson_dixon_coles(). Uso tipico: mata-mata em que
    o mandante precisa reverter o placar agregado por N gols (ex.: Grêmio
    precisando vencer por 2+ apos derrota de 3-2 na ida)."""
    return sum(p for m, p in model_out["margins"].items() if m >= min_margin)


# --------------------------------------------------------- mercados de contagem
# (escanteios, cartoes, chutes - v32). Diferente de gols, NAO usam a correcao
# Dixon-Coles (tau): essa correcao existe pela sub-representacao de placares
# baixos ESPECIFICA de futebol (poucos gols, dependencia tatica em jogos
# apertados 0-0/1-0/0-1/1-1) - nao ha razao matematica pra portar pra
# contagens de media mais alta (escanteios ~5-6/lado, chutes ~12-13/lado).
#
# Duas funcoes, nao uma generica, porque o problema estatistico muda por
# tipo de mercado (ver docs/DAILY_METHODOLOGY.md v32, achado do backtest):
#
#   poisson_total(): mercados de TOTAL do jogo (over/under N.5). O total e
#   modelado como UMA Poisson so, com lambda_total estimado diretamente -
#   NUNCA como soma de duas marginais independentes. Motivo: escanteios/
#   cartoes dos dois lados sao correlacionados por estado de placar (time
#   perdendo pressiona mais) e abertura do jogo (jogo aberto gera evento
#   pros dois lados) - Var(H+A) != Var(H)+Var(A), somar duas Poisson
#   independentes SUBESTIMARIA a variancia real do total.
#
#   poisson_grid(): mercados POR TIME (over/under do time A isolado). A
#   covariancia entre os lados nao importa aqui (e a marginal de UM time
#   so), mas a variancia da propria marginal pode estar subestimada pelo
#   mesmo motivo (pressao tardia/estado de jogo) - LIMITACAO DECLARADA, nao
#   corrigida nesta versao por falta de dado que isole o efeito.
def poisson_total(lambda_total, linhas=(8.5, 9.5, 10.5), max_n=30):
    """Probabilidade de over/under para o TOTAL de um evento de contagem
    (escanteios, cartoes, chutes) no jogo inteiro, via Poisson simples.

    lambda_total: media esperada do TOTAL (casa+fora), estimada diretamente
    (ex.: ewma_shrinkage() sobre o total historico), nunca como soma de duas
    marginais independentes - ver nota do bloco acima.

    max_n default 30 (bem maior que o max_goals=10 do Dixon-Coles de
    proposito - escanteios/chutes passam de 10-15 fácil; truncar cedo
    distorce o over das linhas altas).

    Retorna dict {"over_8.5": p, "under_8.5": 1-p, ...} por linha, mais
    "media" e "distribuicao" (grid completo, para auditoria/self-teste de
    que max_n cobre massa suficiente).
    """
    if lambda_total <= 0:
        raise ValueError(f"lambda_total tem que ser positivo, recebido {lambda_total}")
    dist = {k: _pois(lambda_total, k) for k in range(max_n + 1)}
    out = {"media": lambda_total, "distribuicao": dist}
    for linha in linhas:
        piso = int(math.floor(linha))  # 8.5 -> acumula k<=8 no under
        under = sum(p for k, p in dist.items() if k <= piso)
        over = 1.0 - under  # inclui a cauda alem de max_n - nunca subestima o over
        out[f"under_{linha}"] = under
        out[f"over_{linha}"] = over
    return out


def negbin_total(lambda_total, forma, linhas=(8.5, 9.5, 10.5), max_n=30):
    """Igual a poisson_total, mas com a marginal SUPERDISPERSA (binomial
    negativa, mistura Poisson-gama) - mesmo mecanismo de _negbin() usado em
    gols_dixon_coles(). 'forma' baixo = mais superdisperso; None reduz a
    poisson_total() (mesma interface).

    NAO e a mesma decisao do v28 em gols (que foi REJEITADA por backtest
    real - ver docstring de gols_dixon_coles): aqui a superdispersao so
    entra em producao SE scripts/backtest_escanteios.py validar melhora
    real de calibracao contra dado real, testado do zero para este
    mercado - nunca por analogia com outro mercado.
    """
    if forma is None:
        return poisson_total(lambda_total, linhas, max_n)
    if lambda_total <= 0:
        raise ValueError(f"lambda_total tem que ser positivo, recebido {lambda_total}")
    dist = {k: _negbin(lambda_total, k, forma) for k in range(max_n + 1)}
    out = {"media": lambda_total, "distribuicao": dist}
    for linha in linhas:
        piso = int(math.floor(linha))
        under = sum(p for k, p in dist.items() if k <= piso)
        out[f"under_{linha}"] = under
        out[f"over_{linha}"] = 1.0 - under
    return out


def poisson_grid(lambda_a, lambda_b, max_n=15):
    """Grid conjunto Poisson INDEPENDENTE para um evento de contagem por
    time (ex.: escanteios do mandante vs escanteios do visitante).

    LIMITACAO DECLARADA: assume independencia entre os dois lados - ver nota
    do bloco acima sobre correlacao por estado de jogo. Aceita como limite
    conhecido, nao corrigida por falta de dado que isole o efeito.

    Retorna dict com "media_a", "media_b" e "grid" (dict (a,b)->p) - usar
    junto de over_under_time() para extrair over/under de um lado.
    """
    if lambda_a <= 0 or lambda_b <= 0:
        raise ValueError(f"lambdas tem que ser positivos, recebido ({lambda_a}, {lambda_b})")
    grid, total = {}, 0.0
    for a in range(max_n + 1):
        pa = _pois(lambda_a, a)
        for b in range(max_n + 1):
            p = pa * _pois(lambda_b, b)
            grid[(a, b)] = p
            total += p
    for k in grid:
        grid[k] /= total
    return {"media_a": lambda_a, "media_b": lambda_b, "grid": grid}


def over_under_time(grid_out, lado, linha):
    """P(over linha) para um dos dois lados de poisson_grid(). lado: 'a' ou 'b'."""
    if lado not in ("a", "b"):
        raise ValueError(f"lado tem que ser 'a' ou 'b', recebido {lado!r}")
    idx = 0 if lado == "a" else 1
    piso = int(math.floor(linha))
    under = sum(p for par, p in grid_out["grid"].items() if par[idx] <= piso)
    return 1.0 - under


def ewma_shrinkage(historico, media_liga, alpha=3.0, decay=0.9):
    """Estima um lambda (media esperada) para um time a partir do seu
    HISTORICO PRIOR (lista de valores realizados, cronologica, mais recente
    por ULTIMO) via EWMA, regredido a media da liga - shrinkage continuo,
    nao corte rigido por N de jogos.

    POR QUE EWMA + SHRINKAGE, NAO MEDIA SIMPLES OU CORTE FIXO (v32): forma
    recente pesa mais que forma antiga (regra 6.2 "EWMA na entrada" ja
    prescrevia isso, nunca implementado em codigo). Com poucos jogos por
    time (~17-19 antes do warm-up nas ligas com stats), um corte tipo "so
    avalia depois de N=5 jogos" descarta parte ja escassa do dado - o
    shrinkage continuo usa TODO historico disponivel, com peso maior na
    media da liga quando o time tem poucos jogos, decaindo conforme o time
    acumula historico proprio.

    VAZAMENTO (responsabilidade do CHAMADOR, nao desta funcao): 'historico'
    e 'media_liga' TEM que conter so jogos anteriores ao que esta sendo
    previsto (walk-forward) - esta funcao so agrega o que recebe, nao sabe
    nem pode saber se ha vazamento upstream.

    alpha: peso (em "jogos equivalentes") dado a media da liga na etapa de
    shrinkage. decay: fator de decaimento do EWMA por jogo mais antigo
    (0.9 = jogo de 5 partidas atras pesa 0.9^5 ~= 59% do jogo mais recente).
    """
    n = len(historico)
    if n == 0:
        return media_liga
    soma, peso_total, peso = 0.0, 0.0, 1.0
    for valor in reversed(historico):  # do mais recente pro mais antigo
        soma += peso * valor
        peso_total += peso
        peso *= decay
    ewma_time = soma / peso_total
    return (alpha * media_liga + n * ewma_time) / (alpha + n)


# ------------------------------------------------------------------- de-vig
def devig_power(odds, tol=1e-10, max_iter=200):
    """De-vig pelo metodo POWER: acha k tal que sum((1/odd)^k) = 1.
    Aceita 2+ lados. Retorna lista de probabilidades justas na mesma ordem.
    """
    imps = [1.0 / o for o in odds]
    s = sum(imps)
    if s <= 1.0:
        raise ValueError(
            f"soma das probabilidades implicitas = {s:.4f} <= 1 - odds sem margem "
            "sao dado de agregador invalido (regra v8), descartar")
    # overround => sum(imps) > 1 em k=1; f(k) e decrescente em k => raiz em k > 1
    def f(k):
        return sum(i ** k for i in imps) - 1.0
    lo_k, hi_k = 1.0, 2.0
    while f(hi_k) > 0:
        hi_k *= 2.0
        if hi_k > 64:
            raise ValueError("power de-vig nao convergiu - odds anomalas, descartar")
    for _ in range(max_iter):
        mid = (lo_k + hi_k) / 2
        v = f(mid)
        if abs(v) < tol:
            break
        # f e decrescente: f(mid)>0 => raiz a direita de mid
        if v > 0:
            lo_k = mid
        else:
            hi_k = mid
    k = (lo_k + hi_k) / 2
    return [i ** k for i in imps]


# -------------------------------------------------- inversao 1X2 -> lambdas
class InversaoFalhou(Exception):
    """A inversao nao convergiu ou produziu lambdas implausiveis. Chamador
    DEVE descartar o evento, nunca cair para um valor default."""


def implied_lambdas(p_home, p_draw, p_away, rho=-0.11,
                    tol=1e-9, max_iter=200):
    """INVERSA do Dixon-Coles: dadas as probabilidades JUSTAS de 1X2 (ja
    de-vigadas), acha (lambda_mandante, lambda_visitante) que as reproduzem.

    POR QUE ISTO EXISTE (v27)
    -------------------------
    Ate aqui o sistema so sabia ir de lambda -> probabilidade, e o lambda
    vinha de proxy chutado a partir de tabela/forma. Isso levou a competir
    com a casa no 1X2 usando informacao pior que a dela - erro documentado
    na decisao v17-b, repetido em 4 jogos seguidos.

    A inversao vira o problema do avesso: o 1X2 da casa e o MELHOR estimador
    publico disponivel do jogo (e o produto mais eficiente dela). Em vez de
    disputar esse numero, eu o ACEITO como entrada e extraio dele os lambdas
    implicitos. Com os lambdas, calculo qualquer mercado derivado (over/under,
    BTTS, dupla chance, placar) SEM precisar pesquisar nada sobre os times.

    Isso e o que permite avaliar centenas de jogos por dia em vez de 2: o
    insumo passa a ser a propria odd, que ja vem no catalogo.

    IMPORTANTE - o que isto NAO e: nao e uma fonte de edge sobre o 1X2. As
    probabilidades derivadas herdam exatamente a informacao da casa, mais o
    erro do modelo de gols. Servem para (a) enunciar probabilidade em PE e
    (b) comparar contra os mercados SECUNDARIOS da casa, que sao menos
    eficientes (regra 8). Nunca para reapostar no proprio 1X2 de origem.

    Levanta InversaoFalhou se nao convergir ou se os lambdas sairem fora de
    faixa plausivel de futebol - dado ruim tem que morrer aqui, nao virar
    palpite.
    """
    alvo = (p_home, p_draw, p_away)
    if any(p <= 0 for p in alvo):
        raise InversaoFalhou(f"probabilidade nao-positiva em {alvo}")
    if abs(sum(alvo) - 1.0) > 1e-6:
        raise InversaoFalhou(f"probabilidades nao somam 1: {sum(alvo):.6f}")

    # Parametrizacao: total = lh + la (ritmo do jogo), diff = lh - la (forca
    # relativa). Sao quase ortogonais em relacao a (p_draw) e (p_home-p_away),
    # o que faz a busca coordenada convergir rapido e de forma estavel.
    def probs(total, diff):
        lh = (total + diff) / 2.0
        la = (total - diff) / 2.0
        if lh <= 0.01 or la <= 0.01:
            raise InversaoFalhou(f"lambda nao-positivo (lh={lh:.3f}, la={la:.3f})")
        o = poisson_dixon_coles(lh, la, rho=rho)
        return o["p_home"], o["p_draw"], o["p_away"], lh, la

    def residuos(total, diff):
        ph, pd, pa, _, _ = probs(total, diff)
        return ((ph - pa) - (p_home - p_away), pd - p_draw)

    def clampa(total, diff):
        # Os dois parametros sao ACOPLADOS: lh=(total+diff)/2, la=(total-diff)/2,
        # entao |diff| tem que caber dentro de total ou um lambda fica negativo.
        # Clampar cada um isoladamente nao basta - foi o que quebrou o caso
        # (2.4, 0.7) na primeira versao.
        total = min(max(total, 0.30), 12.0)
        limite = total - 0.20            # garante ambos os lambdas >= 0.10
        return total, min(max(diff, -limite), limite)

    total, diff = 2.6, 0.0          # chute inicial: jogo medio, times iguais
    convergiu = False
    for _ in range(max_iter):
        r1, r2 = residuos(total, diff)
        if abs(r1) < tol and abs(r2) < tol:
            convergiu = True
            break
        # Jacobiano numerico COMPLETO. A primeira versao usava so as diagonais
        # (assumindo que 'diff' so mexe no favoritismo e 'total' so no empate);
        # a aproximacao vale perto do centro mas quebra em jogos muito
        # desequilibrados - (3.1, 0.5) e (0.8, 2.9) nao convergiam.
        h = 1e-5
        r1t, r2t = residuos(*clampa(total + h, diff))
        r1d, r2d = residuos(*clampa(total, diff + h))
        j11, j21 = (r1t - r1) / h, (r2t - r2) / h     # d/d total
        j12, j22 = (r1d - r1) / h, (r2d - r2) / h     # d/d diff
        det = j11 * j22 - j12 * j21
        if abs(det) < 1e-14:
            raise InversaoFalhou("jacobiano singular - sem solucao local")
        # regra de Cramer para J * [dt, dd] = -[r1, r2]
        dt = -(j22 * r1 - j12 * r2) / det
        dd = -(j11 * r2 - j21 * r1) / det
        # busca de linha: aceita o passo so se o residuo diminuir de fato.
        # Newton puro diverge nos casos extremos; com recuo ele sempre progride.
        norma = abs(r1) + abs(r2)
        passo = 1.0
        for _ in range(30):
            nt, nd = clampa(total + passo * dt, diff + passo * dd)
            try:
                n1, n2 = residuos(nt, nd)
            except InversaoFalhou:
                passo *= 0.5
                continue
            if abs(n1) + abs(n2) < norma:
                total, diff = nt, nd
                break
            passo *= 0.5
        else:
            raise InversaoFalhou("busca de linha nao encontrou passo que melhore")
    if not convergiu:
        raise InversaoFalhou("nao convergiu em max_iter")

    lh, la = (total + diff) / 2.0, (total - diff) / 2.0
    # faixa de sanidade: futebol de verdade vive entre ~0.15 e ~5 gols
    # esperados por lado. Fora disso e odd corrompida ou mercado exotico.
    if not (0.10 <= lh <= 6.0 and 0.10 <= la <= 6.0):
        raise InversaoFalhou(f"lambdas implausiveis: lh={lh:.3f}, la={la:.3f}")

    # verificacao final de ida-e-volta: recalcular e conferir contra o alvo.
    # Se a reconstrucao nao bate, a solucao nao vale - nao entregar numero
    # que nao reproduz a propria entrada.
    conf = poisson_dixon_coles(lh, la, rho=rho)
    for nome, obtido, esperado in (("p_home", conf["p_home"], p_home),
                                   ("p_draw", conf["p_draw"], p_draw),
                                   ("p_away", conf["p_away"], p_away)):
        if abs(obtido - esperado) > 1e-4:
            raise InversaoFalhou(
                f"round-trip falhou em {nome}: {obtido:.6f} != {esperado:.6f}")
    return lh, la


def devig_shin(odds, tol=1e-12, max_iter=300):
    """De-vig pelo metodo de SHIN.

    POR QUE (v28): POWER e proporcional assumem que a casa distribui a margem
    de forma homogenea. Ela nao distribui - o azarao carrega margem
    proporcionalmente maior (vies favorito-azarao), fenomeno documentado e
    reproduzido no estudo de ma-especificacao. Ignorar isso enviesa as
    probabilidades justas de forma SISTEMATICA, e todo mercado derivado herda
    o erro.

    Shin modela a margem como consequencia de negociantes informados: acha o
    parametro z (fracao de dinheiro informado) tal que as probabilidades
    resultantes somem 1. Por construcao ele tira MAIS margem dos azaroes que
    dos favoritos, que e exatamente a assimetria observada.

    Nao substitui o POWER - entra como CENARIO adicional de robustez, para o
    motor nao depender de nenhum metodo unico de de-vig.
    """
    imps = [1.0 / o for o in odds]
    S = sum(imps)
    if S <= 1.0:
        raise ValueError(
            f"soma das probabilidades implicitas = {S:.4f} <= 1 - odds sem "
            "margem sao dado de agregador invalido (regra v8), descartar")

    def p_de_z(z):
        if z >= 1.0:
            raise ValueError("z fora de faixa")
        out = []
        for pi in imps:
            raiz = math.sqrt(z * z + 4 * (1 - z) * pi * pi / S)
            out.append((raiz - z) / (2 * (1 - z)))
        return out

    def f(z):
        return sum(p_de_z(z)) - 1.0

    lo, hi = 0.0, 0.99
    # f(0) = S - 1 > 0 ; f cresce com z decrescente -> raiz no meio
    if f(lo) <= 0:
        return [pi / S for pi in imps]      # sem margem a corrigir
    if f(hi) > 0:
        raise ValueError("Shin nao convergiu - odds anomalas, descartar")
    for _ in range(max_iter):
        mid = (lo + hi) / 2
        v = f(mid)
        if abs(v) < tol:
            break
        if v > 0:
            lo = mid
        else:
            hi = mid
    return p_de_z((lo + hi) / 2)


# ------------------------------------------------------------------ metricas
def wilson_ci(k, n, z=1.96):
    """Retorna (taxa_observada, limite_inferior, limite_superior)."""
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return p, max(0.0, center - half), min(1.0, center + half)


def ev_unitario(prob, odd):
    """EV por 1 unidade apostada. Positivo = +EV."""
    return prob * (odd - 1) - (1 - prob)


def kelly_fraction(prob, odd, fraction=0.25):
    """Fracao de Kelly (default quarter-Kelly, decisao B2). Nunca usar full.
    Retorna fracao da banca (>=0)."""
    b = odd - 1
    full = (prob * b - (1 - prob)) / b
    return max(0.0, full * fraction)


def clv(odd_entrada, odd_fechamento):
    """Closing line value: positivo = batemos o fechamento."""
    return odd_entrada / odd_fechamento - 1


def brier(pairs):
    """pairs: [(prob_prevista, ocorreu_0_ou_1), ...]. Menor = melhor."""
    if not pairs:
        return None
    return sum((p - o) ** 2 for p, o in pairs) / len(pairs)


# ------------------------------------------------------------------ combinadas
# (v33). O item 10 "Combinadas" da metodologia sempre disse "prob conjunta
# real; imposto SGP" mas nunca teve formula nenhuma por tras - so texto.
#
# VALIDACAO EMPIRICA (nao suposicao): usando os 15.136-15.137 jogos reais do
# dataset de backtest (Fase 0, v32), medi a correlacao real entre limiares de
# CATEGORIAS DIFERENTES no mesmo jogo:
#
#   Over 2.5 gols   x Over 9.5 escanteios: phi=-0.004 | P(ambos) real 27.4% vs independente 27.5%
#   Over 2.5 gols   x Over 3.5 cartoes:    phi=+0.011 | P(ambos) real 30.5% vs independente 30.3%
#   Over 9.5 escant. x Over 3.5 cartoes:   phi=-0.010 | P(ambos) real 34.1% vs independente 34.3%
#
# Correlacao desprezivel nos tres pares (razao real/independente entre 0.993
# e 1.009) - tratar CATEGORIAS DIFERENTES (gols/escanteios/cartoes/chutes)
# como independentes numa combinada e sustentado por dado real, nao e uma
# aposta de metodo.
#
# ISSO NAO VALE para mercados MECANICAMENTE ligados - ex.: "Over 2.5 gols" e
# "Ambas Marcam" vem do MESMO placar (nao sao dois eventos, sao duas leituras
# do mesmo evento). Multiplicar as probabilidades desses dois seria dupla
# contagem, nao um erro de correlacao - NUNCA combinar pernas que descrevem
# o mesmo desfecho subjacente (mesma familia de mercado no mesmo jogo).
def prob_combinada(probs):
    """Probabilidade conjunta de N pernas, assumindo independencia entre
    elas. So valido para pernas de CATEGORIAS DIFERENTES (ver nota acima) -
    o chamador e responsavel por garantir que nenhum par de pernas descreve
    o mesmo desfecho subjacente."""
    p = 1.0
    for x in probs:
        if not (0.0 <= x <= 1.0):
            raise ValueError(f"probabilidade fora de [0,1]: {x}")
        p *= x
    return p


def odd_combinada(odds):
    """Odd final de uma combinada (produto das odds das pernas)."""
    o = 1.0
    for x in odds:
        if x <= 1.0:
            raise ValueError(f"odd invalida na combinada: {x}")
        o *= x
    return o


def ev_combinada(probs, odds):
    """EV por unidade apostada na combinada inteira - reusa ev_unitario()
    sobre a probabilidade e a odd JA combinadas."""
    if len(probs) != len(odds):
        raise ValueError("probs e odds precisam ter o mesmo tamanho")
    return ev_unitario(prob_combinada(probs), odd_combinada(odds))


# --------------------------------------------------------------------- demo
def _demo():
    print("== AUTO-TESTE com odds reais Betano de 26/07 (Flamengo x Sao Paulo) ==")
    fair = devig_power([1.50, 4.20, 7.10])
    print(f"1X2 1.50/4.20/7.10 -> justas: {fair[0]:.1%} / {fair[1]:.1%} / {fair[2]:.1%} "
          f"(soma {sum(fair):.4f})")
    fair_t = devig_power([1.90, 1.91])
    print(f"Total 2.5 1.90/1.91 -> justas: over {fair_t[0]:.1%} / under {fair_t[1]:.1%}")

    print("\n== Dixon-Coles exemplo: lambda_casa=1.9, lambda_fora=0.8 ==")
    m = poisson_dixon_coles(1.9, 0.8)
    print(f"1X2: {m['p_home']:.1%} / {m['p_draw']:.1%} / {m['p_away']:.1%} | "
          f"over2.5 {m['over_2.5']:.1%} | BTTS {m['btts']:.1%}")

    print("\n== Wilson / EV / Kelly / CLV ==")
    p, lo, hi = wilson_ci(6, 16)
    print(f"6/16 acertos -> {p:.1%} [Wilson 95%: {lo:.1%}-{hi:.1%}]")
    print(f"EV(prob=0.55, odd=2.00) = {ev_unitario(0.55, 2.0):+.3f}u")
    print(f"quarter-Kelly(0.55, 2.00) = {kelly_fraction(0.55, 2.0):.2%} da banca")
    print(f"CLV(entrada 2.10, fechamento 1.95) = {clv(2.10, 1.95):+.2%}")
    print(f"Brier[(0.65,1),(0.56,0)] = {brier([(0.65,1),(0.56,0)]):.4f}")

    print("\n== Mercados de contagem (v32): poisson_total/poisson_grid/ewma_shrinkage ==")
    pt = poisson_total(9.8, linhas=(8.5, 9.5, 10.5))
    massa = sum(pt["distribuicao"].values())
    print(f"total escanteios lambda=9.8 -> over9.5 {pt['over_9.5']:.1%} / "
          f"under9.5 {pt['under_9.5']:.1%} (massa coberta por max_n: {massa:.5f})")
    assert abs(pt["over_9.5"] + pt["under_9.5"] - 1.0) < 1e-9, "over+under tem que somar 1"
    assert massa > 0.999, "max_n=30 devia cobrir >99.9% da massa em lambda=9.8"
    assert pt["over_8.5"] > pt["over_9.5"] > pt["over_10.5"], "over tem que cair com a linha"

    pg = poisson_grid(5.2, 4.6)
    massa_g = sum(pg["grid"].values())
    over_a = over_under_time(pg, "a", 5.5)
    print(f"grid por time (5.2/4.6) -> over5.5 lado A: {over_a:.1%} (massa: {massa_g:.5f})")
    assert massa_g > 0.999, "max_n=15 devia cobrir >99.9% da massa em lambda~5"

    lam = ewma_shrinkage([6, 8, 5], media_liga=9.5, alpha=3.0)
    lam_sem_hist = ewma_shrinkage([], media_liga=9.5)
    print(f"ewma_shrinkage([6,8,5], liga=9.5) = {lam:.2f} | sem historico = {lam_sem_hist:.2f}")
    assert lam_sem_hist == 9.5, "sem historico tem que devolver a media da liga"
    assert 6.0 < lam < 9.5, "com historico abaixo da liga, resultado tem que ficar entre os dois"
    print("Auto-testes de mercados de contagem OK.")

    print("\n== Combinadas (v33): prob_combinada/odd_combinada/ev_combinada ==")
    # exemplo do proprio usuario: +8.5 escanteios @1.30 + +1.5 gols @1.20
    odds_pernas = [1.30, 1.20]
    probs_pernas = [0.75, 0.83]  # ilustrativo - viria de taxa_empirica() (forma_recente.py)
    odd_final = odd_combinada(odds_pernas)
    prob_final = prob_combinada(probs_pernas)
    ev_final = ev_combinada(probs_pernas, odds_pernas)
    print(f"pernas: odds {odds_pernas} probs {probs_pernas}")
    print(f"odd combinada = {odd_final:.2f} | prob combinada = {prob_final:.1%} | "
          f"EV = {ev_final:+.3f}u")
    assert abs(odd_final - 1.56) < 1e-9, "odd_combinada(1.30,1.20) deveria ser 1.56"
    assert abs(prob_final - 0.6225) < 1e-9, "prob_combinada(0.75,0.83) deveria ser 0.6225"
    assert abs(ev_final - ev_unitario(prob_final, odd_final)) < 1e-9, \
        "ev_combinada deveria bater com ev_unitario sobre os valores combinados"
    print("Auto-testes de combinadas OK.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        _demo()
    else:
        print(__doc__)
