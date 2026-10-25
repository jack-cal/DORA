# SUMUWW · 0.57.45 / 0.6.94

Solmuun lisätään maksukyselyt, tarkistus ennen lähetystä, RBF-korvauksen tila ja tietojen luku lohkojärjestyksessä. Korvaava tapahtuma tarkistetaan ennen odottavien tapahtumien poistamista. Moniallekirjoitus ja lukitut ulostulot on toteutettu erillisiä aktivointitestejä varten; ne eivät vielä ole käytössä julkisessa verkossa.

1 SMW = 100 000 000 yugeon. Automaattinen maksu tarjoaa kolme tasoa paikallisten havaintojen perusteella, mutta ei takaa vahvistusaikaa. Voit syöttää maksutason yksikössä yugeon/vB. Tarkista lopullinen maksu ja kokonaissumma SMW-yksikössä ennen lähettämistä. Hylätty tapahtuma ei vähennä saldoa.

`1 yugeon = 0.00000001 SMW`

`1 SMW = 100,000,000 yugeon`

Automaattinen maksu perustuu jonossa olevaan datamäärään, lohkokapasiteettiin ja siirtojen etusijaan. Aiempien lohkojen maksuja ei käytetä. Lyhyessä jonossa käytetään vähimmäishintaa. Esikatselu päivittyy; lopullinen vahvistus lukitsee maksun. Havainnot koskevat yhdistettyä paikallista solmua, eivät kaikkia solmuja.

Tämän solmun kirjaama korvaushistoria säilyy lompakon uudelleenkäynnistyksen jälkeen. Poistetut tapahtumat eivät vaikuta saldoon.

Selain näyttää paljastetut moniallekirjoituksen ja tulosteiden lukituksen ehdot. Aktivointia julkisessa verkossa ei ole vielä ajoitettu.
