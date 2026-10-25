# SUMUWW Android 0.6.95 · Notes de version

SUMUWW Android 0.6.95 · Le nœud valide, conserve, relaie et expose les données de la chaîne.

La spécification API décrit le cœur du nœud intégré. L’application Android n’a pas d’écran de configuration RPC.

## API RPC et HTTP

validateaddress vérifie la somme de contrôle et le réseau choisi. decoderawtransaction renvoie decoded_only, sans attester la signature ni la confirmation. Les sorties OP_RETURN conservent les données destinées aux programmes externes . Le nœud ajoute la consultation des frais, la vérification avant envoi, le suivi des remplacements RBF et la lecture ordonnée des données de bloc. La validation précède toute suppression de transaction en attente. Les signatures multiples et les sorties verrouillées sont implémentées pour des essais isolés ; elles ne sont pas encore activées sur le réseau public.

[API_CONTRACT.json](../../../API_CONTRACT.json)
