# SUMUWW Android 0.6.95 · Notas da versão

SUMUWW Android 0.6.95 · O nó valida, guarda, retransmite e permite consultar a cadeia.

A especificação API descreve o núcleo do nó integrado. O aplicativo Android não tem tela de configuração RPC.

## API RPC e HTTP

validateaddress verifica a soma de verificação e a rede escolhida. decoderawtransaction retorna decoded_only, sem comprovar assinatura ou confirmação. As saídas OP_RETURN preservam dados para programas externos. O nó inclui consultas de taxas, verificação antes do envio, estado de substituições RBF e leitura ordenada dos dados dos blocos. A substituição é validada antes de remover transações pendentes. As assinaturas múltiplas e as saídas bloqueadas estão implementadas para testes isolados; ainda não estão ativas na rede pública.

[API_CONTRACT.json](../../../API_CONTRACT.json)
