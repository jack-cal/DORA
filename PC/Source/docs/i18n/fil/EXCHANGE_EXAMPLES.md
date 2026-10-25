# SUMUWW · Beripikasyon

SUMUWW PC 0.57.46 · Sinusuri, iniimbak, ipinapasa at ipinapakita ng node ang datos ng chain.

## Pormat ng lagda

Binubuo ng opsyonal na source SDK ang transaksiyon at sinusuri ang ibinigay na lagda nang walang susi o network. Hindi ito programang lumalagda o utos ng node. Sa format ng halimbawa lang ang limitasyong P2WPKH, hindi sa node. Magagamit pa rin ang personal na wallet.

## Beripikasyon

I-install ang dependencies at patakbuhin ang python examples/node_contract.py mula sa source. Pampublikong test key at pansamantalang regtest ang sumusubok sa pagpapasa, pagtanggi, kumpirmasyon, reorganisasyon at pag-iimbak. Walang totoong pondo, profile ng user o hardware signer na ginagamit.

```powershell
python examples/node_contract.py
python -m unittest tests.test_node_contract tests.test_rpc -v
```

[Dokumentasyon](README.html) · [Interface ng node](EXCHANGE_INTEGRATION.html) · [RPC at HTTP API](RPC_API.html) · [Pagpapatakbo ng node](NETWORK_RUNBOOK.html) · [Mga tala ng bersyon](RELEASE_NOTES.html)

[Detalyadong sanggunian sa Ingles](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
