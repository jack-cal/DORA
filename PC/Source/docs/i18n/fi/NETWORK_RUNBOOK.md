# SUMUWW · Solmun käyttö

SUMUWW PC 0.57.46 · Solmu tarkistaa, tallentaa, välittää ja tarjoaa ketjun tiedot.

## Verkko ja osoitteet

Julkinen verkko on `sumuww`, sisäinen alias `dora`. Tarkista alla oleva genesis-tiiviste. Osoitteet käyttävät witness v0 P2WPKH:ta ja pakatun secp256k1-julkisen avaimen HASH160:tä. Memoa tai tagia ei vaadita. Hylkää väärän verkon osoitteet ja virheelliset tarkistussummat. Tallenna HD-vastaanotto-/vaihtorahahaara ja indeksi; älä oleta Bitcoinin johtamispolkua.

## Todennus ja rajat

Ota RPC erikseen käyttöön numeerisessa loopback-osoitteessa `127.0.0.1:18443` yksityisellä Bearer-tunnisteella. Lompakon avaamista tai etäallekirjoitusta ei tarjota. Käytä paikallista palvelua tai todennettua tunnelia; selaimen Origin/Referer-pyynnöt hylätään. JSON-RPC käyttää POST `/rpc`, olio-/taulukko-`params` ja `id`; ilmoitukset palauttavat HTTP 204. Rajat: runko 8004096 tavua, otsakkeet 8192, erä 16, samanaikaiset pyynnöt 16, määräaika 10 sekuntia; limit 1–1000, offset 0–1000000. Menetelmiä on 28 ja REST-reittejä 11.

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

[Dokumentaatio](README.html) · [Solmun rajapinta](EXCHANGE_INTEGRATION.html) · [RPC- ja HTTP-API](RPC_API.html) · [Julkaisutiedot](RELEASE_NOTES.html) · [Varmennus](EXCHANGE_EXAMPLES.html)

[Laaja englanninkielinen viite](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
