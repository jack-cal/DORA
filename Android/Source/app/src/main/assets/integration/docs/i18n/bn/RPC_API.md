# SUMUWW Android 0.6.95 · RPC ও HTTP API

SUMUWW Android 0.6.95 · নোড চেইনের তথ্য যাচাই, সংরক্ষণ, প্রচার ও খোঁজার সুবিধা দেয়।

API বিবরণ অ্যাপে থাকা নোডের মূল অংশ ব্যাখ্যা করে। Android অ্যাপে RPC সেটিংসের পর্দা নেই।

## RPC ও HTTP API

validateaddress চেকসাম ও নির্বাচিত নেটওয়ার্ক যাচাই করে। decoderawtransaction-এর decoded_only শুধু পাঠোদ্ধার বোঝায়, স্বাক্ষরের বৈধতা বা নিশ্চিতকরণ নয়। OP_RETURN বাইরের প্রোগ্রামের জন্য তথ্য রাখে. নোডে ফি জানা, পাঠানোর আগে পরীক্ষা, RBF প্রতিস্থাপনের অবস্থা এবং ব্লকের ক্রমে তথ্য পড়ার সুবিধা যোগ হয়েছে। অপেক্ষমাণ লেনদেন মুছবার আগে প্রতিস্থাপন যাচাই হয়। একাধিক স্বাক্ষর ও লক করা আউটপুট পৃথক সক্রিয়করণ পরীক্ষার জন্য তৈরি; সর্বজনীন নেটওয়ার্কে এখনও সক্রিয় নয়।

## পরিমাণ ও ব্যবহারযোগ্য আউটপুট

`_units` ক্ষুদ্রতম এককের পূর্ণসংখ্যা; `_smw` 8 দশমিকের string; `_dora` সামঞ্জস্যের বিকল্প নাম। `_sumuww` পরিমাণ ক্ষেত্র নেই। 1 SMW = 100000000 একক। `gettxout`-এ `spendable` নেই, অপরিণত coinbase আউটপুটও আসতে পারে। পরের ব্লকে খরচ করতে অন্তত 100 নিশ্চয়তা লাগে। `listunspent`-কে `spendable` দিয়ে ছাঁকুন; `getaddressbalance`-এর available অপরিণত ও অপেক্ষমাণ খরচে আটকানো অর্থ বাদ দেয়। নতুন mempool আউটপুট নিশ্চিত অর্থ নয়। পাতার মধ্যে শীর্ষ যাচাই করুন ও বাছাই ইনপুট আবার পরীক্ষা করুন।

1 SMW = 100,000,000 yugeon। স্থানীয় পর্যবেক্ষণের ভিত্তিতে স্বয়ংক্রিয় ফির তিনটি স্তর আছে; নিশ্চিতকরণের সময়ের নিশ্চয়তা নেই। yugeon/vB-তে হার নিজে দিতে পারেন। পাঠানোর আগে চূড়ান্ত ফি ও মোট SMW যাচাই করুন। প্রত্যাখ্যাত লেনদেনে ব্যালান্স কমে না।

`1 yugeon = 0.00000001 SMW` · `1 SMW = 100000000 yugeon`

| API / wallet | yugeon / SMW |
|---|---|
| minimum relay | 1 yugeon/vB |
| automatic cap | 0.01 SMW |
| manual cap | 1 SMW |
| manual rate | 1–100000 yugeon/vB |

স্বয়ংক্রিয় ফি অপেক্ষমাণ ডেটার পরিমাণ, ব্লকের ধারণক্ষমতা ও লেনদেনের অগ্রাধিকার বিবেচনা করে। আগের ব্লকের ফি ব্যবহার করা হয় না। সারি ছোট হলে সর্বনিম্ন হার বজায় থাকে। পূর্বরূপ হালনাগাদ হয়; চূড়ান্ত নিশ্চিতকরণে ফি স্থির হয়। পর্যবেক্ষণ সংযুক্ত স্থানীয় নোডের, সব নোডের নয়।

ওয়ালেট আবার চালু করলেও এই নোডে নথিভুক্ত লেনদেন প্রতিস্থাপনের ইতিহাস থাকে। সরানো লেনদেন ব্যালেন্সে প্রভাব ফেলে না।

মাইনিং ইতিহাসে প্রতিটি ব্লকের নতুন ইস্যু, লেনদেন ফি ও মোট পুরস্কার আলাদা দেখানো হয়। আপনার ওয়ালেটে পাওয়া অর্থ আলাদা দেখানো হয়। আংশিক দাবি হলে দুই অংশের বণ্টন অনুমান করা হয় না। নোড ফি অনুমানসহ 28টি RPC পদ্ধতি দেয় এবং স্বাক্ষরিত লেনদেন যাচাই ও প্রচার করে।

## লেনদেন ও ব্লক খোঁজা

`getrawtransaction` সক্রিয় চেইন ও mempool খোঁজে, শুধু বিচ্ছিন্ন শাখায় থাকা লেনদেন নয়। ইনপুট আগের আউটপুট নির্দেশ করে, একটিমাত্র প্রেরকের ঠিকানা নয়। `getblock`-এর `verbose` Boolean; সংরক্ষিত নিষ্ক্রিয় ব্লকে `active=false`, `confirmations=-1`। ব্লক hash দিয়ে কাঁচা লেনদেন পাওয়া যায়। `findspendingtransaction` শুধু সক্রিয় চেইনের নিশ্চিত খরচ খোঁজে; null ব্যবহারযোগ্যতার প্রমাণ নয়। `include_mempool=true` দিয়ে `gettxout` দেখুন। পুনর্গঠনে নিশ্চয়তা ও সক্রিয় অবস্থা বদলাতে পারে।

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
