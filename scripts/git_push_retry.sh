#!/usr/bin/env bash
# Push com retry/backoff (decisao 23c) - ate aqui essa regra so existia
# como instrucao textual na metodologia, reimplementada a mao em bash cru
# em toda execucao, sem nenhuma verificacao automatica (achado de
# auditoria, 08/08). 4 tentativas, backoff 2/4/8/16s.
#
# Uso:
#   scripts/git_push_retry.sh                    # push da branch atual pra origin
#   scripts/git_push_retry.sh <branch>            # push de uma branch especifica
#   scripts/git_push_retry.sh <remote> <branch>   # remote + branch explicitos
set -u

if [ "$#" -ge 2 ]; then
    remote="$1"
    branch="$2"
elif [ "$#" -eq 1 ]; then
    remote="origin"
    branch="$1"
else
    remote="origin"
    branch="$(git rev-parse --abbrev-ref HEAD)"
fi

delays=(2 4 8 16)
tentativa=1
max_tentativas=4

while [ "$tentativa" -le "$max_tentativas" ]; do
    if git push -u "$remote" "$branch"; then
        echo "git_push_retry: sucesso na tentativa $tentativa"
        exit 0
    fi
    if [ "$tentativa" -lt "$max_tentativas" ]; then
        espera="${delays[$((tentativa - 1))]}"
        echo "git_push_retry: tentativa $tentativa falhou, esperando ${espera}s antes de tentar de novo..." >&2
        sleep "$espera"
    fi
    tentativa=$((tentativa + 1))
done

echo "git_push_retry: FALHOU apos $max_tentativas tentativas (remote=$remote branch=$branch)" >&2
exit 1
