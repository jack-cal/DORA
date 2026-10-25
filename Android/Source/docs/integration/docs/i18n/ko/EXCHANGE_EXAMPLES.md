# SUMUWW Android 0.6.95 · 검증

SUMUWW Android 0.6.95 · 노드는 체인 데이터를 검증·저장·전파·조회합니다.

API 규격은 앱에 포함된 노드 내부 기능을 설명합니다. 안드로이드 앱에는 RPC 설정 화면이 없습니다.

## RPC·HTTP API

validateaddress는 체크섬과 선택한 네트워크를 검사합니다. decoderawtransaction의 decoded_only는 내용 해석만 뜻하며 서명 검증이나 확정을 뜻하지 않습니다. 기존 OP_RETURN 출력은 외부 프로그램용 데이터를 보존합니다. 노드에 수수료 조회, 전파 전 검증, RBF 교체 상태와 블록 순서에 따른 데이터 기록 조회를 추가했습니다. 교체 거래를 검증한 뒤에만 기존 대기 거래를 제거합니다. 다중 서명과 잠금 출력은 별도 활성화 시험용으로 구현했으며, 운영망에서는 아직 활성화되지 않았습니다.

## 거래·블록 조회

`getrawtransaction`은 활성 체인과 메모리풀을 조회하며 탈락한 분기에만 있는 거래는 찾지 않습니다. 입력은 이전 출력 위치를 가리키며 단일 송신 주소를 뜻하지 않습니다. `getblock`의 `verbose`는 불리언입니다. 보관된 비활성 블록은 `active=false`, `confirmations=-1`이고 해당 블록 해시로 원시 거래를 읽을 수 있습니다. `findspendingtransaction`은 활성 체인의 확정된 사용 거래만 찾으므로 null만으로 사용 가능하다고 판단하면 안 됩니다. `include_mempool=true`인 `gettxout`도 확인하세요. 확인 횟수와 활성 여부는 체인 재편 후 달라질 수 있습니다.

[API_CONTRACT.json](../../../API_CONTRACT.json)
