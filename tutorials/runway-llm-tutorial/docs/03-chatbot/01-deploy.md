# 3-1. 챗봇 배포

문서를 읽고 답하는 챗봇을 배포합니다.

챗봇 프로그램은 **미리 만들어져 있습니다.** 우리가 코드를 짜지 않습니다 — 만들어 둔
것을 사내에 올려 두고, 그 주소를 Runway에 알려 주고, 내 값 몇 개를 채워 배포합니다.

**차트 리포지토리 주소를 이미 받았다면** 아래 [애플리케이션 만들기](#애플리케이션-만들기)로
바로 가세요. 아직 없다면 다음 절부터 시작합니다.

걸리는 시간 20분 (사내에 직접 올리는 경우 40분).

---

## 시작하기 전에

[0-1의 템플릿 ②](../00-preparation/01-keys.md)가 이렇게 채워져 있어야 합니다.

```
Runway 도메인    : mycompany.com
프로젝트 ID      : my-project

시크릿 엔진      : tutorial
시크릿 이름      : llmchat
PVC 이름         : llm-tutorial-data
Qdrant 앱 ID     : qdrant
Qdrant 주소      : http://qdrant.my-project.svc.cluster.local:6333

차트 리포지토리  : <받은 주소>
```

아래 단계에서 이 값들을 폼과 YAML에 옮겨 적습니다.

---

## 코드를 받아 사내 Gitea에 올리기

주소를 이미 받았다면 [이 절은 건너뛰세요](01-deploy.md#애플리케이션-만들기).
챗봇의 코드는 [이 저장소](https://github.com/junwoonam-sa/runway-v2-tutorials/tree/feature/runway-llm-tutorial)에 있습니다.

챗봇의 이미지와 차트가 아직 어디에도 올라가 있지 않다면, 여기서 한 번 올립니다.
**한 사람이 한 번만 하면 되고,** 그다음부터 팀원들은 그 주소만 받아서 씁니다.

빌드는 **클러스터 안에서** 일어납니다. 내 컴퓨터에 도커를 깔 필요가 없습니다 —
Code Server에도 도커 데몬이 없고, 대신 플랫폼이 도커가 붙은 **Gitea Actions 러너**를
미리 깔아 두었습니다. 소스를 Gitea에 올리면 러너가 이미지를 만들어 줍니다.

브라우저와 Code Server 터미널만 있으면 됩니다.

### 1) 코드 내려받기

명령어를 쓰지 않고 **파일로 받아서 옮깁니다.**

1. [저장소 페이지](https://github.com/junwoonam-sa/runway-v2-tutorials/tree/feature/runway-llm-tutorial)를 엽니다
2. 초록색 **Code** 버튼 → **Download ZIP**
3. 받은 zip을 **내 컴퓨터에서** 풉니다 (더블클릭하거나 오른쪽 클릭 → 압축 풀기)

아래 주소를 브라우저 주소창에 넣어도 바로 받아집니다.

```
https://github.com/junwoonam-sa/runway-v2-tutorials/archive/refs/heads/feature/runway-llm-tutorial.zip
```

### 필요한 것은 폴더 하나입니다

압축을 풀면 튜토리얼이 여러 개 나오는데, 우리가 쓰는 것은 그중 하나뿐입니다.

```
runway-v2-tutorials-feature-runway-llm-tutorial/
└── tutorials/
    ├── energy-demand-prediction/       ← 다른 튜토리얼
    ├── wind-power-prediction-.../      ← 다른 튜토리얼
    └── runway-llm-tutorial/            ← 이것만 씁니다
        ├── app/       챗봇 프로그램. 이것이 이미지로 구워집니다
        ├── chart/     Runway에 설치하는 방법이 적힌 차트
        ├── docs/      지금 읽고 있는 이 문서
        └── scripts/   차트를 묶어 올리는 스크립트
```

`runway-llm-tutorial` 폴더 하나가 챗봇의 전부입니다. 이 폴더를 Gitea에 올린 뒤,
그 안의 `app/` 으로 **이미지**를 만들고 `chart/` 로 **차트**를 만듭니다.

### Code Server로 옮기기

1-2에서 만든 Code Server 화면을 엽니다. 왼쪽 파일 목록의 **빈 곳**에
`runway-llm-tutorial` **폴더를 끌어다 놓습니다.** 폴더째 올라갑니다.

올라갔는지 터미널에서 확인합니다 (**Terminal → New Terminal**).

```bash
cd runway-llm-tutorial
ls
```

`app  chart  docs  samples  scripts` 가 보이면 됩니다. **여기서부터 나오는 명령은
전부 이 폴더 안에서** 실행합니다.

> 브라우저가 폴더 드래그를 지원하지 않으면, zip 파일을 그대로 끌어다 놓고
> 터미널에서 푸는 방법도 있습니다.
>
> ```bash
> unzip runway-v2-tutorials-feature-runway-llm-tutorial.zip
> cd runway-v2-tutorials-feature-runway-llm-tutorial/tutorials/runway-llm-tutorial
> ```

### 2) Gitea에 로그인하고 토큰 만들기

**콘솔 → Built-in Apps → Gitea** 카드로 들어갑니다. **이 경로로 들어가야 합니다** —
프로젝트 조직은 SSO로 로그인하는 순간에 만들어져서, 한 번도 들어간 적이 없으면
조직이 아예 안 보이고 404가 뜹니다.

#### 토큰 만들기

Gitea 화면에서 다섯 단계입니다.

1. 오른쪽 위 **프로필 사진** → **Settings**
2. **Applications** 탭
3. **Token Name** 칸에 이름을 적습니다 — 아무 이름이나 됩니다 (예: `llm-tutorial`)
4. 권한 목록에서 **두 가지를 `Write` 로** 지정합니다

   | 항목 | 지정할 값 | 무엇에 쓰나 |
   |---|---|---|
   | `repository` | **Write** | 저장소를 만들고 소스를 올릴 때 |
   | `package` | **Write** | 이미지와 차트를 올릴 때 |

   버전에 따라 `write:repository` · `write:package` 를 **체크하는** 화면일 수도
   있습니다. 이름이 같으니 그대로 켜면 됩니다.

5. **Generate Token**

값이 화면 위쪽에 **한 번만** 나옵니다. 지금 복사해서 0-1에서 열어 둔 메모장에
붙여 두세요. 창을 벗어나면 다시 볼 수 없고, 그때는 지우고 새로 만드는 수밖에
없습니다.

#### 이 토큰을 두 곳에서 씁니다

| 어디에 | 언제 |
|---|---|
| 터미널이 묻는 `Password` 칸 | 3)에서 소스를 올릴 때 |
| 저장소의 `REGISTRY_TOKEN` 시크릿 | 5)에서 이미지를 빌드할 때 |

> ⚠ **`repository` 만 켜면 실패합니다.** 이미지와 차트는 저장소가 아니라
> **패키지 레지스트리**에 올라갑니다. 그때 나오는 오류가 `authGroup.Verify` 처럼
> 생겨서 원인을 알기 어렵습니다.

> ⚠ **토큰을 주소에 끼워 넣지 마세요.** `https://<계정>:<토큰>@gitea...` 형태로 쓰면
> 셸 기록과 `.git/config` 에 남습니다. Code Server의 홈은 재시작해도 남는 볼륨입니다.

### 3) 소스를 Gitea 저장소에 올리기

Gitea 화면 우측 상단 **+ → New Repository**. 세 칸만 봅니다.

| 칸 | 넣을 값 |
|---|---|
| Owner | 내 계정 또는 프로젝트 조직 — **둘 다 됩니다** |
| Repository Name | `llm-tutorial` |
| Visibility | 아무 쪽이나 |

> **어디에 만들어도 됩니다.** 이 저장소에는 소스가 들어갑니다 — 사람이 읽는 것이고,
> 클러스터는 보지 않습니다. 나중에 만들 **이미지만** 프로젝트 조직으로 보내면 되고,
> 그건 5)에서 변수 하나로 정합니다.

만든 뒤, Code Server 터미널에서 올립니다. `runway-llm-tutorial` 폴더 안에 있는지
먼저 확인하세요 — `ls` 했을 때 `app` 이 보이면 맞습니다.

**첫 번째로, 커밋할 사람 정보를 정합니다.** 이게 없으면 커밋이 아예 만들어지지
않습니다.

```bash
git config --global user.email "내 이메일"
git config --global user.name "내 이름"
```

**두 번째로, 커밋하고 주소를 연결합니다.**

```bash
git init -b main
git add -A
git commit -m "튜토리얼 챗봇"
git branch -M main
git remote add origin https://gitea.<도메인>/<계정 또는 조직>/llm-tutorial.git
```

**세 번째로, 올립니다.** Code Server에서는 앞에 한 줄이 더 필요합니다.

```bash
unset GIT_ASKPASS VSCODE_GIT_ASKPASS_NODE VSCODE_GIT_ASKPASS_MAIN VSCODE_GIT_IPC_HANDLE
git -c credential.helper= push -u origin main
```

계정과 비밀번호를 물어봅니다.

| 물어보는 것 | 넣을 값 |
|---|---|
| `Username` | Gitea 계정 이름 |
| `Password` | **2)에서 만든 토큰** — 계정 비밀번호가 아닙니다 |

