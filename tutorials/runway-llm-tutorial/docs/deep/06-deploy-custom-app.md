# Stage 5 — 커스텀 애플리케이션으로 배포

> **이 단계가 끝나면**
> - 챗봇이 Code Server 밖에서, 자기 파드로 돕니다
> - Runway 애플리케이션 목록에 Qdrant·Code Server와 나란히 보입니다
> - 시크릿은 여전히 OpenBao에서 옵니다

소요 60분. **이 단계에 함정이 가장 많습니다.** 순서를 지키세요.

---

## 5-1. 전체 순서

```
1. 차트 확인          → helm template 로 렌더 검증
2. 이미지 빌드·push   → Gitea 컨테이너 레지스트리 (프로젝트 조직 밑!)
3. 차트 패키징·업로드 → Gitea Helm 레지스트리
4. index.yaml 확인    → 여기서 안 보이면 등록도 안 됩니다
5. 리포지토리 등록    → 애플리케이션 생성 폼 안에서
6. 애플리케이션 생성  → 차트/버전/values/열기링크
7. 배포               → 상세 페이지의 배포 버튼
```

**2번과 3번은 다른 레지스트리입니다.** 이미지와 차트는 서로 다른 곳에 올라갑니다.

---

## 5-2. Gitea 준비

### 로그인부터

프로젝트 Gitea 조직은 비공개라 **비로그인 상태에서는 무조건 404**입니다.

더 중요한 것: 조직 멤버십은 **OIDC 로그인 시점에** 그룹-팀 맵이 적용되어 만들어
집니다. Gitea에 SSO로 한 번도 로그인한 적이 없으면 어느 팀에도 속하지 않아 조직이
아예 안 보입니다.

> **조직이나 저장소가 404일 때 가장 먼저 의심할 것이 이것입니다.**
> 콘솔 → Built-in Apps → Gitea 카드로 들어가면 SSO 경로를 탑니다.

### PAT 발급 — 스코프가 작업마다 다릅니다

Gitea → 우측 상단 → Settings → Applications → Generate Token.

| 작업 | 필요한 스코프 |
|---|---|
| clone (읽기) | `read:repository` |
| push | `write:repository` |
| 저장소 생성 | `write:repository` |
| **차트 업로드** | **`write:package`** |
| 차트 조회 (등록 시) | `read:package` |

**차트 업로드는 저장소가 아니라 패키지 레지스트리에 쓰는 동작입니다.**
`write:repository`만 있는 토큰으로는 안 되고, 실패 메시지가 `authGroup.Verify`처럼
불친절하게 나와서 원인을 알기 어렵습니다.

이 튜토리얼은 `write:repository` + `write:package` 둘 다 켜세요.

### 토큰을 URL에 넣지 마세요

```bash
read -s GITEA_PAT && export GITEA_PAT
```

`https://user:token@host/...` 형태는 셸 히스토리와 `.git/config`에 남습니다.
**Code Server의 홈은 영속 볼륨이라 재시작해도 남습니다.**

`export`한 변수는 그 셸에서만 삽니다. 새 터미널을 열면 다시 넣어야 합니다.
비어 있는 채로 `curl --user user:$GITEA_PAT`를 실행하면 빈 비밀번호로 나가 인증
실패하는데, 증상이 "토큰이 틀렸다"로 보입니다.

---

## 5-3. 차트 확인

먼저 렌더가 되는지 봅니다. **아무 값도 안 주면 거부되는 것이 정상입니다.**

```bash
cd ~/work/runway-llm-tutorial
helm template t ./chart
```

```
Error: ... image.repository가 비어 있습니다. 예) gitea.<도메인>/<프로젝트조직>/llm-tutorial
  개인 계정이 아니라 프로젝트 조직 네임스페이스여야 합니다 ...
```

[`chart/templates/check-values.yaml`](../../chart/templates/check-values.yaml)이 하는
일입니다. **설정 오류를 렌더 단계에서 잡습니다.**

