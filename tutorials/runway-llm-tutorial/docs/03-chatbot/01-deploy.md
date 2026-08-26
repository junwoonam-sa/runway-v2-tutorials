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
| Visibility | **Public** (공개) |

> **공개로 두는 이유.** 여기 올린 이미지를 나중에 챗봇이 받아 갑니다. 내 계정 밑에
> 있는 비공개 이미지는 프로젝트가 읽지 못합니다 — 프로젝트가 쓰는 자격증명은 조직
> 봇 계정 것이라 개인 계정 범위 밖이기 때문입니다. **공개로 두면 자격증명 자체가
> 필요 없어서** 이 문제가 사라집니다. 프로젝트 조직 밑에 만들었다면 비공개여도
> 됩니다.

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

### 5) 이미지 빌드해서 올리기

먼저 **저장소에 두 가지를 등록합니다.** 빌드가 레지스트리에 로그인할 때 씁니다.

**저장소 → Settings → Actions** 로 가서, 두 곳에 하나씩 넣습니다.

| 어디 | Name | Value |
|---|---|---|
| **Variables** → Add Variable | `REGISTRY_HOST` | `gitea.<도메인>` — 주소창에 보이는 Gitea 주소에서 `https://` 를 뗀 것 |
| **Secrets** → Add Secret | `REGISTRY_TOKEN` | 2)에서 만든 토큰 (`package` 가 `Write` 인 것) |

예를 들어 Gitea 주소가 `https://gitea.mycompany.com` 이라면 `REGISTRY_HOST` 는
`gitea.mycompany.com` 입니다. 앞에 `https://` 를 붙이면 안 됩니다.

> ⚠ **사용자 Settings가 아니라 저장소 Settings 입니다.** 두 곳 모두 Actions 메뉴가
> 있어서 헷갈립니다. 빠뜨리면 빌드가 이렇게 멈춥니다.
>
> | 빠진 것 | 나오는 메시지 |
> |---|---|
> | `REGISTRY_TOKEN` | `password is empty` |
> | `REGISTRY_HOST` | `server gave HTTP response to HTTPS client` |
>
> 두 번째는 주소를 안 알려 주면 빌드가 **클러스터 내부 주소**를 쓰기 때문입니다.
> 그 주소는 평문이라 docker가 거부하고, 설령 올라가도 나중에 파드가 그 이름으로는
> 이미지를 받지 못합니다.

그다음 태그를 밀면 빌드가 시작됩니다.

```bash
git tag v0.1.0
git push origin v0.1.0
```

Actions 탭에서 진행을 볼 수 있습니다. 끝나면 로그 마지막에 이렇게 나옵니다.

```
올라간 이미지 — chart/values.yaml 에 이 두 값을 적으세요:
  repository: gitea.<도메인>/<프로젝트 ID>/llm-tutorial
  tag:        0.1.0
```

> **이미지는 저장소가 있는 곳에 올라갑니다.** 저장소를 내 계정에 만들었으면 이미지도
> 내 계정 밑으로, 프로젝트 조직에 만들었으면 조직 밑으로 갑니다. 어느 쪽이든 되지만
> **내 계정이라면 저장소가 공개여야 합니다** — 비공개면 프로젝트가 이미지를 읽지 못해
> 파드가 `ImagePullBackOff` 로 멈춥니다. 6)에서 확인하는 방법이 나옵니다.

> **같은 태그를 다시 쓰지 마세요.** 쿠버네티스는 이미 받아 둔 이미지를 다시 받지
> 않습니다. 코드를 고쳤다면 `v0.1.1`, `v0.1.2` 로 올리세요.

### 6) 차트가 그 이미지를 가리키게 하기

빌드 로그 마지막에 나온 두 값을 `chart/values.yaml` 에 적습니다.

```yaml
image:
  repository: "gitea.<도메인>/<계정 또는 조직>/llm-tutorial"
  tag: "0.1.0"
```

그리고 **이미지를 어디에 올렸느냐에 따라** 아래 한 곳이 갈립니다.

| 이미지를 올린 곳 | `imagePullSecrets` |
|---|---|
| 내 계정 (저장소가 **공개**) | `[]` — 비워 둡니다. 자격증명이 필요 없습니다 |
| 프로젝트 조직 | `- name: gitea-image-pull-secret-runway-bot-token` |

내 계정 + 공개인 경우:

```yaml
imagePullSecrets: []
```

