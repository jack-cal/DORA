# SUMUWW Android 0.6.95 · Operação do nó

SUMUWW Android 0.6.95 · O nó valida, guarda, retransmite e permite consultar a cadeia.

## Rede e endereços

A rede pública é `sumuww`; `dora` é seu alias interno. Confira o hash de gênese abaixo. Endereços nativos usam P2WPKH witness v0 e HASH160 de uma chave pública secp256k1 comprimida. Não há memo ou tag obrigatórios. Rejeite endereços de outra rede e checksums inválidos. Registre ramo HD de recebimento/troco e índice; não presuma a derivação do Bitcoin.

## Consulta de transações e blocos

`getrawtransaction` pesquisa a cadeia ativa e o mempool, não transações apenas órfãs. Entradas identificam saídas anteriores, não um remetente único. `getblock` recebe `verbose` booleano; blocos inativos armazenados têm `active=false` e `confirmations=-1`. Suas transações brutas continuam acessíveis pelo hash do bloco. `findspendingtransaction` busca apenas gastos confirmados ativos; null não prova disponibilidade. Consulte `gettxout` com `include_mempool=true`. Confirmações e estado ativo podem mudar após reorganização.

[API_CONTRACT.json](../../../API_CONTRACT.json)
