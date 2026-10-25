# SUMUWW · Mga tala ng bersyon

SUMUWW PC 0.57.46 · Sinusuri, iniimbak, ipinapasa at ipinapakita ng node ang datos ng chain.

## Pormat ng lagda

Binubuo ng opsyonal na source SDK ang transaksiyon at sinusuri ang ibinigay na lagda nang walang susi o network. Hindi ito programang lumalagda o utos ng node. Sa format ng halimbawa lang ang limitasyong P2WPKH, hindi sa node. Magagamit pa rin ang personal na wallet.

## RPC at HTTP API

Sinusuri ng validateaddress ang checksum at napiling network. Ang decoded_only mula sa decoderawtransaction ay pagbasa lang ng datos, hindi patunay ng wastong lagda o kumpirmasyon. Nag-iimbak ang OP_RETURN ng datos para sa panlabas na programa. May dagdag na pagtatanong ng bayad, pagsusuri bago magpadala, katayuan ng pagpapalit sa RBF at datos ayon sa pagkakasunod ng mga block. Sinusuri muna ang kapalit bago alisin ang mga nakabinbing transaksiyon. Naipatupad ang maramihang lagda at naka-lock na output para sa hiwalay na pagsubok; hindi pa aktibo sa pampublikong network.

## Beripikasyon

I-install ang dependencies at patakbuhin ang python examples/node_contract.py mula sa source. Pampublikong test key at pansamantalang regtest ang sumusubok sa pagpapasa, pagtanggi, kumpirmasyon, reorganisasyon at pag-iimbak. Walang totoong pondo, profile ng user o hardware signer na ginagamit.

[Dokumentasyon](README.html) · [Interface ng node](EXCHANGE_INTEGRATION.html) · [RPC at HTTP API](RPC_API.html) · [Pagpapatakbo ng node](NETWORK_RUNBOOK.html) · [Beripikasyon](EXCHANGE_EXAMPLES.html)

[Detalyadong sanggunian sa Ingles](../../../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../../../API_CONTRACT.json) · [vectors.json](../../../../../examples/exchange/vectors.json)
