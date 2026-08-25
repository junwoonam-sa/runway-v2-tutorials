# Stage 1 — 스토리지와 Code Server

> **이 단계가 끝나면**
> - PVC를 하나 만들었습니다
> - 브라우저에서 열리는 개발 환경(Code Server)이 있습니다
> - Stage 0에서 저장한 시크릿이 **파일로 주입되는 것을 눈으로 확인**했습니다
> - 튜토리얼 코드를 그 안에 가져다 두었습니다

소요 40분.

---

## 1-1. 스토리지 만들기

Runway의 **스토리지**는 프로젝트 네임스페이스의 PersistentVolumeClaim입니다.
콘솔이 "볼륨"과 "스토리지" 두 이름을 섞어 쓰는데 같은 것입니다.

좌측 메뉴 **스토리지(Storage)** → **생성(Create)**. 필드는 네 개뿐입니다.

| 필드 | 넣을 값 | 규칙 |
|---|---|---|
| 볼륨 ID | `llm-tutorial-data` | 3~63자, 소문자·숫자·하이픈, 시작과 끝은 영소문자나 숫자 |
| 스토리지 클래스 | 기본값 그대로 | 클러스터가 가진 목록입니다 |
| 접근 모드 | `ReadWriteOnce` | |
| 크기 | `5` | 단위는 GiB 고정 |

몇 가지 알아 둘 것:

- **이름은 나중에 못 바꿉니다.** 크기만, 그것도 늘리는 방향으로만 바꿀 수 있습니다.
- **크기 옆의 숫자는 프로젝트 남은 용량**입니다. 그걸 넘겨도 폼은 통과할 수 있고,
  진짜 한도는 네임스페이스 쿼터입니다 — 초과하면 `STORAGE_QUOTA_EXCEEDED`가 납니다.
- **`ceph-block` 클래스에는 ReadWriteMany를 못 씁니다.** 폼이 막습니다. RWX가
  필요하면 파일시스템 계열 클래스를 고르세요. 이 튜토리얼은 RWO로 충분합니다.
- 상태가 `Pending`에 머무르면 스토리지 클래스가 그 요청을 프로비저닝하지 못하는
  것입니다. 목록은 pending이 있는 동안 5초마다 갱신됩니다.

이 볼륨은 Stage 4에서 **로컬 임베딩 모델의 캐시**를 두는 데 씁니다. 게이트웨이
임베딩만 쓸 거라면 없어도 되지만, 만들어 두면 선택지가 열려 있습니다.

---

## 1-2. Code Server 설치

**애플리케이션(Applications)** → **생성** → 템플릿에서 **Code Server**.

### 폼에서 채울 것

| 그룹 | 필드 | 값 |
|---|---|---|
| 기본 | 이름 | `code-server` |
| 기본 | **ID** | `code-server` — **30자 안쪽**으로 |
| 네트워크 | 외부 접근(HTTPRoute) | 켬 |
| 네트워크 | 호스트명 | `code-<프로젝트>.<도메인>` — **소문자만** |
| 리소스 | CPU/메모리 | 요청 500m / 1Gi 정도면 충분 |
| 스토리지 | persistence | 기본값 유지 (10Gi, `/home/coder`) |
| 시크릿 | OpenBao 엔진 | `tutorial` |
| 시크릿 | OpenBao 시크릿 이름 | `llmchat` |

> **ID를 짧게 잡으세요.** 콘솔은 53자까지 받지만, 차트가 만드는 리소스에 접미사가
> 붙고 쿠버네티스 이름 상한이 63자입니다. ID가 길면 sync가 실패하고, ID는 생성 후
> 편집이 안 됩니다.

> **호스트명에 대문자를 쓰지 마세요.** Gateway API가 정규식으로 거부하고, 그 실패는
> Argo CD sync 오류로 나타나 원인을 찾기 어렵습니다.

### 알아 둘 것

- **`/home/coder`는 경로를 못 바꿉니다.** 상위 차트가 고정해 두었고, `mountPath`를
  써도 조용히 무시됩니다. 다른 경로에 볼륨이 필요하면 `extraPVCs`를 씁니다.
- **홈이 영속 볼륨입니다.** `~/.local/bin`에 설치한 것, `~/.bashrc` 수정, 클론한
  저장소가 파드 재시작 후에도 남습니다. 뒤에서 이 성질을 씁니다.
- 첫 기동이 30~40초 걸릴 수 있습니다(확장 프로그램 시딩). startup probe의 하한이
  그래서 있는 것이니, 조금 기다리세요.

### 만든 뒤 — 배포

생성 폼을 제출하면 상태가 `terminated`입니다. **상세 페이지에서 배포(Deploy)** 를
누르세요. 이걸 눌러야 실제로 워크로드가 뜹니다.

`Healthy`가 되면 **열기(Open)** 를 누릅니다.

> 열기 버튼이 없다면, 생성 폼의 **애플리케이션 열기 링크** 섹션에 이름/URL 쌍을
> 넣지 않은 것입니다. Runway는 차트의 hostnames를 읽지 않습니다 — 호스트명을 두
> 군데에 각각 입력하는 구조입니다.