같은 오류를 런타임까지 끌고 가면 Pod은 정상적으로 뜨고 사용자의 첫 클릭에서
죽습니다. 그때는 클러스터에 객체가 이미 만들어져 있고, Argo CD는 Healthy로 보이고,
로그를 파고 들어가야 원인이 나옵니다.

몇 가지를 일부러 틀려 보세요:

```bash
B="--set image.repository=r --set image.tag=1 --set runway.llm.model=m \
   --set runway.openbao.secretEngine=tutorial --set runway.openbao.secretName=llmchat"

# 대문자 호스트명
helm template t ./chart $B --set runway.httpRoute.enabled=true \
  --set runway.httpRoute.hostnames[0]=Chat.Example.com

# 포트 불일치
helm template t ./chart $B --set runway.httpRoute.enabled=true \
  --set runway.httpRoute.hostnames[0]=chat.example.com --set runway.httpRoute.targetPort=8080

# 로컬 임베딩인데 스토리지 없음
helm template t ./chart $B --set runway.vector.enabled=true \
  --set runway.vector.url=http://q:6333 --set runway.embedding.provider=local
```

전부 이유를 대며 막힙니다. 마지막 것이 **조합 검사**의 예입니다 — 값 하나씩은
멀쩡한데 같이 쓰면 말이 안 되는 경우입니다.

### 실제 값으로 렌더해 보기

`my-values.yaml`을 만듭니다 (**커밋하지 마세요**):

```yaml
image:
  repository: gitea.<도메인>/<프로젝트 ID>/llm-tutorial
  tag: "0.1.0"

runway:
  llm:
    baseUrl: "http://litellm.runway-applications.svc.cluster.local:4000/v1"
    # model 은 비워 두면 앱이 게이트웨이에 물어봅니다. 고정하고 싶을 때만 적으세요.
    # model: "<Stage 0에서 확인한 이름>"
    systemPrompt: "너는 사내 문서를 근거로 답하는 도우미다. 문서에 없으면 모른다고 말한다."

  openbao:
    secretEngine: "tutorial"
    secretName: "llmchat"

  vector:
    enabled: true
    url: "http://qdrant.<프로젝트 ID>.svc.cluster.local:6333"
    collection: "tutorial-docs"

  embedding:
    provider: "auto"
    gatewayModel: ""          # 게이트웨이에 임베딩 모델이 있으면 이름을 넣으세요

  # 외부 노출은 일단 끕니다. 5-8에서 다시 이야기합니다.
  httpRoute:
    enabled: false
```

```bash
helm template llm-tutorial ./chart -f my-values.yaml | head -60
```

OpenBao 어노테이션이 이렇게 나와야 합니다:

```yaml
vault.hashicorp.com/agent-inject: "true"
vault.hashicorp.com/role: "default"
vault.hashicorp.com/namespace: "<프로젝트 ID>"
vault.hashicorp.com/agent-inject-secret-llmchat.env: "tutorial/data/llmchat"
```

`tutorial/data/llmchat` — **`/data/`는 차트가 붙였습니다.** 값에는 엔진 이름과
시크릿 이름만 넣었습니다.

---

## 5-4. 이미지 빌드

Code Server에는 도커 CLI는 있어도 **데몬이 없습니다.** 권한 없는 파드라 띄울 수도
없습니다. 선택지는 둘입니다.

### 방법 A — Gitea Actions (클러스터 안에서)

플랫폼이 dind 사이드카가 붙은 러너를 이미 깔아 두었습니다.

먼저 **러너가 사는지 확인**하세요. 러너는 자기 이미지를 강제로 다시 받으므로,
미러가 설정되지 않은 설치본에서는 job이 큐에서 움직이지 않습니다. 아무 워크플로나
하나 돌려 보고 경로를 정하는 편이 시간을 아낍니다.

저장소 만들기:

