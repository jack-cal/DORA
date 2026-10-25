# SUMUWW · Vérification

SUMUWW PC 0.57.46 · Le nœud valide, conserve, relaie et expose les données de la chaîne.

## Format de signature

Le SDK source facultatif assemble les transactions et vérifie les signatures fournies, sans clé ni réseau. Ce n’est ni un outil de signature ni une commande du nœud. La restriction P2WPKH concerne le format de l’exemple, pas le nœud. Le portefeuille personnel existant reste disponible.

## Vérification

Exécutez python examples/node_contract.py depuis les sources après installation des dépendances. Des clés publiques de test et un regtest temporaire vérifient soumission, rejet, confirmations, réorganisation et conservation. Aucun fonds réel, profil personnel ou dispositif de signature matériel n’est utilisé.

```powershell
python examples/node_contract.py
python -m unittest tests.test_node_contract tests.test_rpc -v
```

[Documentation](README.html) · [Interface du nœud](EXCHANGE_INTEGRATION.html) · [API RPC et HTTP](RPC_API.html) · [Exploitation du nœud](NETWORK_RUNBOOK.html) · [Notes de version](RELEASE_NOTES.html)

[Référence détaillée en anglais](../../../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../../../API_CONTRACT.json) · [vectors.json](../../../../../examples/exchange/vectors.json)
