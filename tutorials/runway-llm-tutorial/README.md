# Runway LLM 챗봇 튜토리얼

Runway 위에서 **내 문서를 읽고 답하는 AI 챗봇**을 만들어 배포합니다.

개발 지식이 없어도 됩니다. 대부분 화면에서 클릭하고 값을 붙여 넣는 작업이고,
명령어가 필요한 곳은 그대로 복사해 쓸 수 있게 적어 두었습니다.

## 개요

| 항목 | 내용 |
|---|---|
| **목적** | 에이전트·MCP·벡터 검색이 붙은 챗봇을 Runway에 배포하고, 내 문서로 답하게 만들기 |
| **난이도** | Beginner (본 흐름) / Intermediate (부록) |
| **예상 소요 시간** | 약 1시간 30분 |
| **대상 버전** | Runway 2.3.0 |
| **주요 스택** | FastAPI, MCP, Qdrant, LiteLLM 게이트웨이, OpenBao, Helm |

## 사전 요구사항

- Runway 프로젝트에 참여(member 이상)한 계정
- 브라우저 — 대부분의 작업이 여기서 일어납니다
- 챗봇의 **차트 리포지토리 주소** (아래 [게시가 필요합니다](#게시가-필요합니다) 참고)

---

## 시작하기

| | | |
|---|---|---|
| **튜토리얼 소개** | [무엇을 만드나요?](docs/intro/01-what-we-build.md) | 완성하면 무엇을 쓰게 되는지 |
| | [애플리케이션 알고가기](docs/intro/02-runway.md) | 알고 가면 안 막히는 세 가지 |
| **0단계. 사전 준비** | [0-1. 환경 정보 및 인증 키 발급](docs/00-preparation/01-keys.md) | 도메인·프로젝트 확인, 키 발급 |
| | [0-2. OpenBao 시크릿 등록](docs/00-preparation/02-openbao.md) | OpenBao에 키 저장하기 |
| **1단계. 개발 환경 설정** | [1-1. PVC 생성](docs/01-dev-env/01-pvc.md) | 저장 공간 |
| | [1-2. Code Server 배포](docs/01-dev-env/02-code-server.md) | 작업 화면 |
| | [1-3. 시크릿 확인](docs/01-dev-env/03-verify.md) | 키가 전달되는지 눈으로 |
| **2단계. 벡터 DB** | [2-1. Qdrant 배포](docs/02-vector-db/01-deploy.md) | 벡터 DB 설치 |
| | [2-2. Qdrant 연결 확인](docs/02-vector-db/02-verify.md) | 주소가 통하는지 |
| **3단계. 챗봇 배포** | [3-1. 챗봇 배포](docs/03-chatbot/01-deploy.md) | 리포지토리 등록 → 차트 → 배포 |
| | [3-2. 상태 확인](docs/03-chatbot/02-status.md) | 무엇이 준비됐는지 읽기 |
| **4단계. 사용하기** | [4-1. 대화해 보기](docs/04-use/01-chat.md) | 첫 메시지 |
| | [4-2. 문서 올리기](docs/04-use/02-documents.md) | 벡터 DB에 문서 넣기 |
| | [4-3. 에이전트 동작 확인](docs/04-use/03-agent.md) | 스스로 검색하는 것 보기 |
| **5단계. 팀에 공개** | [5-1. 팀에 공개하기](docs/05-share/01-publish.md) | 주소 열기, 비밀번호 |
| **부록** | [A. 자가 빌드](docs/appendix/a-self-build.md) | 이미지·차트를 직접 만들기 |
| | [B. 코드 살펴보기](docs/appendix/b-code-tour.md) | 안이 어떻게 도는지 |
| | [C. 문제 해결](docs/appendix/c-troubleshooting.md) | 증상 → 할 일 |

전체를 한 페이지로 묶은 `dist/tutorial.html` 도 있습니다. 내려받아 더블클릭하면
바로 열립니다 — 웹 서버가 필요 없고, 인터넷이 없어도 됩니다.

**따라하는 사람이 설치할 것은 없습니다.** 컨테이너 이미지와 Helm 차트는 미리
준비되어 있고, 3단계에서 그 주소를 입력하기만 합니다.

---

## 무엇을 만드나

![브라우저에서 챗봇 애플리케이션으로, 그 안의 웹 서버·에이전트·MCP 도구 서버가 AI 게이트웨이와 Qdrant를 부르는 구조](docs/assets/architecture.svg)

키는 OpenBao에서 실행 시점에 전달됩니다 — 설정 어디에도 값이 남지 않습니다.

문서를 올려 두고 물어보면, 챗봇이 **스스로 판단해서** 문서를 뒤지고 그 내용을
근거로 답합니다.

```
▸ 도구 호출: search_documents
▸ 도구 결과: [1] policy.md › 휴가 규정 …

문서에 따르면 연차는 15일입니다.
```

---

## 디렉토리 구성

```
runway-llm-tutorial/
├── README.md            이 파일
├── app/                 챗봇 프로그램 — 이것이 이미지로 구워집니다
│   ├── chatbot/           웹 서버, 에이전트, 설정 읽기, 상태 점검
│   ├── mcp_server/        MCP 도구 서버 — 문서 색인과 검색
│   ├── frontend/          화면 (빌드 단계 없음)
│   ├── tests/             pytest
│   ├── requirements.txt   Python 의존성
│   └── Dockerfile         위 셋을 이미지 하나로 묶는 설명서
├── chart/               Runway가 읽는 설치 설명서 (Helm 차트)
│   ├── values.yaml        3-1에서 채우는 빈칸들
│   └── templates/         Deployment, Service, HTTPRoute, Secret, check-values
├── docs/                튜토리얼 문서
│   ├── intro/ 00-preparation/ 01-dev-env/ 02-vector-db/ 03-chatbot/ 04-use/ 05-share/
│   ├── appendix/          부록 A·B·C
│   ├── deep/              개발자용 심화 8편
│   └── assets/            다이어그램 SVG
├── dist/tutorial.html   docs를 묶은 단일 HTML 페이지
├── scripts/             로컬 실행, 스모크 테스트, 차트 패키징, 페이지 빌드
├── samples/             검색을 시험해 볼 샘플 문서
└── .github/workflows/   이미지·차트 게시 (아래 참고 — 지금 위치에서는 동작하지 않습니다)
```

소스 코드와 차트는 **같은 폴더에 있지만 가는 곳이 다릅니다.** `app/` 은 컨테이너
이미지로, `chart/` 는 차트 리포지토리로 갑니다. Runway는 소스 저장소를 읽지 않고
차트 리포지토리만 봅니다 — 자세한 것은 [부록 B](docs/appendix/b-code-tour.md).

---

## 게시가 필요합니다

3-1에서 등록할 **차트 리포지토리 주소**가 아직 비어 있습니다. 이미지와 차트를
한 번 게시해야 그 주소가 생기고, 그때 문서의 빈칸을 채웁니다.

| 채워야 할 곳 | 무엇 |
|---|---|
| `docs/00-preparation/01-keys.md` | 메모 템플릿 ②의 `차트 리포지토리` 줄 |
| `docs/03-chatbot/01-deploy.md` | 시작 블록과 리포지토리 등록 칸 |
| `dist/tutorial.html` | 위 두 문서를 묶은 페이지 (다시 빌드하거나 같은 자리를 고치면 됩니다) |

`.github/workflows/release.yaml` 은 태그를 밀면 이미지와 차트를 게시하도록
작성되어 있지만, **지금 위치에서는 실행되지 않습니다.** GitHub Actions는 저장소
**루트**의 `.github/workflows/` 만 읽는데 이 파일은 튜토리얼 디렉토리 안에
있습니다. 셋 중 하나를 골라야 합니다.

- 워크플로를 저장소 루트로 옮기고 경로를 `tutorials/runway-llm-tutorial/...` 로 고치기
- 이 튜토리얼만 별도 저장소로 분리해 거기서 게시하기
- 사내 Gitea에 직접 올리기 — 폐쇄망이면 어차피 이 경로입니다

방법은 [부록 A. 자가 빌드](docs/appendix/a-self-build.md)에 있습니다.

---

## 개발자를 위한 메모

클러스터 없이 노트북에서 전체를 띄울 수 있습니다. 가짜 게이트웨이와 가짜 Qdrant가
함께 뜹니다.

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r app/requirements.txt
scripts/run-local.sh
```

```bash
cd app && python -m pytest
```

문서를 고친 뒤에는 단일 페이지를 다시 만듭니다.

```bash
python scripts/build-page.py     # → dist/tutorial.html
```

이 튜토리얼이 반복해서 말하는 것:

**설정이 조용히 틀리는 것이 가장 비쌉니다.** 그럴듯한 기본값은 "값을 빠뜨렸다"를
"DNS 오류"로 바꿔 놓습니다. 코드와 차트는 필수값을 추측하지 않습니다.

**실패는 그것을 볼 사람이 있는 곳에서 일어나야 합니다.** 차트는 배포 **전에** 렌더
단계에서 거부하고, 앱은 죽는 대신 **화면에서** 무엇이 빠졌는지 말합니다. 죽은 파드는
아무것도 알려 주지 못합니다.

**애플리케이션 호스트명 앞에는 로그인이 없습니다.** 플랫폼의 로그인 강제는 호스트별
규칙 몇 개뿐이고 애플리케이션 호스트는 거기 없습니다.
