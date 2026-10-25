# SUMUWW Android 0.6.95 · Interfaz del nodo

SUMUWW Android 0.6.95 · El nodo valida, guarda, retransmite y permite consultar la cadena.

La especificación API describe el núcleo del nodo integrado. La aplicación Android no tiene pantalla de configuración RPC.

## Red y direcciones

La red pública es `sumuww`; `dora` es su alias interno. Compruebe el hash de génesis indicado abajo. Las direcciones nativas usan P2WPKH witness v0 y HASH160 de una clave pública secp256k1 comprimida. No hay memo ni etiqueta obligatorios. Rechace direcciones de otra red o con suma de comprobación inválida. Registre la rama HD de recepción/cambio y el índice; no suponga la ruta de derivación de Bitcoin.

## API RPC y HTTP

validateaddress comprueba la suma de verificación y la red seleccionada. decoderawtransaction devuelve decoded_only, sin certificar firmas ni confirmaciones. Las salidas OP_RETURN conservan datos para programas externos. El nodo incorpora consultas de comisiones, comprobaciones previas al envío, estado de sustituciones RBF y registros de datos ordenados por bloque. Se valida la sustitución antes de eliminar transacciones pendientes. Las firmas múltiples y las salidas bloqueadas están implementadas para pruebas aisladas; aún no están activadas en la red pública.

## Importes y salidas disponibles

`_units` son unidades mínimas enteras; `_smw` es una cadena de 8 decimales; `_dora` es un alias de compatibilidad. No existe un campo monetario `_sumuww`. 1 SMW = 100000000 unidades. `gettxout` no tiene `spendable` y puede devolver recompensas inmaduras. Una coinbase necesita al menos 100 confirmaciones para gastarse en el siguiente bloque. Filtre `listunspent` por `spendable`; el importe available de `getaddressbalance` excluye fondos inmaduros y comprometidos en gastos pendientes. Las nuevas salidas del mempool no están confirmadas. Compruebe la punta entre páginas y revalide las entradas elegidas.

1 SMW = 100.000.000 yugeon. Las tarifas automáticas ofrecen tres niveles según las observaciones locales, sin garantizar el tiempo de confirmación. Puedes introducir una tarifa en yugeon/vB. Revisa la comisión final y el total en SMW antes de enviar. Una transacción rechazada no descuenta saldo.

`1 yugeon = 0.00000001 SMW` · `1 SMW = 100000000 yugeon`

| API / wallet | yugeon / SMW |
|---|---|
| minimum relay | 1 yugeon/vB |
| automatic cap | 0.01 SMW |
| manual cap | 1 SMW |
| manual rate | 1–100000 yugeon/vB |

La tarifa automática considera el volumen pendiente, la capacidad de los bloques y la prioridad de las transacciones. No usa tarifas de bloques anteriores. Con poca espera mantiene la tarifa mínima. La vista previa se actualiza; la confirmación final fija la tarifa. Los datos corresponden al nodo local conectado, no a todos los nodos.

El historial de sustituciones registrado por este nodo se conserva al reiniciar la cartera. Las transacciones retiradas no afectan al saldo.

El historial de minería separa la nueva emisión, las comisiones y la recompensa total de cada bloque. El importe recibido por tu cartera se muestra por separado. Si la recompensa se reclama parcialmente, no se inventa un reparto entre sus componentes. El nodo ofrece 28 métodos RPC, incluida la estimación de comisiones, y valida y retransmite transacciones firmadas.

## Consulta de transacciones y bloques

`getrawtransaction` busca en la cadena activa y el mempool, no transacciones exclusivamente huérfanas. Las entradas identifican salidas anteriores, no un remitente único. `getblock` acepta `verbose` booleano; los bloques inactivos guardados tienen `active=false` y `confirmations=-1`. Sus transacciones en bruto siguen accesibles por hash de bloque. `findspendingtransaction` solo busca gastos confirmados de la cadena activa; null no demuestra disponibilidad. Compruebe `gettxout` con `include_mempool=true`. Confirmaciones y estado activo pueden cambiar tras una reorganización.

[API_CONTRACT.json](../../../API_CONTRACT.json)
