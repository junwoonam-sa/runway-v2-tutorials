# Runway LLM 챗봇 튜토리얼

Runway 위에서 **내 문서를 읽고 답하는 AI 챗봇**을 만들어 배포합니다.

개발 지식이 없어도 됩니다. 대부분 화면에서 클릭하고 값을 붙여 넣는 작업이고,
명령어가 필요한 곳은 그대로 복사해 쓸 수 있게 적어 두었습니다.

대상 버전: **Runway 2.3.0** · 전체 소요 **약 1시간 30분**

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
| **2단계. 문서 창고** | [2-1. Qdrant 배포](docs/02-vector-db/01-deploy.md) | 벡터 DB 설치 |
| | [2-2. 창고 연결 확인](docs/02-vector-db/02-verify.md) | 주소가 통하는지 |
| **3단계. 챗봇 배포** | [3-1. 챗봇 배포](docs/03-chatbot/01-deploy.md) | 리포지토리 등록 → 차트 → 배포 |
| | [3-2. 상태 확인](docs/03-chatbot/02-status.md) | 무엇이 준비됐는지 읽기 |
| **4단계. 사용하기** | [4-1. 대화해 보기](docs/04-use/01-chat.md) | 첫 메시지 |
| | [4-2. 문서 올리기](docs/04-use/02-documents.md) | 창고에 문서 넣기 |
| | [4-3. 에이전트 동작 확인](docs/04-use/03-agent.md) | 스스로 검색하는 것 보기 |
| **5단계. 팀에 공개** | [5-1. 팀에 공개하기](docs/05-share/01-publish.md) | 주소 열기, 비밀번호 |
| **부록** | [A. 자가 빌드](docs/appendix/a-self-build.md) | 이미지·차트를 직접 만들기 |
| | [B. 코드 살펴보기](docs/appendix/b-code-tour.md) | 안이 어떻게 도는지 |
| | [C. 문제 해결](docs/appendix/c-troubleshooting.md) | 증상 → 할 일 |

**설치할 것은 없습니다.** 컨테이너 이미지와 Helm 차트는 이미 게시되어 있고,
3단계에서 그 주소를 입력하기만 합니다.

---

## 무엇을 만드나

```
                                   ┌─────────────────────────────┐
  브라우저 ──────────────────────▶ │  챗봇 (애플리케이션 하나)     │
                                   │                             │
                                   │  웹 서버  ── 화면 보여주기    │
                                   │     │                       │
                                   │     ├─ 에이전트              │
                                   │     │   (도구를 쓸지 판단)   │
                                   │     │                       │
                                   │     └─ MCP 도구 서버         │  ← 같은 안에서
                                   └────────────────────┬────────┘     함께 돕니다
                                          │             │
                        AI 게이트웨이 ◀───┘             └──▶ Qdrant (문서 창고)
                        (플랫폼이 운영)                        내가 설치합니다

  키는 OpenBao에서 실행 시점에 전달 — 설정 어디에도 값이 남지 않습니다
```

문서를 올려 두고 물어보면, 챗봇이 **스스로 판단해서** 문서를 뒤지고 그 내용을
근거로 답합니다.

```
▸ 도구 호출: search_documents
▸ 도구 결과: [1] policy.md › 휴가 규정 …

문서에 따르면 연차는 15일입니다.
```

---

## 저장소 구조

```
app/
  chatbot/          웹 서버 — 설정, 게이트웨이, 에이전트, 상태 점검
  mcp_server/       MCP 도구 서버 — 문서 색인과 검색
  frontend/         화면 (빌드 단계 없음)
  tests/            pytest
  Dockerfile
chart/              Helm 차트
scripts/            로컬 실행, 스모크 테스트, 차트 패키징, 가짜 게이트웨이·Qdrant
samples/            검색을 시험해 볼 샘플 문서
docs/               튜토리얼
  intro/ 00-preparation/ 01-dev-env/ 02-vector-db/ 03-chatbot/ 04-use/ 05-share/
  appendix/         부록 A·B·C
  deep/             개발자용 심화 8편
.github/workflows/  태그를 밀면 이미지와 차트를 자동 게시
```

---

## 이 저장소를 포크했다면

`.github/workflows/release.yaml` 이 태그를 밀 때 두 가지를 자동으로 게시합니다.

```bash
git tag v0.1.0 && git push origin v0.1.0
```

| 게시되는 것 | 주소 |
|---|---|
| 컨테이너 이미지 | `ghcr.io/<계정>/runway-llm-tutorial:0.1.0` |
| Helm 차트 | `https://<계정>.github.io/runway-llm-tutorial` |

아래 주소가 3-1에서 등록할 값입니다. 처음 한 번 저장소 Settings → Actions →
Workflow permissions 를 **Read and write** 로 바꿔 두세요.

자세한 것은 [부록 A](docs/appendix/a-self-build.md).

---

## 개발자를 위한 메모

클러스터 없이 노트북에서 전체를 띄울 수 있습니다.

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r app/requirements.txt
scripts/run-local.sh
```

```bash
cd app && python -m pytest
```

이 저장소가 반복해서 말하는 것:

**설정이 조용히 틀리는 것이 가장 비쌉니다.** 그럴듯한 기본값은 "값을 빠뜨렸다"를
"DNS 오류"로 바꿔 놓습니다. 코드와 차트는 필수값을 추측하지 않습니다.

**실패는 그것을 볼 사람이 있는 곳에서 일어나야 합니다.** 차트는 배포 **전에** 렌더
단계에서 거부하고, 앱은 죽는 대신 **화면에서** 무엇이 빠졌는지 말합니다. 죽은 파드는
아무것도 알려 주지 못합니다.

**애플리케이션 호스트명 앞에는 로그인이 없습니다.** 플랫폼의 로그인 강제는 호스트별
규칙 몇 개뿐이고 애플리케이션 호스트는 거기 없습니다.
