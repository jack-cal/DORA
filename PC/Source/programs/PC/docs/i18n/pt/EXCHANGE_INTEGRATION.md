# SUMUWW · Interface do nó

SUMUWW PC 0.57.46 · O nó valida, guarda, retransmite e permite consultar a cadeia.

## Rede e endereços

A rede pública é `sumuww`; `dora` é seu alias interno. Confira o hash de gênese abaixo. Endereços nativos usam P2WPKH witness v0 e HASH160 de uma chave pública secp256k1 comprimida. Não há memo ou tag obrigatórios. Rejeite endereços de outra rede e checksums inválidos. Registre ramo HD de recebimento/troco e índice; não presuma a derivação do Bitcoin.

## Formato de assinatura

O SDK opcional no código-fonte monta transações e verifica assinaturas recebidas sem chaves nem rede. Não é um assinador nem um comando do nó. A limitação P2WPKH pertence ao formato do exemplo, não ao nó. A carteira pessoal existente continua disponível.

## API RPC e HTTP

validateaddress verifica a soma de verificação e a rede escolhida. decoderawtransaction retorna decoded_only, sem comprovar assinatura ou confirmação. As saídas OP_RETURN preservam dados para programas externos. O nó inclui consultas de taxas, verificação antes do envio, estado de substituições RBF e leitura ordenada dos dados dos blocos. A substituição é validada antes de remover transações pendentes. As assinaturas múltiplas e as saídas bloqueadas estão implementadas para testes isolados; ainda não estão ativas na rede pública.

## Autenticação e limites

Ative RPC explicitamente no loopback numérico `127.0.0.1:18443`, com seu token Bearer privado. Não há desbloqueio de carteira nem assinatura remota. Use serviço local ou túnel autenticado; pedidos de navegador com Origin/Referer são rejeitados. JSON-RPC usa POST `/rpc`, `params` objeto/array e `id`; notificações retornam HTTP 204. Limites: corpo 8004096 bytes, cabeçalhos 8192, lote 16, pedidos simultâneos 16, prazo 10 segundos; limit 1–1000 e offset 0–1000000. São 28 métodos e 11 rotas REST.

## Valores e saídas disponíveis

`_units` representa unidades mínimas inteiras; `_smw`, texto com 8 casas decimais; `_dora`, alias de compatibilidade. Não existe campo monetário `_sumuww`. 1 SMW = 100000000 unidades. `gettxout` não tem `spendable` e pode retornar recompensas imaturas. Coinbase precisa de pelo menos 100 confirmações para gasto no próximo bloco. Filtre `listunspent` por `spendable`; o valor available de `getaddressbalance` exclui fundos imaturos e comprometidos em gastos pendentes. Novas saídas do mempool não estão confirmadas. Verifique a ponta entre páginas e revalide as entradas escolhidas.

1 SMW = 100.000.000 yugeon. As taxas automáticas oferecem três níveis com base nas observações locais, sem garantir o tempo de confirmação. Pode introduzir uma taxa em yugeon/vB. Confira a comissão final e o total em SMW antes de enviar. Uma transação rejeitada não desconta o saldo.

`1 yugeon = 0.00000001 SMW` · `1 SMW = 100000000 yugeon`

| API / wallet | yugeon / SMW |
|---|---|
| minimum relay | 1 yugeon/vB |
| automatic cap | 0.01 SMW |
| manual cap | 1 SMW |
| manual rate | 1–100000 yugeon/vB |

A taxa automática considera o volume pendente, a capacidade dos blocos e a prioridade das transações. Não usa taxas de blocos anteriores. Com pouca espera, mantém a taxa mínima. A prévia se atualiza; a confirmação final fixa a taxa. Os dados abrangem o nó local conectado, não todos os nós.

O histórico de substituições registrado por este nó permanece após reiniciar a carteira. As transações removidas não afetam o saldo.

O histórico de mineração separa a nova emissão, as taxas e a recompensa total de cada bloco. O valor recebido pela sua carteira aparece separadamente. Uma reivindicação parcial não permite atribuir os valores de cada componente. O nó oferece 28 métodos RPC, incluindo estimativa de taxas, e valida e retransmite transações assinadas.

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

[Documentação](README.html) · [API RPC e HTTP](RPC_API.html) · [Operação do nó](NETWORK_RUNBOOK.html) · [Notas da versão](RELEASE_NOTES.html) · [Verificação](EXCHANGE_EXAMPLES.html)

[Referência detalhada em inglês](../../../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../../../API_CONTRACT.json) · [vectors.json](../../../../../examples/exchange/vectors.json)
