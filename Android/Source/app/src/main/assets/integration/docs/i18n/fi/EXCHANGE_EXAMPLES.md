# SUMUWW Android 0.6.95 · Varmennus

SUMUWW Android 0.6.95 · Solmu tarkistaa, tallentaa, välittää ja tarjoaa ketjun tiedot.

API-määrittely kuvaa sisäänrakennettua solmuydintä. Android-sovelluksessa ei ole RPC-asetusnäkymää.

## RPC- ja HTTP-API

validateaddress tarkistaa tarkistussumman ja valitun verkon. decoderawtransaction palauttaa decoded_only, ei todistusta allekirjoituksen kelpoisuudesta tai vahvistuksesta. OP_RETURN säilyttää tietoa ulkoisille ohjelmille. Solmuun lisätään maksukyselyt, tarkistus ennen lähetystä, RBF-korvauksen tila ja tietojen luku lohkojärjestyksessä. Korvaava tapahtuma tarkistetaan ennen odottavien tapahtumien poistamista. Moniallekirjoitus ja lukitut ulostulot on toteutettu erillisiä aktivointitestejä varten; ne eivät vielä ole käytössä julkisessa verkossa.

## Tapahtumien ja lohkojen haku

`getrawtransaction` hakee aktiivisesta ketjusta ja mempoolista, ei vain hylätyistä haaroista. Syötteet viittaavat aiempiin tulosteisiin, eivät yksiselitteiseen lähettäjäosoitteeseen. `getblock` ottaa totuusarvon `verbose`; tallennetun epäaktiivisen lohkon arvot ovat `active=false`, `confirmations=-1`. Raakatapahtumat saa edelleen lohkotiivisteellä. `findspendingtransaction` hakee vain aktiivisen ketjun vahvistetut käytöt; null ei todista käytettävyyttä. Tarkista `gettxout` asetuksella `include_mempool=true`. Vahvistukset ja aktiivisuus voivat muuttua uudelleenjärjestelyssä.

[API_CONTRACT.json](../../../API_CONTRACT.json)
