# SUMUWW · Operação do nó

SUMUWW PC 0.57.46 · O nó valida, guarda, retransmite e permite consultar a cadeia.

## Rede e endereços

A rede pública é `sumuww`; `dora` é seu alias interno. Confira o hash de gênese abaixo. Endereços nativos usam P2WPKH witness v0 e HASH160 de uma chave pública secp256k1 comprimida. Não há memo ou tag obrigatórios. Rejeite endereços de outra rede e checksums inválidos. Registre ramo HD de recebimento/troco e índice; não presuma a derivação do Bitcoin.

## Autenticação e limites

Ative RPC explicitamente no loopback numérico `127.0.0.1:18443`, com seu token Bearer privado. Não há desbloqueio de carteira nem assinatura remota. Use serviço local ou túnel autenticado; pedidos de navegador com Origin/Referer são rejeitados. JSON-RPC usa POST `/rpc`, `params` objeto/array e `id`; notificações retornam HTTP 204. Limites: corpo 8004096 bytes, cabeçalhos 8192, lote 16, pedidos simultâneos 16, prazo 10 segundos; limit 1–1000 e offset 0–1000000. São 28 métodos e 11 rotas REST.

## Consulta de transações e blocos

`getrawtransaction` pesquisa a cadeia ativa e o mempool, não transações apenas órfãs. Entradas identificam saídas anteriores, não um remetente único. `getblock` recebe `verbose` booleano; blocos inativos armazenados têm `active=false` e `confirmations=-1`. Suas transações brutas continuam acessíveis pelo hash do bloco. `findspendingtransaction` busca apenas gastos confirmados ativos; null não prova disponibilidade. Consulte `gettxout` com `include_mempool=true`. Confirmações e estado ativo podem mudar após reorganização.

## Verificação

Execute python examples/node_contract.py no código-fonte com as dependências instaladas. Chaves públicas de teste e regtest temporário verificam envio, rejeição, confirmações, reorganização e persistência. Não são usados fundos reais, perfis pessoais nem assinadores físicos.

```text
network: sumuww (dora)
genesis: 00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97
HRP: sumuww
P2P magic: d052470c
1 SMW = 100000000 yugeon
```

[Documentação](README.html) · [Interface do nó](EXCHANGE_INTEGRATION.html) · [API RPC e HTTP](RPC_API.html) · [Notas da versão](RELEASE_NOTES.html) · [Verificação](EXCHANGE_EXAMPLES.html)

[Referência detalhada em inglês](../../../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../../../API_CONTRACT.json) · [vectors.json](../../../../../examples/exchange/vectors.json)
