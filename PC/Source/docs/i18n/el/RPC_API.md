# SUMUWW · RPC και HTTP API

SUMUWW PC 0.57.46 · Ο κόμβος ελέγχει, αποθηκεύει, μεταδίδει και παρέχει δεδομένα της αλυσίδας.

## RPC και HTTP API

Το validateaddress ελέγχει το άθροισμα ελέγχου και το επιλεγμένο δίκτυο. Το decoded_only του decoderawtransaction σημαίνει μόνο ανάλυση, όχι έγκυρη υπογραφή ή επιβεβαίωση. Το OP_RETURN διατηρεί δεδομένα για εξωτερικά προγράμματα. Ο κόμβος προσθέτει ερωτήματα χρεώσεων, έλεγχο πριν την αποστολή, κατάσταση αντικατάστασης RBF και δεδομένα με σειρά μπλοκ. Η αντικατάσταση ελέγχεται πριν αφαιρεθούν εκκρεμείς συναλλαγές. Πολλαπλές υπογραφές και κλειδωμένες έξοδοι έχουν υλοποιηθεί για απομονωμένες δοκιμές ενεργοποίησης· δεν είναι ακόμη ενεργές στο δημόσιο δίκτυο.

## Έλεγχος πρόσβασης και όρια

Ενεργοποιήστε ρητά RPC στο αριθμητικό loopback `127.0.0.1:18443` με ιδιωτικό Bearer token. Δεν παρέχεται ξεκλείδωμα πορτοφολιού ή απομακρυσμένη υπογραφή. Χρησιμοποιήστε τοπική υπηρεσία ή πιστοποιημένο tunnel· Origin/Referer από browser απορρίπτονται. Το JSON-RPC χρησιμοποιεί POST `/rpc`, αντικείμενο/πίνακα `params` και `id`· οι ειδοποιήσεις επιστρέφουν HTTP 204. Όρια: σώμα 8004096 byte, κεφαλίδες 8192, παρτίδα 16, ταυτόχρονα αιτήματα 16, προθεσμία 10 δευτερόλεπτα· limit 1–1000, offset 0–1000000. Υπάρχουν 28 μέθοδοι και 11 διαδρομές REST.

## Ποσά και διαθέσιμες έξοδοι

`_units`: ακέραιες ελάχιστες μονάδες· `_smw`: κείμενο 8 δεκαδικών· `_dora`: ψευδώνυμο συμβατότητας. Δεν υπάρχει πεδίο ποσού `_sumuww`. 1 SMW = 100000000 μονάδες. Το `gettxout` δεν έχει `spendable` και μπορεί να δώσει ανώριμες εξόδους coinbase. Απαιτούνται τουλάχιστον 100 επιβεβαιώσεις για δαπάνη στο επόμενο μπλοκ. Φιλτράρετε `listunspent` με `spendable`· το available του `getaddressbalance` εξαιρεί ανώριμα και δεσμευμένα σε εκκρεμείς δαπάνες ποσά. Νέες έξοδοι mempool δεν είναι επιβεβαιωμένες. Ελέγξτε κορυφή μεταξύ σελίδων και επαληθεύστε ξανά τις επιλεγμένες εισόδους.

1 SMW = 100.000.000 yugeon. Οι αυτόματες χρεώσεις προσφέρουν τρία επίπεδα βάσει τοπικών παρατηρήσεων, χωρίς εγγύηση χρόνου επιβεβαίωσης. Μπορείτε να εισαγάγετε τιμή σε yugeon/vB. Πριν στείλετε, ελέγξτε την τελική χρέωση και το σύνολο σε SMW. Μια απορριφθείσα συναλλαγή δεν μειώνει το υπόλοιπο.

`1 yugeon = 0.00000001 SMW` · `1 SMW = 100000000 yugeon`

| API / wallet | yugeon / SMW |
|---|---|
| minimum relay | 1 yugeon/vB |
| automatic cap | 0.01 SMW |
| manual cap | 1 SMW |
| manual rate | 1–100000 yugeon/vB |

Η αυτόματη χρέωση λαμβάνει υπόψη τον όγκο αναμονής, τη χωρητικότητα των μπλοκ και την προτεραιότητα των συναλλαγών. Δεν χρησιμοποιεί χρεώσεις παλαιότερων μπλοκ. Με μικρή ουρά διατηρείται η ελάχιστη τιμή. Η προεπισκόπηση ανανεώνεται· η τελική επιβεβαίωση οριστικοποιεί τη χρέωση. Οι παρατηρήσεις αφορούν τον συνδεδεμένο τοπικό κόμβο, όχι όλους τους κόμβους.

Το ιστορικό αντικαταστάσεων που κατέγραψε αυτός ο κόμβος διατηρείται μετά την επανεκκίνηση του πορτοφολιού. Οι αφαιρεθείσες συναλλαγές δεν επηρεάζουν το υπόλοιπο.

Το ιστορικό εξόρυξης διαχωρίζει τη νέα έκδοση, τα τέλη και τη συνολική ανταμοιβή κάθε μπλοκ. Το ποσό που έλαβε το πορτοφόλι σας εμφανίζεται χωριστά. Σε μερική διεκδίκηση δεν υποτίθεται κατανομή μεταξύ των δύο μερών. Ο κόμβος παρέχει 28 μεθόδους RPC, μαζί με εκτίμηση τελών, και ελέγχει και μεταδίδει υπογεγραμμένες συναλλαγές.

## Αναζήτηση συναλλαγών και μπλοκ

Το `getrawtransaction` ψάχνει ενεργή αλυσίδα και mempool, όχι συναλλαγές μόνο σε ορφανούς κλάδους. Είσοδοι δείχνουν προηγούμενες εξόδους, όχι μοναδικό αποστολέα. Το `getblock` παίρνει Boolean `verbose`· αποθηκευμένα ανενεργά μπλοκ έχουν `active=false`, `confirmations=-1`. Οι ακατέργαστες συναλλαγές παραμένουν διαθέσιμες μέσω hash μπλοκ. Το `findspendingtransaction` ψάχνει μόνο επιβεβαιωμένες ενεργές δαπάνες· null δεν αποδεικνύει διαθεσιμότητα. Ελέγξτε `gettxout` με `include_mempool=true`. Επιβεβαιώσεις και ενεργή κατάσταση αλλάζουν με αναδιοργάνωση.

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

[Τεκμηρίωση](README.html) · [Διεπαφή κόμβου](EXCHANGE_INTEGRATION.html) · [Λειτουργία κόμβου](NETWORK_RUNBOOK.html) · [Σημειώσεις έκδοσης](RELEASE_NOTES.html) · [Επαλήθευση](EXCHANGE_EXAMPLES.html)

[Αναλυτική αγγλική αναφορά](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
