# SUMUWW Android 0.6.95 · RPC மற்றும் HTTP API

SUMUWW Android 0.6.95 · முனை சங்கிலித் தரவைச் சரிபார்த்து, சேமித்து, பரப்பி, தேடலுக்கு வழங்குகிறது.

API விவரக்குறிப்பு உள்ளமைந்த முனையின் மையத்தை விளக்குகிறது. Android செயலியில் RPC அமைப்புத் திரை இல்லை.

## RPC மற்றும் HTTP API

validateaddress சரிபார்ப்புத் தொகையையும் தேர்ந்தெடுத்த பிணையத்தையும் சோதிக்கிறது. decoderawtransaction தரும் decoded_only தரவைப் படித்ததை மட்டுமே குறிக்கும். கட்டண வினவல், அனுப்பும் முன் சரிபார்ப்பு, RBF மாற்று நிலை மற்றும் தொகுதி வரிசையில் தரவு வாசிப்பு ஆகியவை முனையில் சேர்க்கப்பட்டுள்ளன. நிலுவைப் பரிவர்த்தனைகளை அகற்றும் முன் மாற்றுப் பரிவர்த்தனை சரிபார்க்கப்படும். பல கையொப்பங்களும் பூட்டப்பட்ட வெளியீடுகளும் தனிச் செயல்படுத்தல் சோதனைக்காக உருவாக்கப்பட்டுள்ளன; பொது வலையில் இன்னும் செயல்படவில்லை.

## தொகைகளும் கிடைக்கும் வெளியீடுகளும்

`_units` மிகச்சிறிய அலகின் முழு எண்; `_smw` 8 தசம இடங்களுள்ள உரை; `_dora` பொருந்துதலுக்கான மாற்றுப் பெயர். `_sumuww` தொகைப் புலம் இல்லை. 1 SMW = 100000000 அலகுகள். `gettxout`-ல் `spendable` இல்லை; முதிராத coinbase வெளியீடும் வரலாம். அடுத்த தொகுதியில் செலவிட குறைந்தது 100 உறுதிகள் தேவை. `listunspent`-ஐ `spendable` கொண்டு வடிகட்டவும்; `getaddressbalance`-இன் available முதிராத மற்றும் நிலுவைச் செலவில் உள்ள நிதியை விலக்கும். புதிய mempool வெளியீடுகள் உறுதியான நிதியல்ல. பக்கங்களுக்கு இடையில் முனையைச் சரிபார்த்து தேர்ந்த உள்ளீடுகளை மீண்டும் பரிசோதிக்கவும்.

1 SMW = 100,000,000 yugeon. உள்ளூர் கண்காணிப்பின் அடிப்படையில் தானியங்கிக் கட்டணம் மூன்று நிலைகளை வழங்குகிறது; உறுதிப்படுத்தும் நேரத்திற்கு உத்தரவாதம் இல்லை. yugeon/vB விகிதத்தை நீங்களே உள்ளிடலாம். அனுப்பும் முன் இறுதிக் கட்டணத்தையும் மொத்தத்தையும் SMW-இல் சரிபார்க்கவும். நிராகரிக்கப்பட்ட பரிவர்த்தனை இருப்பைக் குறைக்காது.

`1 yugeon = 0.00000001 SMW` · `1 SMW = 100000000 yugeon`

| API / wallet | yugeon / SMW |
|---|---|
| minimum relay | 1 yugeon/vB |
| automatic cap | 0.01 SMW |
| manual cap | 1 SMW |
| manual rate | 1–100000 yugeon/vB |

தானியங்கிக் கட்டணம் நிலுவைத் தரவின் அளவு, தொகுதியின் கொள்ளளவு, பரிவர்த்தனை முன்னுரிமை ஆகியவற்றைக் கணக்கில் கொள்கிறது. பழைய தொகுதிகளின் கட்டணங்கள் பயன்படுத்தப்படுவதில்லை. வரிசை குறைவாக இருந்தால் குறைந்தபட்ச விகிதம் நீடிக்கும். முன்னோட்டம் புதுப்பிக்கப்படும்; இறுதி உறுதிப்படுத்தலின்போது கட்டணம் நிலைபெறும். கண்காணிப்பு இணைக்கப்பட்ட உள்ளூர் முனைக்குரியது; எல்லா முனைகளுக்குமானது அல்ல.