**정말로 자격증명 없이 받아지는지 지금 확인해 두면** 배포 때 헤매지 않습니다.

```bash
curl -s -o /dev/null -w "%{http_code}" https://gitea.<도메인>/v2/<계정 또는 조직>/llm-tutorial/tags/list; echo
```

| 나온 값 | 뜻 | 할 일 |
|---|---|---|
| `200` | 익명으로 받아집니다 | 그대로 진행 |
| `401` | 아직 비공개입니다 | Gitea → 저장소 → Settings에서 공개로 바꾸세요 |
| `404` | 이미지가 아직 없습니다 | 5)의 Actions가 성공했는지 확인 |

`401` 인 채로 배포하면 파드가 `ImagePullBackOff` 로 멈춥니다. 메시지만 봐서는
원인이 잘 안 보이는 오류라, 여기서 미리 걸러 두는 편이 낫습니다.

### 7) 차트 올리기

저장소에 들어 있는 스크립트가 묶어서 올려 줍니다. **helm이 없어도 됩니다.**

```bash
GITEA_HOST=gitea.<도메인> GITEA_USER=<계정> GITEA_OWNER=<프로젝트 ID> \
  scripts/package-chart.sh
```

토큰을 물으면 붙여 넣으세요. 끝나면 마지막 줄에 **등록할 주소**가 나옵니다.

```
https://gitea.<도메인>/api/packages/<프로젝트 ID>/helm
```

이 주소를 [0-1 템플릿 ②](../00-preparation/01-keys.md)의 `차트 리포지토리` 줄에
적어 두세요. 바로 아래에서 씁니다.

> **이 주소를 브라우저로 열면 404가 나는 것이 정상입니다.** Helm 리포지토리는 사람이
> 볼 페이지를 갖고 있지 않습니다. 스크립트가 마지막에 `index.yaml` 을 보여 주는데,
> 거기 `entries:` 아래에 `llm-tutorial` 과 버전이 보이면 제대로 올라간 것입니다.

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

템플릿 ②의 **`차트 리포지토리`** 줄을 그대로 붙여 넣고 **저장**을 누릅니다.

```
https://<계정>.github.io/runway-llm-tutorial
```

`<계정>` 은 이 튜토리얼 저장소가 올라간 GitHub 계정 이름입니다.
사내 Gitea에 올려 두었다면 [부록 A](../appendix/a-self-build.md)의 주소를 넣으세요.

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

> 여기 적는 값은 **비밀이 아닌 것들**입니다 — PVC 이름, 창고 주소, 엔진 이름.
> 비밀(`LLM_API_KEY`)은 0-2에서 OpenBao에 넣었고 여기 적지 않습니다.
> 왜 그렇게 나뉘는지는 [0-2의 설명](../00-preparation/02-openbao.md)에 있습니다.

```yaml
runway:
  openbao:
    secretEngine: "tutorial"        # 템플릿 ②의 '시크릿 엔진'
    secretName: "llmchat"           # 템플릿 ②의 '시크릿 이름'

  vector:
    enabled: true
    url: "http://qdrant.<프로젝트 ID>.svc.cluster.local:6333"   # 템플릿 ②의 '창고 주소'

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

  access:
    passwordRequired: false   # 5단계에서 켭니다

  certs:
    enabled: false            # 사설 인증서 설치본에서만 켭니다

  httpRoute:
    enabled: false            # 5단계에서 켭니다
    hostnames: []
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

imagePullSecrets: []
nameOverride: ""
fullnameOverride: ""
extraEnv: []
podAnnotations: {}
nodeSelector: {}
tolerations: []
affinity: {}
```

`vector.url` 의 `<프로젝트 ID>` 한 곳만 내 값으로 바꿉니다.

> **이미지 주소와 태그는 여기 없습니다.** 차트를 만들 때 이미 박아 두었기 때문입니다
> (3-1의 6단계). 여기에 또 적을 필요가 없습니다.

> ⚠ **덧붙이지 말고 지우고 넣으세요.** 같은 키가 두 번 있으면 YAML은 **뒤에 나온 것을**
> 씁니다. 앞에 적은 값이 오류 없이 무시되고, 증상은 "설정했는데 동작하지 않는다"로
> 나타납니다.

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
> 호스트명에 대문자가 있거나, 창고 주소 끝에 `/` 가 붙어 있으면 그 자리에서
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

← [2-2. 창고 연결 확인](../02-vector-db/02-verify.md) | 다음: [3-2. 상태 확인 →](02-status.md)