토큰을 붙여 넣어도 화면에는 아무것도 안 보입니다. 정상입니다. 그대로 엔터를 치세요.

> ⚠ **`unset` 줄을 빼면 실패합니다.** Code Server는 편집기 화면에 로그인 창을 띄우는
> 방식으로 자격증명을 받는데, 터미널에서는 그 창으로 갈 수 없습니다. 증상은
> `Missing or invalid credentials` 와 `ECONNREFUSED /tmp/vscode-git-….sock` 입니다.
> 저 줄이 그 방식을 꺼서, 터미널이 직접 묻게 만듭니다.

> **매번 묻는 것이 번거로우면** 한 시간만 기억하게 할 수 있습니다.
>
> ```bash
> git config --global credential.helper 'cache --timeout=3600'
> ```
>
> 파일로 저장하는 `store` 는 권하지 않습니다 — 토큰이 평문으로 남습니다.

### 4) 러너가 살아 있는지 먼저 확인하기

이미지 빌드를 맡기기 전에, 러너가 실제로 도는지 봅니다. **여기서 막히면 뒤가 전부
막히므로 먼저 확인하는 편이 낫습니다.**

저장소 화면의 **Actions** 탭을 엽니다. `build-image` 워크플로가 보이면 **Run
workflow** 를 눌러 한 번 돌려 보세요.