```bash
curl -X POST "https://gitea.<도메인>/api/v1/orgs/<프로젝트 ID>/repos" \
  -H "Authorization: token $GITEA_PAT" -H "Content-Type: application/json" \
  -d '{"name":"llm-tutorial","private":true,"auto_init":false}'
```

> **`auto_init: false`가 중요합니다.** `true`면 원격에 초기 커밋이 생겨 첫 push가
> 거부됩니다. 웹 UI로 만들 때도 README/.gitignore/라이선스를 체크하지 마세요.
>
> 조직에 만들 권한이 없어 403이 나면 `/api/v1/user/repos`로 개인 계정 밑에
> 만드세요. **차트는 개인 계정이어도 됩니다. 이미지는 안 됩니다** (아래 참고).

push:

```bash
cd ~/work/runway-llm-tutorial
git remote add origin https://gitea.<도메인>/<프로젝트 ID>/llm-tutorial.git
git add -A && git commit -m "tutorial app"
git push -u origin main       # 사용자명과 PAT를 물어봅니다
```

워크플로 파일 `.gitea/workflows/build.yaml`:

```yaml
name: build-image
on:
  push:
    tags: ["v*"]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Log in
        run: echo "${{ secrets.GITEA_TOKEN }}" | docker login "${{ vars.REGISTRY }}" -u "${{ vars.REGISTRY_USER }}" --password-stdin
      - name: Build and push
        run: |
          IMAGE="${{ vars.REGISTRY }}/${{ vars.ORG }}/llm-tutorial:${GITHUB_REF_NAME#v}"
          docker build -t "$IMAGE" app/
          docker push "$IMAGE"
```

> **그럴듯한 기본값을 두지 마세요.** `${{ vars.REGISTRY || 'gitea.example.com' }}`
> 같은 폴백을 뒀다가 변수를 빠뜨리면 `dial tcp: lookup gitea.example.com: no such
> host`가 납니다. **설정 누락이 네트워크 장애처럼 보입니다.** 미설정은 이름을 대며
> 즉시 실패하는 편이 낫습니다.

저장소 Settings → Actions에서 `REGISTRY`, `REGISTRY_USER`, `ORG` 변수와
`GITEA_TOKEN` 시크릿을 넣고 태그를 밀면 빌드가 돕니다.

### 방법 B — 도커가 도는 다른 머신

노트북에 도커가 있으면 그냥 거기서:

```bash
docker build -t gitea.<도메인>/<프로젝트 ID>/llm-tutorial:0.1.0 app/
docker login gitea.<도메인>
docker push gitea.<도메인>/<프로젝트 ID>/llm-tutorial:0.1.0
```

### 이미지에 대한 두 가지 경고

> ⚠ **이미지는 프로젝트 조직 네임스페이스에 올리세요.**
>
> 프로젝트의 `gitea-image-pull-secret-runway-bot-token`은 **조직 봇 계정**
> 자격증명이라 권한이 조직 범위에만 있습니다. 개인 계정
> (`gitea.<도메인>/<사용자>/...`) 밑에 push하면 봇이 못 읽어 파드가
> `ImagePullBackOff` + 401 로 멈춥니다.
>
> Helm 차트는 개인 계정에 올려도 됩니다(Argo CD가 사용자 자격증명으로 등록).
> **컨테이너 이미지는 다릅니다.**

> ⚠ **태그를 재사용하지 마세요.**
>
> kubelet은 이미 받아 둔 이미지를 다시 받지 않습니다(`imagePullPolicy:
> IfNotPresent`). 같은 태그로 다시 빌드해 push하면 레지스트리만 바뀌고 **노드는 옛
> 이미지를 계속 씁니다.** 게다가 파드 이벤트에는 `Pulled - already present on
> machine`이 찍혀서 성공처럼 보입니다.
>
> 증상이 "코드를 고쳤는데 반영이 안 된다"로 나타나므로 원인을 코드에서 찾게
> 됩니다. 고칠 때마다 태그를 올리세요.

---

