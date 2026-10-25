# SUMUWW · 0.57.45 / 0.6.94

El nodo incorpora consultas de comisiones, comprobaciones previas al envío, estado de sustituciones RBF y registros de datos ordenados por bloque. Se valida la sustitución antes de eliminar transacciones pendientes. Las firmas múltiples y las salidas bloqueadas están implementadas para pruebas aisladas; aún no están activadas en la red pública.

1 SMW = 100.000.000 yugeon. Las tarifas automáticas ofrecen tres niveles según las observaciones locales, sin garantizar el tiempo de confirmación. Puedes introducir una tarifa en yugeon/vB. Revisa la comisión final y el total en SMW antes de enviar. Una transacción rechazada no descuenta saldo.

`1 yugeon = 0.00000001 SMW`

`1 SMW = 100,000,000 yugeon`

La tarifa automática considera el volumen pendiente, la capacidad de los bloques y la prioridad de las transacciones. No usa tarifas de bloques anteriores. Con poca espera mantiene la tarifa mínima. La vista previa se actualiza; la confirmación final fija la tarifa. Los datos corresponden al nodo local conectado, no a todos los nodos.

El historial de sustituciones registrado por este nodo se conserva al reiniciar la cartera. Las transacciones retiradas no afectan al saldo.

El explorador muestra las condiciones reveladas de multifirma y bloqueo de salidas. La activación en la red pública aún no tiene fecha.