| 보이는 것 | 뜻 | 할 일 |
|---|---|---|
| 몇 초 안에 로그가 흐르기 시작 | 러너 정상 | 5)로 갑니다 |
| `Waiting for runner…` 에서 멈춤 | 러너가 자기 이미지를 받지 못함 | 폐쇄망에서 미러가 설정되지 않은 경우입니다. 플랫폼 담당자에게 문의하세요 |
| Actions 탭 자체가 없음 | 저장소에서 Actions가 꺼져 있음 | Settings → Repository → Actions 켜기 |

### 임베딩은 기본으로 들어 있습니다

문서를 검색하려면 문장을 숫자(벡터)로 바꾸는 계산이 필요합니다. 이 저장소의
이미지는 **앱 안에서 계산하도록** 만들어져 있어서, 따로 할 일이 없습니다.
게이트웨이에 임베딩 모델이 없는 설치본이 많기 때문에 그쪽을 기본으로 뒀습니다.

계산은 CPU로 합니다 — GPU가 필요 없습니다. 첫 문서를 올릴 때 모델을 한 번
내려받아 볼륨에 저장하고, 그다음부터는 그것을 씁니다.

> **게이트웨이에 임베딩 모델이 있다면** 이미지를 가볍게 할 수 있습니다. 먼저
> 확인해 보세요.
>
> ```bash
> source /vault/secrets/llmchat.env
> curl -s -H "Authorization: Bearer $LLM_API_KEY" http://litellm.runway-applications.svc.cluster.local:4000/v1/models
> ```
>
> 목록에 `bge`·`e5`·`embedding` 같은 이름이 있으면, `app/Dockerfile` 에서
> `requirements-local-embeddings` 관련 세 줄을 지우고 values에서
> `embedding.provider: "gateway"` 와 `gatewayModel` 을 적으면 됩니다.
> 그러면 이미지가 훨씬 작아집니다.

