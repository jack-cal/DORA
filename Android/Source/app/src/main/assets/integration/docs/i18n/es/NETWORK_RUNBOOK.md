# SUMUWW Android 0.6.95 · Operación del nodo

SUMUWW Android 0.6.95 · El nodo valida, guarda, retransmite y permite consultar la cadena.

## Red y direcciones

La red pública es `sumuww`; `dora` es su alias interno. Compruebe el hash de génesis indicado abajo. Las direcciones nativas usan P2WPKH witness v0 y HASH160 de una clave pública secp256k1 comprimida. No hay memo ni etiqueta obligatorios. Rechace direcciones de otra red o con suma de comprobación inválida. Registre la rama HD de recepción/cambio y el índice; no suponga la ruta de derivación de Bitcoin.

## Consulta de transacciones y bloques

`getrawtransaction` busca en la cadena activa y el mempool, no transacciones exclusivamente huérfanas. Las entradas identifican salidas anteriores, no un remitente único. `getblock` acepta `verbose` booleano; los bloques inactivos guardados tienen `active=false` y `confirmations=-1`. Sus transacciones en bruto siguen accesibles por hash de bloque. `findspendingtransaction` solo busca gastos confirmados de la cadena activa; null no demuestra disponibilidad. Compruebe `gettxout` con `include_mempool=true`. Confirmaciones y estado activo pueden cambiar tras una reorganización.

[API_CONTRACT.json](../../../API_CONTRACT.json)
