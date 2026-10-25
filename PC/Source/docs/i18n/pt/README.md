# SUMUWW · Documentação

SUMUWW PC 0.57.46 · O nó valida, guarda, retransmite e permite consultar a cadeia.

## Formato de assinatura

O SDK opcional no código-fonte monta transações e verifica assinaturas recebidas sem chaves nem rede. Não é um assinador nem um comando do nó. A limitação P2WPKH pertence ao formato do exemplo, não ao nó. A carteira pessoal existente continua disponível.

## API RPC e HTTP

validateaddress verifica a soma de verificação e a rede escolhida. decoderawtransaction retorna decoded_only, sem comprovar assinatura ou confirmação. As saídas OP_RETURN preservam dados para programas externos. O nó inclui consultas de taxas, verificação antes do envio, estado de substituições RBF e leitura ordenada dos dados dos blocos. A substituição é validada antes de remover transações pendentes. As assinaturas múltiplas e as saídas bloqueadas estão implementadas para testes isolados; ainda não estão ativas na rede pública.

## Verificação

Execute python examples/node_contract.py no código-fonte com as dependências instaladas. Chaves públicas de teste e regtest temporário verificam envio, rejeição, confirmações, reorganização e persistência. Não são usados fundos reais, perfis pessoais nem assinadores físicos.

```text
network: sumuww (dora)
genesis: 00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97
HRP: sumuww
P2P magic: d052470c
1 SMW = 100000000 yugeon
```

[Interface do nó](EXCHANGE_INTEGRATION.html) · [API RPC e HTTP](RPC_API.html) · [Operação do nó](NETWORK_RUNBOOK.html) · [Notas da versão](RELEASE_NOTES.html) · [Verificação](EXCHANGE_EXAMPLES.html)

[Referência detalhada em inglês](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