> **첫 실행에 `huggingface.co` 접근이 필요합니다.** 모델 가중치를 거기서 받습니다.
> 폐쇄망이면 받지 못하므로, 플랫폼 담당자에게 게이트웨이에 임베딩 모델을 등록해
> 달라고 요청하는 편이 빠릅니다. 확인:
> `curl -sI -m 10 https://huggingface.co | head -1`

### 5) 등록해 두기 — 값 세 개

빌드가 레지스트리에 로그인하고, 이미지와 차트를 어디에 올릴지 정하는 값들입니다.

**저장소 → Settings → Actions**

| 어디 | Name | Value |
|---|---|---|
| **Variables** | `REGISTRY_HOST` | `gitea.<도메인>` — 주소창의 Gitea 주소에서 `https://` 를 뗀 것 |
| **Variables** | `REGISTRY_OWNER` | **프로젝트 ID** — 이미지를 올릴 곳 |
| **Secrets** | `REGISTRY_TOKEN` | 2)에서 만든 토큰 (`package` 가 `Write` 인 것) |

> ⚠ **사용자 Settings가 아니라 저장소 Settings 입니다.** 두 곳 모두 Actions 메뉴가
> 있어서 헷갈립니다. 빠뜨리면 빌드가 이렇게 멈춥니다.
>
> | 빠진 것 | 나오는 메시지 |
> |---|---|
> | `REGISTRY_TOKEN` | `password is empty` |
> | `REGISTRY_HOST` | `server gave HTTP response to HTTPS client` |

> **이미지는 프로젝트 조직에, 차트는 아무 데나.** 이미지는 노드가 프로젝트의 봇
> 자격증명으로 받아 가는데 그 봇이 개인 계정을 못 읽습니다. 차트는 Argo CD가
> **내 자격증명**으로 읽으니 개인 계정이어도 됩니다. 차트를 다른 곳에 올리고
> 싶으면 `CHART_OWNER` 변수를 추가하세요 — 비워 두면 이 저장소가 있는 곳입니다.

### 6) 태그를 밀면 나머지는 자동입니다

```bash
git add -A && git commit -m "설정 반영" && git push
git tag v0.1.0 && git push origin v0.1.0
```

Actions 탭에서 진행이 보입니다. 태그 하나로 네 가지가 일어납니다.

1. `app/` 을 이미지로 빌드해 올림
2. 그 이미지 주소와 태그를 `chart/values.yaml` 에 박아 넣음
3. 차트 버전을 태그와 같게 맞춤
4. 차트를 묶어 Helm 레지스트리에 올림

**손으로 버전을 맞출 일이 없습니다.** 로그 마지막에 등록할 주소와 차트 버전이
나옵니다.

```
애플리케이션 생성 폼에 넣을 리포지토리 URL:
  https://gitea.<도메인>/api/packages/<계정 또는 조직>/helm
차트 버전: 0.1.0
```

이 주소를 [0-1 템플릿 ②](../00-preparation/01-keys.md)의 `차트 리포지토리` 줄에
적어 두세요. 바로 아래에서 씁니다.

> **고칠 때마다 태그를 올리세요.** `v0.1.1`, `v0.1.2` … 같은 태그를 다시 쓰면
> 두 곳에서 막힙니다. 노드는 이미 받아 둔 이미지를 다시 받지 않고, Helm
> 레지스트리는 같은 차트 버전을 덮어쓰지 않습니다(`409`).

> **패키지가 두 개 생기면 정상입니다.** 계정 페이지(`.../-/packages`)에 타입이
> `Container` 인 것과 `Helm` 인 것이 하나씩 보입니다. 앞은 파드가 실행할 이미지,
> 뒤는 Runway가 읽을 차트입니다. **등록하는 주소는 Helm 쪽입니다.**