---

## 1-3. 시크릿이 주입되었는지 확인 — 이 단계의 핵심

Code Server의 터미널을 엽니다 (`Ctrl+``  또는 메뉴 → Terminal → New Terminal).

```bash
ls -l /vault/secrets/
cat /vault/secrets/llmchat.env
```

```
LLM_API_KEY=sk-...
```

**이게 보이면 Stage 0이 제대로 된 것입니다.** 값이 코드에도 이미지에도 없이,
파드가 뜰 때 파일로 들어왔습니다.

셸에서 바로 쓰려면:

```bash
set -a && . /vault/secrets/llmchat.env && set +a
echo "${LLM_API_KEY:0:6}…"     # 앞 6자만 — 전체를 찍지 마세요
```

### 파일이 없다면

| 증상 | 원인 |
|---|---|
| `/vault/secrets` 디렉터리 자체가 없음 | 폼의 OpenBao 두 필드 중 하나가 비었음. 둘 다 채워야 주입이 켜집니다 |
| 디렉터리는 있는데 파일이 없음 | 엔진 이름이나 시크릿 이름 오타. OpenBao UI에서 경로를 다시 확인 |
| 파드가 아예 안 뜸 (`FailedMount`) | ServiceAccount 토큰 볼륨 문제 — Code Server는 기본으로 켜져 있으므로 드묾 |

파드 이벤트를 보려면:

```bash
kubectl -n <프로젝트> describe pod -l app.kubernetes.io/instance=code-server | tail -30
```

---

## 1-4. 작업 환경 준비

### helm 설치

Code Server 이미지에는 helm이 없습니다. 홈이 영속 볼륨이므로 `~/.local/bin`에
설치하면 재시작 후에도 남습니다.

```bash
curl -fsSL https://get.helm.sh/helm-v3.16.3-linux-amd64.tar.gz \
  | tar -xz -C /tmp linux-amd64/helm \
  && mkdir -p ~/.local/bin && mv /tmp/linux-amd64/helm ~/.local/bin/helm
```

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc && export PATH="$HOME/.local/bin:$PATH"
helm version
```

외부 인터넷이 막혀 있으면 helm 없이도 됩니다 — Stage 5의
`scripts/package-chart.sh`가 tar로 직접 묶는 경로를 갖고 있습니다.

### 튜토리얼 코드 가져오기

```bash
mkdir -p ~/work && cd ~/work
git clone <이 저장소 주소> runway-llm-tutorial
cd runway-llm-tutorial
```

> **`~`에서 `git init`을 하지 마세요.** 홈 디렉터리 전체가 저장소가 됩니다.
> 증상은 `git mv` 같은 명령이 경로 앞에 폴더명을 덧붙이는 것입니다. 확인:
>
> ```bash
> git rev-parse --show-toplevel
> ```
>
> 프로젝트 폴더가 아니라 `/home/coder`가 나오면 잘못된 것입니다. 프로젝트 폴더에서
> `git init`을 다시 하면 안쪽 저장소가 우선하므로 파괴적 조작 없이 해결됩니다.

### Python 환경

```bash
python3 -m venv ~/work/venv
. ~/work/venv/bin/activate
pip install -r app/requirements.txt
```

`~/work`가 홈 아래라 이 venv도 재시작 후에 남습니다.

동작 확인:

```bash
cd app && python -m pytest -q
```

```
22 passed
```

---

## 여기까지 되면 성공

- [ ] 스토리지 목록에 `llm-tutorial-data` 가 `Bound` 상태로 있다
- [ ] Code Server가 `Healthy`이고 브라우저에서 열린다
- [ ] `cat /vault/secrets/llmchat.env` 가 `LLM_API_KEY=sk-...` 를 보여 준다
- [ ] `helm version` 이 동작한다
- [ ] `python -m pytest -q` 가 통과한다

---

## 막히면

| 증상 | 원인 | 조치 |
|---|---|---|
| 생성했는데 아무것도 안 뜸 | 배포 버튼 미클릭 | 상세 페이지 → 배포 |
| sync 실패 + 63자 초과 | ID가 김 | 더 짧은 ID로 다시 생성 (편집 불가) |
| sync 실패 + 호스트명 정규식 | 대문자 | 소문자로 |
| 열기 버튼 없음 | 열기 링크 미입력 | 생성 폼의 열기 링크 섹션 |
| `exceeded quota: requests.cpu` | 쿼터 부족 | `kubectl -n <프로젝트> describe resourcequota` |
| PVC가 `Pending` | 스토리지 클래스가 프로비저닝 못 함 | 다른 클래스로 다시 만들기 |
| `/vault/secrets` 없음 | OpenBao 두 필드 중 하나가 빔 | 둘 다 채우고 재배포 |

---

← [01. 환경 정보와 인증 키](01-openbao-and-keys.md) | 다음: [03. 챗봇 앱 만들기 →](03-chatbot-app.md)
