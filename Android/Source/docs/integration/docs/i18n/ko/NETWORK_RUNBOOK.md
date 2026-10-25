# SUMUWW Android 0.6.95 · 노드 운영

SUMUWW Android 0.6.95 · 노드는 체인 데이터를 검증·저장·전파·조회합니다.

## 네트워크와 주소

공개 네트워크 이름은 `sumuww`이며 `dora`는 내부 별칭입니다. 아래 제네시스 해시도 확인하세요. 기본 주소는 압축된 secp256k1 공개키의 HASH160을 사용하는 witness v0 P2WPKH입니다. 필수 메모나 태그는 없습니다. 다른 네트워크의 주소나 체크섬이 잘못된 주소는 거부합니다. HD 주소별로 수신·거스름돈 분기와 인덱스를 기록하고, 비트코인과 파생 경로가 같다고 가정하지 마세요.

## 거래·블록 조회

`getrawtransaction`은 활성 체인과 메모리풀을 조회하며 탈락한 분기에만 있는 거래는 찾지 않습니다. 입력은 이전 출력 위치를 가리키며 단일 송신 주소를 뜻하지 않습니다. `getblock`의 `verbose`는 불리언입니다. 보관된 비활성 블록은 `active=false`, `confirmations=-1`이고 해당 블록 해시로 원시 거래를 읽을 수 있습니다. `findspendingtransaction`은 활성 체인의 확정된 사용 거래만 찾으므로 null만으로 사용 가능하다고 판단하면 안 됩니다. `include_mempool=true`인 `gettxout`도 확인하세요. 확인 횟수와 활성 여부는 체인 재편 후 달라질 수 있습니다.

[API_CONTRACT.json](../../../API_CONTRACT.json)
