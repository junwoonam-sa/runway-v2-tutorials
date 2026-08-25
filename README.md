# Runway v2 Tutorials

Makinarocks Runway v2 AI 플랫폼에서 ML 워크플로우를 실행하는 방법을 보여주는 튜토리얼 모음입니다.

## 디렉토리 구조

```
runway-v2-tutorial/
├── README.md                  # 전체 튜토리얼 인덱스 (이 파일)
├── CLAUDE.md                  # Claude Code용 프로젝트 가이드
├── .gitignore
└── tutorials/
    ├── _template/             # 새 튜토리얼 스캐폴드용 템플릿
    │   ├── README.md
    │   └── requirements.txt
    └── <tutorial-name>/       # 각 튜토리얼은 독립된 디렉토리
        ├── README.md          # 튜토리얼 설명 및 실행 방법 (필수)
        ├── requirements.txt   # Python 의존성 (필수)
        ├── dataset/           # 샘플 데이터 (선택)
        └── ...                # 파이프라인/스크립트 코드
```

## 튜토리얼 목록

| 이름 | 주제 | 주요 기술 |
|------|------|----------|
| [wind-power-prediction-with-xgboost](tutorials/wind-power-prediction-with-xgboost/) | 풍력 발전량 예측 모델 학습/평가/배포 | XGBoost, Airflow, MLflow |
| [runway-llm-tutorial](tutorials/runway-llm-tutorial/) | 내 문서를 읽고 답하는 LLM 챗봇 배포 | FastAPI, MCP, Qdrant, LiteLLM, OpenBao, Helm |

## 새 튜토리얼 추가하기

1. `tutorials/_template/` 를 `tutorials/<new-tutorial-name>/` 로 복사
2. `README.md`, `requirements.txt` 를 해당 튜토리얼에 맞게 수정
3. 코드/데이터셋 추가
4. 루트 `README.md`의 튜토리얼 목록에 항목 추가

## 공통 인프라 (Runway v2)

- **Keycloak**: `keycloak.<your-runway-domain>` — OIDC 토큰 발급
- **MLflow**: 클러스터 내부 URL 접근 + Host 헤더를 `mlflow.<your-runway-domain>` 로 패치
- **PVC**: `/mnt/model-registry` — 모델 아티팩트 영구 저장소
