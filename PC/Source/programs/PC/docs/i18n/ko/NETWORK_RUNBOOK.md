# SUMUWW · 노드 운영

SUMUWW PC 0.57.46 · 노드는 체인 데이터를 검증·저장·전파·조회합니다.

## 네트워크와 주소

공개 네트워크 이름은 `sumuww`이며 `dora`는 내부 별칭입니다. 아래 제네시스 해시도 확인하세요. 기본 주소는 압축된 secp256k1 공개키의 HASH160을 사용하는 witness v0 P2WPKH입니다. 필수 메모나 태그는 없습니다. 다른 네트워크의 주소나 체크섬이 잘못된 주소는 거부합니다. HD 주소별로 수신·거스름돈 분기와 인덱스를 기록하고, 비트코인과 파생 경로가 같다고 가정하지 마세요.

## 인증과 제한

RPC를 명시적으로 켜고 숫자 루프백 `127.0.0.1:18443` 및 비공개 Bearer 토큰을 사용합니다. 지갑 잠금 해제나 원격 서명 기능은 노출하지 않습니다. 같은 PC의 서비스나 인증된 터널로 연결하세요. 브라우저의 Origin/Referer 요청은 거부됩니다. JSON-RPC는 POST `/rpc`, 객체·배열 `params`, `id`를 사용하고 알림 요청에는 HTTP 204를 반환합니다. 한도는 본문 8004096바이트, 헤더 8192바이트, 묶음 16개, 동시 요청 16개, 제한 시간 10초입니다. 페이지 limit은 1–1000, offset은 0–1000000이며 메서드 28개와 REST 경로 11개가 있습니다.

## 거래·블록 조회

`getrawtransaction`은 활성 체인과 메모리풀을 조회하며 탈락한 분기에만 있는 거래는 찾지 않습니다. 입력은 이전 출력 위치를 가리키며 단일 송신 주소를 뜻하지 않습니다. `getblock`의 `verbose`는 불리언입니다. 보관된 비활성 블록은 `active=false`, `confirmations=-1`이고 해당 블록 해시로 원시 거래를 읽을 수 있습니다. `findspendingtransaction`은 활성 체인의 확정된 사용 거래만 찾으므로 null만으로 사용 가능하다고 판단하면 안 됩니다. `include_mempool=true`인 `gettxout`도 확인하세요. 확인 횟수와 활성 여부는 체인 재편 후 달라질 수 있습니다.

## 검증

의존성을 설치한 소스에서 python examples/node_contract.py를 실행합니다. 공개 시험 키와 임시 regtest로 거래 제출·거부·확정·체인 재편·데이터 보존을 시험합니다. 실제 자금, 사용자 프로필, 하드웨어 서명기는 사용하지 않습니다.

```text
network: sumuww (dora)
genesis: 00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97
HRP: sumuww
P2P magic: d052470c
1 SMW = 100000000 yugeon
```

[문서](README.html) · [노드 연동](EXCHANGE_INTEGRATION.html) · [RPC·HTTP API](RPC_API.html) · [변경 사항](RELEASE_NOTES.html) · [검증](EXCHANGE_EXAMPLES.html)

[영문 상세 참고 문서](../../../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../../../API_CONTRACT.json) · [vectors.json](../../../../../examples/exchange/vectors.json)
