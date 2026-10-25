# SUMUWW · Operación del nodo

SUMUWW PC 0.57.46 · El nodo valida, guarda, retransmite y permite consultar la cadena.

## Red y direcciones

La red pública es `sumuww`; `dora` es su alias interno. Compruebe el hash de génesis indicado abajo. Las direcciones nativas usan P2WPKH witness v0 y HASH160 de una clave pública secp256k1 comprimida. No hay memo ni etiqueta obligatorios. Rechace direcciones de otra red o con suma de comprobación inválida. Registre la rama HD de recepción/cambio y el índice; no suponga la ruta de derivación de Bitcoin.

## Autenticación y límites

Active RPC explícitamente en la dirección numérica local `127.0.0.1:18443` con su token Bearer privado. No se expone desbloqueo del monedero ni firma remota. Use un servicio local o túnel autenticado; se rechazan solicitudes de navegador con Origin/Referer. JSON-RPC usa POST `/rpc`, `params` como objeto/array e `id`; las notificaciones devuelven HTTP 204. Límites: cuerpo 8004096 bytes, cabeceras 8192, lote 16, solicitudes simultáneas 16, plazo 10 segundos; limit 1–1000 y offset 0–1000000. Hay 28 métodos y 11 rutas REST.

## Consulta de transacciones y bloques

`getrawtransaction` busca en la cadena activa y el mempool, no transacciones exclusivamente huérfanas. Las entradas identifican salidas anteriores, no un remitente único. `getblock` acepta `verbose` booleano; los bloques inactivos guardados tienen `active=false` y `confirmations=-1`. Sus transacciones en bruto siguen accesibles por hash de bloque. `findspendingtransaction` solo busca gastos confirmados de la cadena activa; null no demuestra disponibilidad. Compruebe `gettxout` con `include_mempool=true`. Confirmaciones y estado activo pueden cambiar tras una reorganización.

## Verificación

Ejecute python examples/node_contract.py desde el código fuente con sus dependencias. Claves públicas de prueba y un regtest temporal verifican envío, rechazo, confirmaciones, reorganización y persistencia. No se usan fondos reales, perfiles personales ni firmadores físicos.

```text
network: sumuww (dora)
genesis: 00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97
HRP: sumuww
P2P magic: d052470c
1 SMW = 100000000 yugeon
```

[Documentación](README.html) · [Interfaz del nodo](EXCHANGE_INTEGRATION.html) · [API RPC y HTTP](RPC_API.html) · [Notas de versión](RELEASE_NOTES.html) · [Verificación](EXCHANGE_EXAMPLES.html)

[Referencia ampliada en inglés](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
