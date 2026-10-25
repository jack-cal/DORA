# SUMUWW Android 0.6.95 · Documentation

SUMUWW Android 0.6.95 · Le nœud valide, conserve, relaie et expose les données de la chaîne.

## Réseau et adresses

Le réseau public est `sumuww`, avec l’alias interne `dora`. Vérifiez le hash de genèse ci-dessous. Les adresses natives utilisent P2WPKH witness v0 et HASH160 d’une clé publique secp256k1 compressée. Aucun mémo ni tag n’est obligatoire. Rejetez les adresses d’un autre réseau et les sommes de contrôle invalides. Notez la branche réception/monnaie et l’index HD ; ne supposez pas le chemin de dérivation de Bitcoin.

## Montants et sorties disponibles

`_units` désigne des unités minimales entières ; `_smw` une chaîne à 8 décimales ; `_dora` un alias compatible. Aucun champ monétaire `_sumuww` n’existe. 1 SMW = 100000000 unités. `gettxout` n’a pas de champ `spendable` et peut renvoyer une récompense immature. Une coinbase exige au moins 100 confirmations pour être dépensée au bloc suivant. Filtrez `listunspent` sur `spendable` ; le montant available de `getaddressbalance` exclut les fonds immatures ou engagés par des transactions en attente. Les nouvelles sorties du mempool ne sont pas confirmées. Vérifiez la pointe entre les pages et revalidez les entrées choisies.

1 SMW = 100 000 000 yugeon. Les frais automatiques proposent trois niveaux selon les observations locales, sans garantir le délai de confirmation. Vous pouvez saisir un taux en yugeon/vB. Vérifiez les frais définitifs et le total en SMW avant l’envoi. Une transaction refusée ne débite pas votre solde.

`1 yugeon = 0.00000001 SMW` · `1 SMW = 100000000 yugeon`

| API / wallet | yugeon / SMW |
|---|---|
| minimum relay | 1 yugeon/vB |
| automatic cap | 0.01 SMW |
| manual cap | 1 SMW |
| manual rate | 1–100000 yugeon/vB |

Les frais automatiques suivent le volume en attente, la capacité des blocs et la priorité des transactions, sans reprendre les frais passés. Si la file est peu chargée, le taux reste minimal. L’aperçu s’actualise ; la confirmation finale fixe les frais. Les observations concernent le nœud local connecté, pas tous les nœuds.

L’historique des remplacements observés par ce nœud est conservé après le redémarrage du portefeuille. Les transactions retirées ne modifient pas le solde.

L’historique de minage distingue l’émission nouvelle, les frais et la récompense totale de chaque bloc. Le montant reçu par votre portefeuille apparaît séparément. Une récompense partiellement réclamée ne permet pas d’attribuer les deux composantes. Le nœud fournit 28 méthodes RPC, dont l’estimation des frais, et valide et relaie les transactions signées.

## Recherche de transactions et de blocs

`getrawtransaction` recherche la chaîne active et le mempool, pas les seules branches orphelines. Les entrées désignent des sorties précédentes, pas une adresse d’expéditeur unique. `getblock` reçoit un `verbose` booléen ; un bloc inactif conservé a `active=false` et `confirmations=-1`. Ses transactions brutes restent accessibles par hash de bloc. `findspendingtransaction` ne cherche que les dépenses confirmées actives ; null ne prouve pas la disponibilité. Vérifiez `gettxout` avec `include_mempool=true`. Confirmations et état actif peuvent changer après réorganisation.

[API_CONTRACT.json](../../../API_CONTRACT.json)