> **직접 올리고 싶다면** 저장소의 `scripts/package-chart.sh` 가 차트만 따로
> 묶어 올립니다 — `bash scripts/package-chart.sh`. 워크플로가 하는 일과 같습니다.

---

## 애플리케이션 만들기

**애플리케이션(Applications)** → 우측 상단 **+ 생성**.

### 기본 정보

| 칸 | 넣을 값 |
|---|---|
| 이름 | `LLM 챗봇` |
| **ID** | `llm-chat` |
| 설명 (선택) | `문서를 읽고 답하는 AI 챗봇` |

> **ID는 짧게 지으세요.** 만든 뒤에는 바꿀 수 없고, 너무 길면 배포가 실패합니다.
> `llm-chat` 정도면 안전합니다.

---

## Helm 리포지토리 등록

**Helm 리포지토리 URL** 칸 오른쪽의 **등록** 버튼을 클릭합니다.

**7)에서 나온 주소**를 그대로 붙여 넣고 **저장**을 누릅니다. 0-1 템플릿 ②의
`차트 리포지토리` 줄에 적어 둔 그 값입니다.

```
https://gitea.<도메인>/api/packages/<계정 또는 조직>/helm
```

주소를 받아서 시작한 경우라면 받은 주소를 그대로 넣으면 됩니다.

> ⚠ **끝에 아무것도 붙이지 마세요.** `/index.yaml` 이나 `/api/charts` 를 붙이면
> 등록이 실패합니다. 브라우저로 열었을 때 404가 나는 그 주소가 맞습니다.

> **등록이 하는 일**
> 저장을 누르면 Runway가 그 주소에서 차트 목록을 가져옵니다. 그다음 **차트**와
> **차트 버전** 드롭다운이 활성화됩니다.

> **이 주소를 브라우저로 열면 안내 문구만 나오는 것이 정상입니다.** 사람이 볼
> 페이지가 아니라 프로그램이 읽는 목록입니다.

---

## 차트 고르기

드롭다운에서 고릅니다.

| 칸 | 값 |
|---|---|
| 차트 | `llm-tutorial` |
| 차트 버전 | 목록에서 가장 높은 것 |

고르면 화면 아래에 **헬름 차트(values.yaml)** 영역이 나타납니다.

---

## 애플리케이션 열기 링크

이름과 주소를 추가합니다.

| 칸 | 값 |
|---|---|
| 이름 | `챗봇` |
| URL | `https://llm-chat-<프로젝트 ID>.<도메인>` |

예: `https://llm-chat-my-project.mycompany.com`

> 이 주소는 5단계에서 실제로 열 주소입니다. 지금은 적어만 두고, 3단계에서는
> 외부 접근을 꺼 둔 채로 확인합니다.

---

## values.yaml 수정 — 차트의 빈칸 채우기

여기가 [소개에서 말한 "빈칸"](../intro/02-runway.md)입니다. 차트는 설치 설명서이고,
`values.yaml` 은 사람마다 다른 값을 채우는 자리입니다.

**헬름 차트** 영역은 기본으로 **폼** 탭이 열려 있습니다.
**YAML** 탭을 선택한 뒤, 아래 네 곳만 내 값으로 바꿉니다.

> 여기 적는 값은 **비밀이 아닌 것들**입니다 — PVC 이름, Qdrant 주소, 엔진 이름.
> 비밀(`LLM_API_KEY`)은 0-2에서 OpenBao에 넣었고 여기 적지 않습니다.
> 왜 그렇게 나뉘는지는 [0-2의 설명](../00-preparation/02-openbao.md)에 있습니다.

```yaml
runway:
  openbao:
    secretEngine: "tutorial"        # 템플릿 ②의 '시크릿 엔진'
    secretName: "llmchat"           # 템플릿 ②의 '시크릿 이름'

  vector:
    enabled: true
    url: "http://qdrant.<프로젝트 ID>.svc.cluster.local:6333"   # 템플릿 ②의 'Qdrant 주소'

  storage:
    enabled: true
    existingClaim: "llm-tutorial-data"   # 템플릿 ②의 'PVC 이름'
```

