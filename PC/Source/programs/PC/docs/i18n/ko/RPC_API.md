# SUMUWW · RPC·HTTP API

SUMUWW PC 0.57.46 · 노드는 체인 데이터를 검증·저장·전파·조회합니다.

## RPC·HTTP API

validateaddress는 체크섬과 선택한 네트워크를 검사합니다. decoderawtransaction의 decoded_only는 내용 해석만 뜻하며 서명 검증이나 확정을 뜻하지 않습니다. 기존 OP_RETURN 출력은 외부 프로그램용 데이터를 보존합니다. 노드에 수수료 조회, 전파 전 검증, RBF 교체 상태와 블록 순서에 따른 데이터 기록 조회를 추가했습니다. 교체 거래를 검증한 뒤에만 기존 대기 거래를 제거합니다. 다중 서명과 잠금 출력은 별도 활성화 시험용으로 구현했으며, 운영망에서는 아직 활성화되지 않았습니다.

## 인증과 제한

RPC를 명시적으로 켜고 숫자 루프백 `127.0.0.1:18443` 및 비공개 Bearer 토큰을 사용합니다. 지갑 잠금 해제나 원격 서명 기능은 노출하지 않습니다. 같은 PC의 서비스나 인증된 터널로 연결하세요. 브라우저의 Origin/Referer 요청은 거부됩니다. JSON-RPC는 POST `/rpc`, 객체·배열 `params`, `id`를 사용하고 알림 요청에는 HTTP 204를 반환합니다. 한도는 본문 8004096바이트, 헤더 8192바이트, 묶음 16개, 동시 요청 16개, 제한 시간 10초입니다. 페이지 limit은 1–1000, offset은 0–1000000이며 메서드 28개와 REST 경로 11개가 있습니다.

## 금액과 사용 가능한 출력

`_units`는 최소 단위의 정수, `_smw`는 소수점 8자리 문자열, `_dora`는 호환용 별칭입니다. `_sumuww` 금액 필드는 없습니다. 1 SMW는 100000000단위입니다. `gettxout`에는 `spendable` 필드가 없고 미성숙 채굴 보상도 반환할 수 있습니다. 다음 블록에서 보상을 쓰려면 확인이 100회 이상이어야 합니다. `listunspent`는 `spendable`로 걸러야 하며 `getaddressbalance`의 available 금액은 미성숙·대기 거래에서 사용 중인 자금을 제외합니다. 메모리풀의 새 출력은 확정 잔고가 아닙니다. 여러 페이지를 읽을 때 최신 블록이 바뀌지 않았는지 확인하고 선택한 입력을 다시 검증하세요.

1 SMW = 100,000,000 yugeon입니다. 자동 수수료는 로컬 관측값을 바탕으로 느림·보통·빠름을 제안하며, 확정 시간을 보장하지 않습니다. yugeon/vB 단위로 수수료율을 직접 입력할 수도 있습니다. 전송 전에 최종 수수료와 총액을 SMW로 확인하세요. 거부된 거래는 잔액에서 차감되지 않습니다.

`1 yugeon = 0.00000001 SMW` · `1 SMW = 100000000 yugeon`

| API / wallet | yugeon / SMW |
|---|---|
| minimum relay | 1 yugeon/vB |
| automatic cap | 0.01 SMW |
| manual cap | 1 SMW |
| manual rate | 1–100000 yugeon/vB |

자동 수수료는 현재 대기 거래량, 블록 처리 용량과 거래 우선순위를 반영합니다. 과거 블록의 수수료는 사용하지 않습니다. 대기량이 적으면 최소 수수료율을 유지합니다. 추천값은 갱신되며 최종 확인 시 수수료가 고정됩니다. 연결된 내 노드의 관측값이며 모든 노드의 상태를 뜻하지 않습니다.

지갑을 다시 열어도 이 노드에서 기록한 거래 교체 내역이 유지됩니다. 제거된 거래는 잔액에 반영되지 않습니다.

채굴 내역에서 블록별 신규 발행 보상, 거래 수수료 보상, 총보상을 구분합니다. 내 지갑이 받은 금액은 별도로 표시합니다. 보상을 일부만 청구한 경우에는 두 항목의 지급액을 임의로 나누지 않습니다. 노드는 수수료 추정을 포함한 RPC 28개를 제공하고, 서명된 거래를 검증·전파합니다.

## 거래·블록 조회

`getrawtransaction`은 활성 체인과 메모리풀을 조회하며 탈락한 분기에만 있는 거래는 찾지 않습니다. 입력은 이전 출력 위치를 가리키며 단일 송신 주소를 뜻하지 않습니다. `getblock`의 `verbose`는 불리언입니다. 보관된 비활성 블록은 `active=false`, `confirmations=-1`이고 해당 블록 해시로 원시 거래를 읽을 수 있습니다. `findspendingtransaction`은 활성 체인의 확정된 사용 거래만 찾으므로 null만으로 사용 가능하다고 판단하면 안 됩니다. `include_mempool=true`인 `gettxout`도 확인하세요. 확인 횟수와 활성 여부는 체인 재편 후 달라질 수 있습니다.

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

[문서](README.html) · [노드 연동](EXCHANGE_INTEGRATION.html) · [노드 운영](NETWORK_RUNBOOK.html) · [변경 사항](RELEASE_NOTES.html) · [검증](EXCHANGE_EXAMPLES.html)

[영문 상세 참고 문서](../../../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../../../API_CONTRACT.json) · [vectors.json](../../../../../examples/exchange/vectors.json)
