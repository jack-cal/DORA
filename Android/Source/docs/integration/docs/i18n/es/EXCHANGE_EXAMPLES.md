# SUMUWW Android 0.6.95 · Verificación

SUMUWW Android 0.6.95 · El nodo valida, guarda, retransmite y permite consultar la cadena.

La especificación API describe el núcleo del nodo integrado. La aplicación Android no tiene pantalla de configuración RPC.

## API RPC y HTTP

validateaddress comprueba la suma de verificación y la red seleccionada. decoderawtransaction devuelve decoded_only, sin certificar firmas ni confirmaciones. Las salidas OP_RETURN conservan datos para programas externos. El nodo incorpora consultas de comisiones, comprobaciones previas al envío, estado de sustituciones RBF y registros de datos ordenados por bloque. Se valida la sustitución antes de eliminar transacciones pendientes. Las firmas múltiples y las salidas bloqueadas están implementadas para pruebas aisladas; aún no están activadas en la red pública.

## Consulta de transacciones y bloques

`getrawtransaction` busca en la cadena activa y el mempool, no transacciones exclusivamente huérfanas. Las entradas identifican salidas anteriores, no un remitente único. `getblock` acepta `verbose` booleano; los bloques inactivos guardados tienen `active=false` y `confirmations=-1`. Sus transacciones en bruto siguen accesibles por hash de bloque. `findspendingtransaction` solo busca gastos confirmados de la cadena activa; null no demuestra disponibilidad. Compruebe `gettxout` con `include_mempool=true`. Confirmaciones y estado activo pueden cambiar tras una reorganización.

[API_CONTRACT.json](../../../API_CONTRACT.json)
