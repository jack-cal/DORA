# SUMUWW · 0.57.45 / 0.6.94

Le nœud ajoute la consultation des frais, la vérification avant envoi, le suivi des remplacements RBF et la lecture ordonnée des données de bloc. La validation précède toute suppression de transaction en attente. Les signatures multiples et les sorties verrouillées sont implémentées pour des essais isolés ; elles ne sont pas encore activées sur le réseau public.

1 SMW = 100 000 000 yugeon. Les frais automatiques proposent trois niveaux selon les observations locales, sans garantir le délai de confirmation. Vous pouvez saisir un taux en yugeon/vB. Vérifiez les frais définitifs et le total en SMW avant l’envoi. Une transaction refusée ne débite pas votre solde.

`1 yugeon = 0.00000001 SMW`

`1 SMW = 100,000,000 yugeon`

Les frais automatiques suivent le volume en attente, la capacité des blocs et la priorité des transactions, sans reprendre les frais passés. Si la file est peu chargée, le taux reste minimal. L’aperçu s’actualise ; la confirmation finale fixe les frais. Les observations concernent le nœud local connecté, pas tous les nœuds.

L’historique des remplacements observés par ce nœud est conservé après le redémarrage du portefeuille. Les transactions retirées ne modifient pas le solde.

L’explorateur affiche les conditions révélées de multisignature et de verrouillage des sorties. L’activation sur le réseau public n’est pas programmée.
