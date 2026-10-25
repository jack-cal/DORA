# SUMUWW · Verificação

SUMUWW PC 0.57.46 · O nó valida, guarda, retransmite e permite consultar a cadeia.

## Formato de assinatura

O SDK opcional no código-fonte monta transações e verifica assinaturas recebidas sem chaves nem rede. Não é um assinador nem um comando do nó. A limitação P2WPKH pertence ao formato do exemplo, não ao nó. A carteira pessoal existente continua disponível.

## Verificação

Execute python examples/node_contract.py no código-fonte com as dependências instaladas. Chaves públicas de teste e regtest temporário verificam envio, rejeição, confirmações, reorganização e persistência. Não são usados fundos reais, perfis pessoais nem assinadores físicos.

```powershell
python examples/node_contract.py
python -m unittest tests.test_node_contract tests.test_rpc -v
```

[Documentação](README.html) · [Interface do nó](EXCHANGE_INTEGRATION.html) · [API RPC e HTTP](RPC_API.html) · [Operação do nó](NETWORK_RUNBOOK.html) · [Notas da versão](RELEASE_NOTES.html)

[Referência detalhada em inglês](../../../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../../../API_CONTRACT.json) · [vectors.json](../../../../../examples/exchange/vectors.json)
