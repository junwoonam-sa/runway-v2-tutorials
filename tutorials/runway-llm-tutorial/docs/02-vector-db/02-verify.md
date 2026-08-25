# 2-2. 창고 연결 확인

방금 만든 창고 주소가 실제로 통하는지 확인합니다.

걸리는 시간 3분 · 명령어 한 줄.

---

## 왜 지금 확인하나

3단계에서 챗봇 설정에 이 주소를 적습니다. 주소가 틀리면 챗봇은 뜨지만 문서 기능만
동작하지 않고, 그때 원인이 "주소 오타"인지 다른 것인지 가리는 데 시간이 걸립니다.

**여기서 3분 쓰면 나중에 그 시간을 아낍니다.**

---

## 확인하기

1-2에서 만든 Code Server의 터미널을 엽니다
(**Terminal → New Terminal**).

아래 줄에서 `<프로젝트 ID>` 만 내 것으로 바꿔 붙여 넣습니다.

```bash
curl -s http://qdrant.<프로젝트 ID>.svc.cluster.local:6333/collections
```

이렇게 나오면 정상입니다.

```json
{"result":{"collections":[]},"status":"ok","time":0.00001}
```

`collections` 가 **비어 있는 것이 맞습니다** — 아직 문서를 하나도 안 올렸으니까요.
4단계에서 문서를 올리면 여기 이름이 생깁니다.

---

## 안 나온다면

| 나온 것 | 원인 | 할 일 |
|---|---|---|
| 아무 응답 없이 멈춤 | 주소가 틀림 | Qdrant의 **ID**와 **프로젝트 ID**를 다시 확인 |
| `Could not resolve host` | 주소 철자 오류 | `.svc.cluster.local` 까지 정확히 들어갔는지 확인 |
| `Connection refused` | Qdrant가 아직 안 뜸 | 애플리케이션 목록에서 `Healthy` 인지 확인 |

주소를 만들 때 자주 나는 실수:

```
❌ http://qdrant.svc.cluster.local:6333              프로젝트 ID 빠짐
❌ http://qdrant.my-project.svc.cluster.local        포트 빠짐
❌ https://qdrant.my-project.svc.cluster.local:6333  https 아님
✅ http://qdrant.my-project.svc.cluster.local:6333
```

Qdrant의 ID를 `qdrant` 가 아닌 다른 이름으로 만들었다면, 그 이름이 맨 앞에 들어갑니다.

---

## 여기까지 되면 성공

- [ ] `curl` 명령이 `{"result":{"collections":[]}...}` 를 돌려준다

---

← [2-1. Qdrant 배포](01-deploy.md) | 다음: [3-1. 챗봇 배포 →](../03-chatbot/01-deploy.md)
