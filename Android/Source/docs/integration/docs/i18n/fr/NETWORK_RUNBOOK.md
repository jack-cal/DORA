# SUMUWW Android 0.6.95 · Exploitation du nœud

SUMUWW Android 0.6.95 · Le nœud valide, conserve, relaie et expose les données de la chaîne.

## Réseau et adresses

Le réseau public est `sumuww`, avec l’alias interne `dora`. Vérifiez le hash de genèse ci-dessous. Les adresses natives utilisent P2WPKH witness v0 et HASH160 d’une clé publique secp256k1 compressée. Aucun mémo ni tag n’est obligatoire. Rejetez les adresses d’un autre réseau et les sommes de contrôle invalides. Notez la branche réception/monnaie et l’index HD ; ne supposez pas le chemin de dérivation de Bitcoin.

## Recherche de transactions et de blocs

`getrawtransaction` recherche la chaîne active et le mempool, pas les seules branches orphelines. Les entrées désignent des sorties précédentes, pas une adresse d’expéditeur unique. `getblock` reçoit un `verbose` booléen ; un bloc inactif conservé a `active=false` et `confirmations=-1`. Ses transactions brutes restent accessibles par hash de bloc. `findspendingtransaction` ne cherche que les dépenses confirmées actives ; null ne prouve pas la disponibilité. Vérifiez `gettxout` avec `include_mempool=true`. Confirmations et état actif peuvent changer après réorganisation.

[API_CONTRACT.json](../../../API_CONTRACT.json)