## 5-5. 차트 패키징과 업로드

```bash
cd ~/work/runway-llm-tutorial
GITEA_HOST=gitea.<도메인> GITEA_USER=<계정> GITEA_OWNER=<프로젝트 ID 또는 계정> \
  scripts/package-chart.sh
```

수동으로 하면:

```bash
helm package ./chart
curl -i --user <계정>:$GITEA_PAT -X POST \
  --upload-file llm-tutorial-0.1.0.tgz \
  "https://gitea.<도메인>/api/packages/<owner>/helm/api/charts"
```

helm이 없어도 됩니다. 규칙은 두 가지뿐입니다 — **아카이브 루트 디렉터리 이름 =
`Chart.yaml`의 `name`**, **파일명 = `<name>-<version>.tgz`**.

```bash
rm -rf /tmp/pkg && mkdir -p /tmp/pkg/llm-tutorial
cp -r ./chart/* /tmp/pkg/llm-tutorial/
tar -czf llm-tutorial-0.1.0.tgz -C /tmp/pkg llm-tutorial
```

### 확인 — 이게 되면 리포지토리로서 완전합니다

```bash
curl -s --user <계정>:$GITEA_PAT \
  "https://gitea.<도메인>/api/packages/<owner>/helm/index.yaml"
```

```yaml
entries:
  llm-tutorial:
    - apiVersion: v2
      name: llm-tutorial
      version: 0.1.0
      ...
```

**여기서 안 보이면 등록도 안 됩니다.** 먼저 이걸 통과시키세요.

### URL 세 가지를 혼동하지 마세요

| 용도 | URL |
|---|---|
| **등록** (폼에 넣을 값) | `https://gitea.<도메인>/api/packages/<owner>/helm` |
| 업로드 | 위 + `/api/charts` |
| 사람이 보는 페이지 | `https://gitea.<도메인>/<owner>/-/packages` |

> **등록 URL을 브라우저로 열면 404가 나는 것이 정상입니다.** Helm 리포지토리는
> 베이스 경로에 페이지를 서빙하지 않습니다. `<url>/index.yaml`만 있으면 됩니다.
> 웹 UI 페이지 URL을 등록하면 HTML이 돌아와 파싱에 실패합니다.
>
> `.git`을 붙이거나 `/index.yaml`을 붙이지도 마세요.

---

## 5-6. 리포지토리 등록

**애플리케이션** → **생성** → 템플릿 목록 옆의 **리포지토리 등록**.

| 필드 | 값 |
|---|---|
| URL | `https://gitea.<도메인>/api/packages/<owner>/helm` |
| Username | Gitea 계정명 |
| Password | PAT (`read:package` 이상) |

> ⚠ **URL을 확정한 뒤에 한 번에 등록하세요.**
>
> 콘솔에는 리포지토리 삭제 UI가 없고, 같은 URL 재등록은 `REPOSITORY_EXISTS`로
> 막힙니다. 삭제는 API나 Argo CD UI에서만 됩니다.

### 실패 코드 읽는 법

| 코드 | 뜻 | 볼 곳 |
|---|---|---|
| `AUTHENTICATION_FAILED` | 자격증명 거부 | 사용자명/PAT, 스코프 |
| `REPOSITORY_USERNAME_REQUIRED` | 쌍으로 안 넣음 | 둘 다 채우기 |
| `CONNECTION_FAILED` | **닿지 못함** | TLS, DNS, egress |
| `REPOSITORY_EXISTS` | 같은 URL이 이미 등록됨 | 위 경고 참고 |

`CONNECTION_FAILED`는 인증 실패와 **다른 코드**입니다. 이게 뜨면 자격증명을 아무리
고쳐도 소용없습니다.

**연결하는 주체가 Argo CD라는 점이 핵심입니다.** 등록 시 접속을 시도하는 것은
브라우저도, Code Server 파드도 아니라 클러스터 안의 Argo CD입니다. 내 쪽에서
`curl`이 된다고 등록이 되는 것이 아닙니다 — CA 번들이 컨테이너마다 다릅니다.

