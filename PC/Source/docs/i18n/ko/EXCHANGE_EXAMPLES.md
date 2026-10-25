# SUMUWW · 검증

SUMUWW PC 0.57.46 · 노드는 체인 데이터를 검증·저장·전파·조회합니다.

## 서명 형식

선택 사항인 소스 SDK는 키나 네트워크 없이 거래를 조립하고 전달받은 서명을 검증합니다. 서명 프로그램이나 노드 명령이 아닙니다. P2WPKH 일반송금 제한은 예제 형식에만 적용되며 노드 전체의 제한이 아닙니다. 기존 개인 지갑은 그대로 사용할 수 있습니다.

## 검증

의존성을 설치한 소스에서 python examples/node_contract.py를 실행합니다. 공개 시험 키와 임시 regtest로 거래 제출·거부·확정·체인 재편·데이터 보존을 시험합니다. 실제 자금, 사용자 프로필, 하드웨어 서명기는 사용하지 않습니다.

```powershell
python examples/node_contract.py
python -m unittest tests.test_node_contract tests.test_rpc -v
```

[문서](README.html) · [노드 연동](EXCHANGE_INTEGRATION.html) · [RPC·HTTP API](RPC_API.html) · [노드 운영](NETWORK_RUNBOOK.html) · [변경 사항](RELEASE_NOTES.html)

[영문 상세 참고 문서](../../../EXCHANGE_INTEGRATION.html) · [API_CONTRACT.json](../../../API_CONTRACT.json) · [vectors.json](../../../examples/exchange/vectors.json)