나머지는 손대지 않아도 됩니다. 이미지 주소와 태그는 차트에 이미 들어 있습니다.

### YAML로 한 번에 넣기

위 네 곳을 찾아 고치는 대신, **YAML 탭의 내용을 전부 지우고** 아래를 통째로 붙여
넣어도 됩니다. 바꿀 곳은 한 줄뿐입니다.

```yaml
runway:
  llm:
    # 대부분의 설치본에서 이 주소가 그대로 맞습니다
    baseUrl: "http://litellm.runway-applications.svc.cluster.local:4000/v1"
    model: ""              # 비우면 실행할 때 게이트웨이에 물어보고 고릅니다
    temperature: 0.7
    maxTokens: 0
    systemPrompt: ""       # 답변 말투를 정하고 싶으면 여기에
    maxToolRounds: 3

  # 0-2에서 OpenBao에 저장한 것을 가리킵니다
  openbao:
    secretEngine: "tutorial"
    secretName: "llmchat"
    mountPath: /vault/secrets

  credentials:
    existingSecret: ""
    create: false
    data:
      LLM_API_KEY: ""      # 비워 두세요. 키는 OpenBao에서 옵니다
      ACCESS_PASSWORD: ""

  # 2-1에서 만든 Qdrant
  vector:
    enabled: true
    url: "http://qdrant.<프로젝트 ID>.svc.cluster.local:6333"   # ← 바꾸세요
    collection: "tutorial-docs"

  embedding:
    provider: "auto"       # 게이트웨이를 먼저 재보고 안 되면 앱에서 계산
    gatewayModel: ""
    localModel: "intfloat/multilingual-e5-small"
    cachePath: /data/embedding-cache

  # 1-1에서 만든 볼륨
  storage:
    enabled: true
    existingClaim: "llm-tutorial-data"
    mountPath: /data

  # 주소 앞에 플랫폼 로그인이 없습니다. 비밀번호를 켜 둡니다.
  access:
    passwordRequired: true

  certs:
    enabled: false            # 사설 인증서 설치본에서만 켭니다

  httpRoute:
    enabled: true
    hostnames:
      - "llm-chat-<프로젝트 ID>.<도메인>"   # ← 바꾸세요. 전부 소문자
    targetPort: 80
    path: /
    gateway:
      name: platform-core-gateway
      namespace: istio-system

replicaCount: 1

service:
  type: ClusterIP
  port: 80

containerPort: 8000

resources:
  requests:
    cpu: 100m
    memory: 256Mi
  limits:
    cpu: "1"
    memory: 1Gi

podSecurityContext:
  runAsNonRoot: true
  runAsUser: 10001
  fsGroup: 10001

securityContext:
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: false
  capabilities:
    drop:
      - ALL

nameOverride: ""
fullnameOverride: ""
extraEnv: []
podAnnotations: {}
nodeSelector: {}
tolerations: []
affinity: {}
```

**두 곳**을 내 값으로 바꿉니다 — `vector.url` 의 `<프로젝트 ID>`, 그리고
`httpRoute.hostnames` 의 주소입니다. 호스트명은 위 「애플리케이션 열기 링크」에
적은 것과 **같아야** 합니다.

> **비밀번호가 필요합니다.** `passwordRequired: true` 이므로 OpenBao의 `llmchat` 에
> `ACCESS_PASSWORD` 가 들어 있어야 합니다(0-2에서 넣었습니다). 없으면 배포가
> 거부되면서 그 이유를 말해 줍니다.

> ⚠ **`image:` 와 `imagePullSecrets:` 를 여기 적지 마세요.** 차트를 만들 때 이미
> 박아 넣었습니다. 여기 적으면 **그 값을 덮어씁니다** — 옛 태그를 적어 두면 새로
> 빌드한 이미지가 아니라 옛 이미지가 계속 뜨고, 증상은 "고쳤는데 반영이 안 된다"로
> 나타납니다. 코드를 고쳤을 때는 태그를 올려 다시 빌드하고, 애플리케이션에서
> **차트 버전만** 새 것으로 바꾸면 됩니다.