### 우회 경로 — Argo CD UI에서 직접 등록

콘솔 등록이 `CONNECTION_FAILED`로 막히면 Argo CD에서 직접 넣을 수 있습니다.
**이렇게 등록한 리포지토리는 Runway 애플리케이션 생성 폼의 목록에 그대로
나타납니다.**

`https://argocd.<도메인>` → Settings → Repositories → CONNECT REPO

| 필드 | 값 |
|---|---|
| Connection method | VIA HTTPS |
| **Type** | **helm** ← 기본값이 `git`이므로 반드시 변경 |
| Name | `llm-tutorial` |
| **Project** | **Runway 프로젝트 ID** |
| Repository URL | `https://gitea.<도메인>/api/packages/<owner>/helm` |
| Username / Password | 계정명 / PAT |
| Skip server verification | TLS 문제 진단 시 체크 |

이 화면은 콘솔이 뭉뚱그린 원인을 **문자열 그대로** 보여 줍니다.

- `x509: certificate signed by unknown authority` → TLS
- `dial tcp: lookup ... no such host` → DNS
- 타임아웃 → egress

---

## 5-7. 애플리케이션 생성

**애플리케이션** → **생성** → 방금 등록한 리포지토리의 `llm-tutorial` 차트.

| 필드 | 값 | 제한 |
|---|---|---|
| 이름 | `LLM 튜토리얼 챗봇` | 128자 |
| **ID** | `llm-tutorial` | 3~53자, **30자 안쪽 권장**, 편집 불가 |
| 차트 버전 | `0.1.0` | |
| Values | 5-3에서 만든 `my-values.yaml` 내용 | |

ID 규칙: `[a-z0-9-]`만, 시작/끝은 영소문자나 숫자, 숫자만으로는 안 됩니다.

> **ID를 짧게.** 차트가 만드는 리소스에 접미사가 붙고 쿠버네티스 이름 상한이
> 63자입니다. 실제 사례로 39자 ID + 27자 접미사 = 66자가 되어 sync가 실패한 적이
> 있습니다. 콘솔은 53자까지 받지만 접미사를 고려하지 않습니다.

### 의존성 카드는 값을 넣어 주지 않습니다

생성 드로어의 `Dependencies (의존성)` 카드는 **안내일 뿐 피커가 아닙니다.**
후보를 골라도 values에는 아무것도 들어가지 않습니다. 콘솔 자신이 그렇게 적어
두었습니다 — "연동 정보의 값을 복사하여 values.yaml의 해당 필드에 입력하세요."

"골랐는데 왜 안 되지"로 시간을 버리기 딱 좋은 지점입니다.

### 애플리케이션 열기 링크 — 빼먹지 마세요

Runway는 차트의 `runway.httpRoute.hostnames`를 **읽지 않습니다.** 콘솔은 그 값을
읽어오지도, 대조하지도 않습니다.

**애플리케이션 열기 링크** 섹션에 이름/URL 쌍을 직접 입력해야 **열기(Open)** 버튼이
생깁니다. 즉 호스트명을 두 군데에 따로 입력하는 구조이고, 한쪽만 고치면 버튼이
엉뚱한 곳으로 갑니다. (외부 노출을 껐다면 이 섹션은 비워 두세요.)

---

## 5-8. 배포와 확인

상세 페이지 → **배포(Deploy)**.

```bash
kubectl -n <프로젝트 ID> rollout status deploy/llm-tutorial
kubectl -n <프로젝트 ID> logs deploy/llm-tutorial --tail=50
```

로그에서 볼 세 줄:

```
INFO llmchat.config read injected secret /vault/secrets/llmchat.env
INFO llmchat 설정 로드 완료 — model=... vector=on mcp=on
INFO llmchat.mcp MCP 서버 기동: 5개 툴 — search_documents, ...
```

