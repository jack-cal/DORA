# SUMUWW · 변경 사항

SUMUWW PC 0.57.46 · 노드는 체인 데이터를 검증·저장·전파·조회합니다.

## 서명 형식

선택 사항인 소스 SDK는 키나 네트워크 없이 거래를 조립하고 전달받은 서명을 검증합니다. 서명 프로그램이나 노드 명령이 아닙니다. P2WPKH 일반송금 제한은 예제 형식에만 적용되며 노드 전체의 제한이 아닙니다. 기존 개인 지갑은 그대로 사용할 수 있습니다.

## RPC·HTTP API

validateaddress는 체크섬과 선택한 네트워크를 검사합니다. decoderawtransaction의 decoded_only는 내용 해석만 뜻하며 서명 검증이나 확정을 뜻하지 않습니다. 기존 OP_RETURN 출력은 외부 프로그램용 데이터를 보존합니다. 노드에 수수료 조회, 전파 전 검증, RBF 교체 상태와 블록 순서에 따른 데이터 기록 조회를 추가했습니다. 교체 거래를 검증한 뒤에만 기존 대기 거래를 제거합니다. 다중 서명과 잠금 출력은 별도 활성화 시험용으로 구현했으며, 운영망에서는 아직 활성화되지 않았습니다.

## 검증

의존성을 설치한 소스에서 python examples/node_contract.py를 실행합니다. 공개 시험 키와 임시 regtest로 거래 제출·거부·확정·체인 재편·데이터 보존을 시험합니다. 실제 자금, 사용자 프로필, 하드웨어 서명기는 사용하지 않습니다.

[문서](README.html) · [노드 연동](EXCHANGE_INTEGRATION.html) · [RPC·HTTP API](RPC_API.html) · [노드 운영](NETWORK_RUNBOOK.html) · [검증](EXCHANGE_EXAMPLES.html)

[영문 상세 참고 문서](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
