# SUMUWW · 0.57.45 / 0.6.94

Noden tilføjer gebyrforespørgsler, kontrol før afsendelse, status for RBF-erstatning og data i blokrækkefølge. Erstatningen valideres, før ventende transaktioner fjernes. Flere signaturer og låste outputs er implementeret til isolerede aktiveringstests; de er endnu ikke aktive på det offentlige netværk.

1 SMW = 100.000.000 yugeon. Automatiske gebyrer tilbyder tre niveauer ud fra lokale observationer uden at garantere bekræftelsestiden. Du kan indtaste en sats i yugeon/vB. Kontrollér det endelige gebyr og totalen i SMW før afsendelse. En afvist transaktion reducerer ikke saldoen.

`1 yugeon = 0.00000001 SMW`

`1 SMW = 100,000,000 yugeon`

Automatiske gebyrer følger den ventende datamængde, blokkapaciteten og transaktionernes prioritet. Gebyrer fra tidligere blokke bruges ikke. Ved kort kø gælder minimumssatsen. Forhåndsvisningen opdateres; den endelige bekræftelse fastlægger gebyret. Oplysningerne dækker den tilsluttede lokale node, ikke alle noder.

Udskiftninger registreret af denne node bevares i historikken efter genstart af tegnebogen. Fjernede transaktioner påvirker ikke saldoen.

Explorer viser afslørede betingelser for flere underskrifter og låste output. Aktivering på det offentlige netværk er endnu ikke planlagt.
