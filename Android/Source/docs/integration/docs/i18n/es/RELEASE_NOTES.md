# SUMUWW Android 0.6.95 · Notas de versión

SUMUWW Android 0.6.95 · El nodo valida, guarda, retransmite y permite consultar la cadena.

La especificación API describe el núcleo del nodo integrado. La aplicación Android no tiene pantalla de configuración RPC.

## API RPC y HTTP

validateaddress comprueba la suma de verificación y la red seleccionada. decoderawtransaction devuelve decoded_only, sin certificar firmas ni confirmaciones. Las salidas OP_RETURN conservan datos para programas externos. El nodo incorpora consultas de comisiones, comprobaciones previas al envío, estado de sustituciones RBF y registros de datos ordenados por bloque. Se valida la sustitución antes de eliminar transacciones pendientes. Las firmas múltiples y las salidas bloqueadas están implementadas para pruebas aisladas; aún no están activadas en la red pública.

[API_CONTRACT.json](../../../API_CONTRACT.json)
