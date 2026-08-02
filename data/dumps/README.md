# Dumps brutos de extracao

Toda extracao bem-sucedida de catalogo de casa deve ser salva aqui como
`YYYY-MM-DD-casa.json` e commitada.

Por que (v26, 02/08): em 01/08 a extracao v23 trouxe 542 eventos da Betano,
mas o dump so existiu dentro da resposta da ferramenta. No dia seguinte -
exatamente quando o usuario pediu para testar a extracao varias vezes e de
varias formas - nao havia dado real contra o qual re-rodar `scan_odds.py`.
Os conectores so funcionam em turno interativo (decisao 39), entao janela
de extracao perdida e dado perdido.

Extracao que nao foi persistida nao pode ser reauditada.