첫 줄이 없으면 OpenBao 주입이 안 된 것이고, 셋째 줄이 없으면 MCP 자식 프로세스가
못 뜬 것입니다.

접근:

```bash
kubectl -n <프로젝트 ID> port-forward svc/llm-tutorial 8080:80
```

`http://localhost:8080` — 문서를 올리고 물어보세요.

### 외부로 열기 전에

> ⚠ **애플리케이션 호스트명 앞에는 Keycloak 로그인이 붙지 않습니다.**
>
> 플랫폼의 로그인 강제는 호스트별 규칙으로 열거되어 있고, 기본 설치에는 네 개뿐
> 입니다 — 콘솔, 워크스페이스, MLflow API 경로, 추론 엔드포인트. **애플리케이션
> 호스트명은 어디에도 포함되지 않습니다.**
>
> 정적 페이지라면 사소한 문제지만, **이 앱은 토큰을 씁니다.** 호스트명을 아는
> 사람은 누구나 프로젝트의 LLM 예산을 쓰고, 올려 둔 문서를 검색할 수 있습니다.

방어 두 가지, 그리고 둘은 겹쳐 씁니다.

**1) 외부 노출을 끄고 port-forward로 쓰기.** 기본값입니다.

**2) 공유 비밀번호.** OpenBao 시크릿에 `ACCESS_PASSWORD`를 추가하면 앱이 자동으로
요구합니다. values에서 명시하려면:

```yaml
runway:
  access:
    passwordRequired: true
  httpRoute:
    enabled: true
    hostnames:
      - "llm-tutorial.<도메인>"      # 소문자만
```

공유 비밀번호는 **신원이 아닙니다.** 지나가던 사용을 막을 뿐, 누가 무엇을 물었는지는
알려 주지 않습니다. 그래도 아무것도 없는 것보다는 낫습니다.

---

## 여기까지 되면 성공

- [ ] `index.yaml` 에 `llm-tutorial` 과 `0.1.0` 이 보인다
- [ ] 리포지토리가 등록되고 생성 폼에서 차트가 보인다
- [ ] 애플리케이션이 `Healthy` 다
- [ ] 로그에 `read injected secret` 과 `MCP 서버 기동` 이 있다
- [ ] port-forward로 열어 문서 기반 답변을 받았다
- [ ] 외부 노출을 켰다면 그 의미를 알고 켰다

---

## 막히면

| 증상 | 원인 | 조치 |
|---|---|---|
| sync 실패 + 63자 초과 | ID가 김 | 짧은 ID로 재생성 (편집 불가) |
| sync 실패 + 호스트명 정규식 | 대문자 | 소문자로 |
| 등록 `CONNECTION_FAILED` | Argo CD가 닿지 못함 | Argo CD UI 수동 등록 (5-6) |
| 등록 `AUTHENTICATION_FAILED` | PAT 스코프 | `read:package` 확인 |
| Gitea 조직 404 | 비로그인 / 팀 미배정 | **SSO 재로그인** |
| 차트 업로드 `authGroup.Verify` | 빈 토큰 또는 `write:package` 없음 | 변수와 스코프 확인 |
| `ImagePullBackOff` + 401 | 이미지를 개인 계정에 push | 조직 네임스페이스로 |
| 코드 고쳤는데 반영 안 됨 | 같은 태그 재사용 | 태그를 올리세요 |
| `FailedMount: secret` | 없는 CA Secret 마운트 | `runway.certs.enabled=false` 또는 Secret 존재 확인 |
| 배포해도 아무것도 없음 | 배포 버튼 미클릭 | 상세 페이지 |
| 열기 버튼 없음 | 열기 링크 미입력 | 생성 폼 |
| `exceeded quota` | 프로젝트 자원 부족 | `describe resourcequota` |

---

← [05. 벡터 DB (Qdrant)](05-vector-db-qdrant.md) | [99. 문제 해결 →](99-troubleshooting.md)
