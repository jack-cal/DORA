# SUMUWW · Documentación

SUMUWW PC 0.57.46 · El nodo valida, guarda, retransmite y permite consultar la cadena.

## Formato de firma

El SDK opcional de código fuente construye transacciones y verifica firmas recibidas sin claves ni red. No es un firmador ni un comando del nodo. La limitación P2WPKH corresponde al formato del ejemplo, no al nodo. La cartera personal existente sigue disponible.

## API RPC y HTTP

validateaddress comprueba la suma de verificación y la red seleccionada. decoderawtransaction devuelve decoded_only, sin certificar firmas ni confirmaciones. Las salidas OP_RETURN conservan datos para programas externos. El nodo incorpora consultas de comisiones, comprobaciones previas al envío, estado de sustituciones RBF y registros de datos ordenados por bloque. Se valida la sustitución antes de eliminar transacciones pendientes. Las firmas múltiples y las salidas bloqueadas están implementadas para pruebas aisladas; aún no están activadas en la red pública.

## Verificación

Ejecute python examples/node_contract.py desde el código fuente con sus dependencias. Claves públicas de prueba y un regtest temporal verifican envío, rechazo, confirmaciones, reorganización y persistencia. No se usan fondos reales, perfiles personales ni firmadores físicos.

```text
network: sumuww (dora)
genesis: 00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97
HRP: sumuww
P2P magic: d052470c
1 SMW = 100000000 yugeon
```

[Interfaz del nodo](EXCHANGE_INTEGRATION.html) · [API RPC y HTTP](RPC_API.html) · [Operación del nodo](NETWORK_RUNBOOK.html) · [Notas de versión](RELEASE_NOTES.html) · [Verificación](EXCHANGE_EXAMPLES.html)

[Referencia ampliada en inglés](../../../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../../../API_CONTRACT.json) · [vectors.json](../../../../../examples/exchange/vectors.json)
