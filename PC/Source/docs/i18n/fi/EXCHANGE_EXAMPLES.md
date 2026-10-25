# SUMUWW · Varmennus

SUMUWW PC 0.57.46 · Solmu tarkistaa, tallentaa, välittää ja tarjoaa ketjun tiedot.

## Allekirjoitusmuoto

Valinnainen lähdekoodin SDK kokoaa transaktiot ja tarkistaa toimitetut allekirjoitukset ilman avaimia tai verkkoa. Se ei ole allekirjoitusohjelma eikä solmun komento. P2WPKH-rajoitus koskee esimerkin muotoa, ei solmua. Henkilökohtainen lompakko säilyy käytössä.

## Varmennus

Asenna riippuvuudet ja suorita lähdekoodista python examples/node_contract.py. Julkiset testiavaimet ja tilapäinen regtest testaavat lähetyksen, hylkäyksen, vahvistukset, uudelleenjärjestelyn ja tietojen säilymisen. Oikeita varoja, käyttäjäprofiileja tai laitteistoallekirjoittajia ei käytetä.

```powershell
python examples/node_contract.py
python -m unittest tests.test_node_contract tests.test_rpc -v
```

[Dokumentaatio](README.html) · [Solmun rajapinta](EXCHANGE_INTEGRATION.html) · [RPC- ja HTTP-API](RPC_API.html) · [Solmun käyttö](NETWORK_RUNBOOK.html) · [Julkaisutiedot](RELEASE_NOTES.html)

[Laaja englanninkielinen viite](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
