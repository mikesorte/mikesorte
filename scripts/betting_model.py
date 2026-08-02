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


def win_by_margin(model_out, min_margin):
    """P(mandante vence por >= min_margin gols de diferenca), a partir do
    dict retornado por poisson_dixon_coles(). Uso tipico: mata-mata em que
    o mandante precisa reverter o placar agregado por N gols (ex.: Grêmio
    precisando vencer por 2+ apos derrota de 3-2 na ida)."""
    return sum(p for m, p in model_out["margins"].items() if m >= min_margin)


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


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        _demo()
    else:
        print(__doc__)