> ⚠ **덧붙이지 말고 지우고 넣으세요.** 같은 키가 두 번 있으면 YAML은 **뒤에 나온 것을**
> 씁니다. 앞에 적은 값이 오류 없이 무시되고, 증상은 "설정했는데 동작하지 않는다"로
> 나타납니다.

> **`provider: "auto"` 를 그대로 두면 됩니다.** 게이트웨이에 임베딩 모델이 있으면
> 그쪽을 쓰고, 없으면 앱에서 계산합니다. 어느 쪽을 골랐는지는 상태 화면의 임베딩
> 항목에 표시됩니다.
>
> 볼륨(`storage.enabled: true`)은 켜 두세요. 앱에서 계산할 때 받은 모델 가중치를
> 거기에 저장하고, 그래야 파드가 재시작해도 다시 받지 않습니다.

### AI 모델 이름은 안 적어도 됩니다

다른 안내에서는 모델 이름을 적으라고 할 수 있습니다. **이 챗봇은 안 적어도 됩니다.**
실행될 때 게이트웨이에 "쓸 수 있는 모델이 뭐가 있냐"고 직접 물어보고 알아서
고릅니다. 무엇을 골랐는지는 화면에 표시해 줍니다.

특정 모델을 꼭 써야 한다면 `runway.llm.model` 에 이름을 적으면 됩니다.

### 게이트웨이 주소가 다르다면

기본값은 대부분의 설치본에서 그대로 맞습니다.

```yaml
runway:
  llm:
    baseUrl: "http://litellm.runway-applications.svc.cluster.local:4000/v1"
```

이 주소가 다른 설치본이면 챗봇이 화면에서 "게이트웨이에 연결하지 못했습니다"라고
알려 줍니다. 그때 플랫폼 담당자에게 물어보면 됩니다.

---

## 생성하고 배포하기

**생성** 버튼을 클릭하고, 상세 화면에서 **배포** 버튼을 클릭합니다.

1~2분 뒤 상태가 `Healthy` 로 바뀌면 완료입니다.

> 값을 잘못 넣었다면 배포가 **거부되면서 이유를 말해 줍니다.** 예를 들어
> 호스트명에 대문자가 있거나, Qdrant 주소 끝에 `/` 가 붙어 있으면 그 자리에서
> 알려 줍니다. 클러스터에는 아무것도 만들어지지 않으니 안심하고 고치면 됩니다.

---

## 여기까지 되면 성공

- [ ] Helm 리포지토리를 등록했고 차트 목록이 나타났다
- [ ] `llm-tutorial` 차트를 골랐다
- [ ] YAML에서 네 곳을 내 값으로 바꿨다
- [ ] 애플리케이션이 `Healthy` 다

---

## 막혔다면

| 이런 화면이 나오면 | 원인 | 이렇게 하세요 |
|---|---|---|
| 등록했는데 차트 목록이 비어 있음 | 주소가 틀렸거나 아직 게시 전 | 주소 끝에 `/` 나 `index.yaml` 을 붙이지 않았는지 확인 |
| `CONNECTION_FAILED` | 클러스터가 그 주소에 닿지 못함 | 폐쇄망일 수 있습니다. [부록 A](../appendix/a-self-build.md)로 사내에 올리세요 |
| `REPOSITORY_EXISTS` | 같은 주소가 이미 등록됨 | 이미 등록된 것을 쓰면 됩니다 |
| 배포가 거부되며 메시지가 뜸 | 값이 잘못됨 | 메시지가 어느 값인지 말해 줍니다. 그대로 고치세요 |
| 상태가 `ImagePullBackOff` | 이미지를 못 받아옴 | 클러스터가 외부 레지스트리에 닿지 못하는 경우입니다. [부록 A](../appendix/a-self-build.md) |
| 만들었는데 실행 안 됨 | 배포 버튼 미클릭 | 상세 화면 → **배포** |

---

← [2-2. Qdrant 연결 확인](../02-vector-db/02-verify.md) | 다음: [3-2. 상태 확인 →](02-status.md)
