# SUMUWW · Documentation

SUMUWW PC 0.57.46 · Le nœud valide, conserve, relaie et expose les données de la chaîne.

## Format de signature

Le SDK source facultatif assemble les transactions et vérifie les signatures fournies, sans clé ni réseau. Ce n’est ni un outil de signature ni une commande du nœud. La restriction P2WPKH concerne le format de l’exemple, pas le nœud. Le portefeuille personnel existant reste disponible.

## API RPC et HTTP

validateaddress vérifie la somme de contrôle et le réseau choisi. decoderawtransaction renvoie decoded_only, sans attester la signature ni la confirmation. Les sorties OP_RETURN conservent les données destinées aux programmes externes . Le nœud ajoute la consultation des frais, la vérification avant envoi, le suivi des remplacements RBF et la lecture ordonnée des données de bloc. La validation précède toute suppression de transaction en attente. Les signatures multiples et les sorties verrouillées sont implémentées pour des essais isolés ; elles ne sont pas encore activées sur le réseau public.

## Vérification

Exécutez python examples/node_contract.py depuis les sources après installation des dépendances. Des clés publiques de test et un regtest temporaire vérifient soumission, rejet, confirmations, réorganisation et conservation. Aucun fonds réel, profil personnel ou dispositif de signature matériel n’est utilisé.

```text
network: sumuww (dora)
genesis: 00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97
HRP: sumuww
P2P magic: d052470c
1 SMW = 100000000 yugeon
```

[Interface du nœud](EXCHANGE_INTEGRATION.html) · [API RPC et HTTP](RPC_API.html) · [Exploitation du nœud](NETWORK_RUNBOOK.html) · [Notes de version](RELEASE_NOTES.html) · [Vérification](EXCHANGE_EXAMPLES.html)

[Référence détaillée en anglais](../../../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../../../API_CONTRACT.json) · [vectors.json](../../../../../examples/exchange/vectors.json)
