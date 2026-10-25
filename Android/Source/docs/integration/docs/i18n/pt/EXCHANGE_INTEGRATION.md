# SUMUWW Android 0.6.95 · Interface do nó

SUMUWW Android 0.6.95 · O nó valida, guarda, retransmite e permite consultar a cadeia.

A especificação API descreve o núcleo do nó integrado. O aplicativo Android não tem tela de configuração RPC.

## Rede e endereços

A rede pública é `sumuww`; `dora` é seu alias interno. Confira o hash de gênese abaixo. Endereços nativos usam P2WPKH witness v0 e HASH160 de uma chave pública secp256k1 comprimida. Não há memo ou tag obrigatórios. Rejeite endereços de outra rede e checksums inválidos. Registre ramo HD de recebimento/troco e índice; não presuma a derivação do Bitcoin.

## API RPC e HTTP

validateaddress verifica a soma de verificação e a rede escolhida. decoderawtransaction retorna decoded_only, sem comprovar assinatura ou confirmação. As saídas OP_RETURN preservam dados para programas externos. O nó inclui consultas de taxas, verificação antes do envio, estado de substituições RBF e leitura ordenada dos dados dos blocos. A substituição é validada antes de remover transações pendentes. As assinaturas múltiplas e as saídas bloqueadas estão implementadas para testes isolados; ainda não estão ativas na rede pública.

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

[API_CONTRACT.json](../../../API_CONTRACT.json)