பணப்பையை மீண்டும் தொடங்கிய பின்னரும் இந்த முனை பதிவு செய்த பரிவர்த்தனை மாற்ற வரலாறு இருக்கும். நீக்கப்பட்ட பரிவர்த்தனைகள் இருப்பைப் பாதிக்காது.

சுரங்க வரலாற்றில் ஒவ்வொரு தொகுதியின் புதிய வெளியீடு, பரிவர்த்தனைக் கட்டணம், மொத்த வெகுமதி தனித்தனியாகக் காட்டப்படும். உங்கள் பணப்பை பெற்ற தொகை தனியாகக் காட்டப்படும். ஒரு பகுதி மட்டுமே பெறப்பட்டால் இரு கூறுகளின் பங்குகள் ஊகிக்கப்படாது. கட்டண மதிப்பீடு உட்பட 28 RPC முறைகளை முனை வழங்குகிறது; கையொப்பமிட்ட பரிவர்த்தனைகளைச் சரிபார்த்து அனுப்புகிறது.

## பரிவர்த்தனை மற்றும் தொகுதி தேடல்

`getrawtransaction` செயலிலுள்ள சங்கிலி மற்றும் mempool-ஐத் தேடும்; பிரிந்த கிளையில் மட்டுமே உள்ள பரிவர்த்தனையை அல்ல. உள்ளீடுகள் முந்தைய வெளியீடுகளைக் குறிக்கும், ஒரே அனுப்புநர் முகவரியை அல்ல. `getblock`-இன் `verbose` Boolean; சேமித்த செயலற்ற தொகுதிகளில் `active=false`, `confirmations=-1`. தொகுதி hash மூலம் மூலப் பரிவர்த்தனைகள் கிடைக்கும். `findspendingtransaction` செயலில் உறுதியான செலவுகளை மட்டுமே தேடும்; null கிடைப்பதற்கான சான்றல்ல. `include_mempool=true` உடன் `gettxout` பார்க்கவும். மறுசீரமைப்பில் உறுதிகளும் செயல்நிலையும் மாறலாம்.

| method | params |
|---|---|
| `getblockchaininfo` | `{} / []` |
| `gethtlcinfo` | `{} / []` |
| `getspendinginfo` | `{} / []` |
| `getdatarecords` | `blockhash, offset=0, limit=100` |
| `decodescript` | `hex` |
| `gettxout` | `txid, index, include_mempool=true` |
| `findspendingtransaction` | `txid, index, start_height=0` |
| `getnetworkinfo` | `{} / []` |
| `getblockcount` | `{} / []` |
| `getbestblockhash` | `{} / []` |
| `getblockhash` | `height` |
| `getblock` | `hash, verbose=true` |
| `getrawmempool` | `{} / []` |
| `getmempoolinfo` | `{} / []` |
| `getmempoolpolicy` | `{} / []` |
| `estimatefee` | `vsize=140, mode=normal` |
| `testmempoolaccept` | `hex` |
| `getmempoolentry` | `txid` |
| `gettransactionstatus` | `txid` |
| `getrawtransaction` | `txid, verbose=true` |
| `decoderawtransaction` | `hex` |
| `validateaddress` | `address` |
| `listunspent` | `address, limit=100, offset=0` |
| `getaddressbalance` | `address` |
| `sendrawtransaction` | `hex` |
| `submitblock` | `hex` |
| `getblocktemplate` | `address` |
| `help` | `{} / []` |

| HTTP | URI | JSON |
|---|---|---|
| `GET` | `/api/v1/info` | `—` |
| `GET` | `/api/v1/network` | `—` |
| `GET` | `/api/v1/mempool` | `—` |
| `GET` | `/api/v1/mempool/info` | `—` |
| `GET` | `/api/v1/blocks/{height-or-hash}` | `—` |
| `GET` | `/api/v1/transactions/{txid}` | `—` |
| `GET` | `/api/v1/addresses/{address}/balance` | `—` |
| `GET` | `/api/v1/addresses/{address}/utxos?limit=100&offset=0` | `—` |
| `POST` | `/api/v1/transactions` | `{"hex":"..."}` |
| `POST` | `/api/v1/blocks` | `{"hex":"..."}` |
| `POST` | `/api/v1/mining/template` | `{"address":"..."}` |

[API_CONTRACT.json](../../../API_CONTRACT.json)
