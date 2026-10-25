# SUMUWW · Exploitation du nœud

SUMUWW PC 0.57.46 · Le nœud valide, conserve, relaie et expose les données de la chaîne.

## Réseau et adresses

Le réseau public est `sumuww`, avec l’alias interne `dora`. Vérifiez le hash de genèse ci-dessous. Les adresses natives utilisent P2WPKH witness v0 et HASH160 d’une clé publique secp256k1 compressée. Aucun mémo ni tag n’est obligatoire. Rejetez les adresses d’un autre réseau et les sommes de contrôle invalides. Notez la branche réception/monnaie et l’index HD ; ne supposez pas le chemin de dérivation de Bitcoin.

## Authentification et limites

Activez explicitement RPC sur la boucle locale numérique `127.0.0.1:18443`, avec son jeton Bearer privé. Aucune fonction de déverrouillage ou de signature distante n’est exposée. Utilisez un service local ou un tunnel authentifié ; les requêtes de navigateur Origin/Referer sont refusées. JSON-RPC utilise POST `/rpc`, `params` objet/tableau et `id` ; les notifications renvoient HTTP 204. Limites : corps 8004096 octets, en-têtes 8192, lots 16, requêtes simultanées 16, délai 10 secondes ; pagination limit 1–1000, offset 0–1000000. Il existe 28 méthodes et 11 routes REST.

## Recherche de transactions et de blocs

`getrawtransaction` recherche la chaîne active et le mempool, pas les seules branches orphelines. Les entrées désignent des sorties précédentes, pas une adresse d’expéditeur unique. `getblock` reçoit un `verbose` booléen ; un bloc inactif conservé a `active=false` et `confirmations=-1`. Ses transactions brutes restent accessibles par hash de bloc. `findspendingtransaction` ne cherche que les dépenses confirmées actives ; null ne prouve pas la disponibilité. Vérifiez `gettxout` avec `include_mempool=true`. Confirmations et état actif peuvent changer après réorganisation.

## Vérification

Exécutez python examples/node_contract.py depuis les sources après installation des dépendances. Des clés publiques de test et un regtest temporaire vérifient soumission, rejet, confirmations, réorganisation et conservation. Aucun fonds réel, profil personnel ou dispositif de signature matériel n’est utilisé.

```text
network: sumuww (dora)
genesis: 00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97
HRP: sumuww
P2P magic: d052470c
1 SMW = 100000000 yugeon
```

[Documentation](README.html) · [Interface du nœud](EXCHANGE_INTEGRATION.html) · [API RPC et HTTP](RPC_API.html) · [Notes de version](RELEASE_NOTES.html) · [Vérification](EXCHANGE_EXAMPLES.html)

[Référence détaillée en anglais](../../../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../../../API_CONTRACT.json) · [vectors.json](../../../../../examples/exchange/vectors.json)
