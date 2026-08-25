# LLM 게이트웨이 사용법 (샘플 문서)

## 키 세 가지는 서로 다릅니다

| 키 | 발급 주체 | 용도 | 생김새 |
|---|---|---|---|
| API 키 | Keycloak | 플랫폼 API, MLflow, Airflow, 추론 엔드포인트 | `eyJ`로 시작 |
| LLM API 키 | LiteLLM | LLM 게이트웨이 호출 | `sk-`로 시작 |
| S3 키 | SeaweedFS | 오브젝트 스토리지 | 액세스 키 + 시크릿 쌍 |

챗봇에 넣어야 하는 것은 **LLM API 키**입니다. API 키를 넣으면 게이트웨이가 401로
거부하고, 증상은 "인증 실패" 한 줄뿐이라 원인이 잘 드러나지 않습니다.

## 호출 주소

인클러스터에서는 `http://litellm.runway-applications.svc.cluster.local:4000/v1`,
바깥에서는 `https://llm.<도메인>/v1` 입니다. 인클러스터 주소는 인그레스를 건너뛰므로
TLS 신뢰 문제가 생기지 않습니다.

## 모델 이름은 추측할 수 없습니다

게이트웨이가 publish하는 모델 이름은 관리자가 설정에 손으로 적어 넣은 문자열입니다.
목록을 직접 물어보세요.

    curl -H "Authorization: Bearer sk-..." https://llm.<도메인>/v1/models

기본 설치에는 채팅 모델이 하나뿐이고, 임베딩 모델은 등록되어 있지 않을 수 있습니다.
