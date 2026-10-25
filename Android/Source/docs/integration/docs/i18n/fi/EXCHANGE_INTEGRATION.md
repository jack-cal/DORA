# SUMUWW Android 0.6.95 · Solmun rajapinta

SUMUWW Android 0.6.95 · Solmu tarkistaa, tallentaa, välittää ja tarjoaa ketjun tiedot.

API-määrittely kuvaa sisäänrakennettua solmuydintä. Android-sovelluksessa ei ole RPC-asetusnäkymää.

## Verkko ja osoitteet

Julkinen verkko on `sumuww`, sisäinen alias `dora`. Tarkista alla oleva genesis-tiiviste. Osoitteet käyttävät witness v0 P2WPKH:ta ja pakatun secp256k1-julkisen avaimen HASH160:tä. Memoa tai tagia ei vaadita. Hylkää väärän verkon osoitteet ja virheelliset tarkistussummat. Tallenna HD-vastaanotto-/vaihtorahahaara ja indeksi; älä oleta Bitcoinin johtamispolkua.

## RPC- ja HTTP-API

validateaddress tarkistaa tarkistussumman ja valitun verkon. decoderawtransaction palauttaa decoded_only, ei todistusta allekirjoituksen kelpoisuudesta tai vahvistuksesta. OP_RETURN säilyttää tietoa ulkoisille ohjelmille. Solmuun lisätään maksukyselyt, tarkistus ennen lähetystä, RBF-korvauksen tila ja tietojen luku lohkojärjestyksessä. Korvaava tapahtuma tarkistetaan ennen odottavien tapahtumien poistamista. Moniallekirjoitus ja lukitut ulostulot on toteutettu erillisiä aktivointitestejä varten; ne eivät vielä ole käytössä julkisessa verkossa.

## Summat ja käytettävissä olevat tulosteet

`_units` tarkoittaa kokonaisia pienimpiä yksiköitä; `_smw` 8 desimaalin merkkijonoa; `_dora` yhteensopivuusaliasta. `_sumuww`-summakenttää ei ole. 1 SMW = 100000000 yksikköä. `gettxout` ei sisällä `spendable`-kenttää ja voi palauttaa kypsymättömän coinbase-tulosteen. Seuraavassa lohkossa käyttämiseen tarvitaan vähintään 100 vahvistusta. Suodata `listunspent` kentällä `spendable`; `getaddressbalance`-vastauksen available sulkee pois kypsymättömät ja odottaviin tapahtumiin sidotut varat. Mempoolin uudet tulosteet eivät ole vahvistettuja. Tarkista kärki sivujen välillä ja validoi valitut syötteet uudelleen.

1 SMW = 100 000 000 yugeon. Automaattinen maksu tarjoaa kolme tasoa paikallisten havaintojen perusteella, mutta ei takaa vahvistusaikaa. Voit syöttää maksutason yksikössä yugeon/vB. Tarkista lopullinen maksu ja kokonaissumma SMW-yksikössä ennen lähettämistä. Hylätty tapahtuma ei vähennä saldoa.

`1 yugeon = 0.00000001 SMW` · `1 SMW = 100000000 yugeon`

| API / wallet | yugeon / SMW |
|---|---|
| minimum relay | 1 yugeon/vB |
| automatic cap | 0.01 SMW |
| manual cap | 1 SMW |
| manual rate | 1–100000 yugeon/vB |

Automaattinen maksu perustuu jonossa olevaan datamäärään, lohkokapasiteettiin ja siirtojen etusijaan. Aiempien lohkojen maksuja ei käytetä. Lyhyessä jonossa käytetään vähimmäishintaa. Esikatselu päivittyy; lopullinen vahvistus lukitsee maksun. Havainnot koskevat yhdistettyä paikallista solmua, eivät kaikkia solmuja.

Tämän solmun kirjaama korvaushistoria säilyy lompakon uudelleenkäynnistyksen jälkeen. Poistetut tapahtumat eivät vaikuta saldoon.

Louhintahistoria erittelee kunkin lohkon uuden liikkeeseenlaskun, siirtomaksut ja kokonaispalkkion. Lompakkosi vastaanottama summa näkyy erikseen. Osittain lunastetun palkkion jakautumista ei oleteta. Solmu tarjoaa 28 RPC-menetelmää, mukaan lukien maksuarvion, sekä tarkistaa ja välittää allekirjoitetut tapahtumat.

## Tapahtumien ja lohkojen haku

`getrawtransaction` hakee aktiivisesta ketjusta ja mempoolista, ei vain hylätyistä haaroista. Syötteet viittaavat aiempiin tulosteisiin, eivät yksiselitteiseen lähettäjäosoitteeseen. `getblock` ottaa totuusarvon `verbose`; tallennetun epäaktiivisen lohkon arvot ovat `active=false`, `confirmations=-1`. Raakatapahtumat saa edelleen lohkotiivisteellä. `findspendingtransaction` hakee vain aktiivisen ketjun vahvistetut käytöt; null ei todista käytettävyyttä. Tarkista `gettxout` asetuksella `include_mempool=true`. Vahvistukset ja aktiivisuus voivat muuttua uudelleenjärjestelyssä.

[API_CONTRACT.json](../../../API_CONTRACT.json)
