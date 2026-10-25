# SUMUWW · Solmun rajapinta

SUMUWW PC 0.57.46 · Solmu tarkistaa, tallentaa, välittää ja tarjoaa ketjun tiedot.

## Verkko ja osoitteet

Julkinen verkko on `sumuww`, sisäinen alias `dora`. Tarkista alla oleva genesis-tiiviste. Osoitteet käyttävät witness v0 P2WPKH:ta ja pakatun secp256k1-julkisen avaimen HASH160:tä. Memoa tai tagia ei vaadita. Hylkää väärän verkon osoitteet ja virheelliset tarkistussummat. Tallenna HD-vastaanotto-/vaihtorahahaara ja indeksi; älä oleta Bitcoinin johtamispolkua.

## Allekirjoitusmuoto

Valinnainen lähdekoodin SDK kokoaa transaktiot ja tarkistaa toimitetut allekirjoitukset ilman avaimia tai verkkoa. Se ei ole allekirjoitusohjelma eikä solmun komento. P2WPKH-rajoitus koskee esimerkin muotoa, ei solmua. Henkilökohtainen lompakko säilyy käytössä.

## RPC- ja HTTP-API

validateaddress tarkistaa tarkistussumman ja valitun verkon. decoderawtransaction palauttaa decoded_only, ei todistusta allekirjoituksen kelpoisuudesta tai vahvistuksesta. OP_RETURN säilyttää tietoa ulkoisille ohjelmille. Solmuun lisätään maksukyselyt, tarkistus ennen lähetystä, RBF-korvauksen tila ja tietojen luku lohkojärjestyksessä. Korvaava tapahtuma tarkistetaan ennen odottavien tapahtumien poistamista. Moniallekirjoitus ja lukitut ulostulot on toteutettu erillisiä aktivointitestejä varten; ne eivät vielä ole käytössä julkisessa verkossa.

## Todennus ja rajat

Ota RPC erikseen käyttöön numeerisessa loopback-osoitteessa `127.0.0.1:18443` yksityisellä Bearer-tunnisteella. Lompakon avaamista tai etäallekirjoitusta ei tarjota. Käytä paikallista palvelua tai todennettua tunnelia; selaimen Origin/Referer-pyynnöt hylätään. JSON-RPC käyttää POST `/rpc`, olio-/taulukko-`params` ja `id`; ilmoitukset palauttavat HTTP 204. Rajat: runko 8004096 tavua, otsakkeet 8192, erä 16, samanaikaiset pyynnöt 16, määräaika 10 sekuntia; limit 1–1000, offset 0–1000000. Menetelmiä on 28 ja REST-reittejä 11.

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

## Varmennus

Asenna riippuvuudet ja suorita lähdekoodista python examples/node_contract.py. Julkiset testiavaimet ja tilapäinen regtest testaavat lähetyksen, hylkäyksen, vahvistukset, uudelleenjärjestelyn ja tietojen säilymisen. Oikeita varoja, käyttäjäprofiileja tai laitteistoallekirjoittajia ei käytetä.

```text
network: sumuww (dora)
genesis: 00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97
HRP: sumuww
P2P magic: d052470c
1 SMW = 100000000 yugeon
```

[Dokumentaatio](README.html) · [RPC- ja HTTP-API](RPC_API.html) · [Solmun käyttö](NETWORK_RUNBOOK.html) · [Julkaisutiedot](RELEASE_NOTES.html) · [Varmennus](EXCHANGE_EXAMPLES.html)

[Laaja englanninkielinen viite](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
