/*
 * 프런트엔드 — 빌드 단계 없음. 브라우저가 이 파일을 그대로 실행합니다.
 *
 * 서버가 보내는 것은 SSE 이벤트 스트림이고, 종류는 다섯입니다:
 *   token       답변 조각               → 말풍선에 이어 붙임
 *   tool_call   도구를 부르기 시작함     → 활동 줄 표시
 *   tool_result 도구 결과 요약           → 활동 줄에 접어 둠
 *   mode        도구 사용 방식이 바뀜     → 뱃지 갱신
 *   error/end   실패 / 스트림 종료
 *
 * 도구 활동을 굳이 화면에 보여 주는 이유: 에이전트가 "왜 그 답을 했는지"가 보여야
 * 튜토리얼로 의미가 있습니다. 감춰 두면 그냥 챗봇과 구별되지 않습니다.
 */

const state = {
  history: [],
  streaming: false,
  password: sessionStorage.getItem("accessPassword") || "",
  // 화면에서 적은 지시. 이 브라우저에만 남습니다 — 서버는 상태를 갖지 않습니다.
  systemPrompt: localStorage.getItem("systemPrompt") || "",
  controller: null,
};

const MAX_PROMPT_CHARS = 4000;   // 서버의 schemas.MAX_SYSTEM_PROMPT_CHARS 와 같은 값

const el = {
  chat: document.getElementById("chat"),
  empty: document.getElementById("empty-state"),
  input: document.getElementById("input"),
  send: document.getElementById("send"),
  stop: document.getElementById("stop"),
  composer: document.getElementById("composer"),
  modelName: document.getElementById("model-name"),
  toolMode: document.getElementById("tool-mode"),
  statusDot: document.getElementById("status-dot"),
  docsToggle: document.getElementById("docs-toggle"),
  promptToggle: document.getElementById("prompt-toggle"),
  promptPanel: document.getElementById("prompt-panel"),
  promptInput: document.getElementById("prompt-input"),
  promptSave: document.getElementById("prompt-save"),
  promptClear: document.getElementById("prompt-clear"),
  promptCount: document.getElementById("prompt-count"),
  statusToggle: document.getElementById("status-toggle"),
  statusPanel: document.getElementById("status-panel"),
  statusList: document.getElementById("status-list"),
  statusLabel: document.getElementById("status-label"),
  statusDotBadge: document.getElementById("status-dot-badge"),
  statusRefresh: document.getElementById("status-refresh"),
  blockedNote: document.getElementById("blocked-note"),
  docsPanel: document.getElementById("docs-panel"),
  docsList: document.getElementById("docs-list"),
  docsLog: document.getElementById("docs-log"),
  fileInput: document.getElementById("file-input"),
  passwordDialog: document.getElementById("password-dialog"),
  passwordInput: document.getElementById("password-input"),
};

const TOOL_MODE_LABEL = {
  "tool-calling": "도구 호출",
  "retrieval-fallback": "검색 주입(폴백)",
  none: "도구 없음",
};

const STATUS_LABEL = { ok: "준비됨", warn: "확인 필요", fail: "문제 있음" };

function headers(extra = {}) {
  const h = { ...extra };
  if (state.password) h["X-Access-Password"] = state.password;
  return h;
}

/* ---------------------------------------------------------------- 렌더링 */

function bubble(role) {
  el.empty?.remove();
  const node = document.createElement("div");
  node.className = `msg ${role}`;
  const body = document.createElement("div");
  body.className = "body";
  node.appendChild(body);
  el.chat.appendChild(node);
  el.chat.scrollTop = el.chat.scrollHeight;
  return body;
}

function activity(text, detail) {
  const node = document.createElement("details");
  node.className = "activity";
  const summary = document.createElement("summary");
  summary.textContent = text;
  node.appendChild(summary);
  if (detail) {
    const pre = document.createElement("pre");
    pre.textContent = detail;
    node.appendChild(pre);
  }
  el.chat.appendChild(node);
  el.chat.scrollTop = el.chat.scrollHeight;
  return node;
}

/* 아주 얕은 마크다운. 라이브러리를 들이지 않는 대신 인라인 코드, 굵게, 줄바꿈만.
   textContent로 먼저 넣고 정규식으로 감싸므로 원본 HTML은 실행되지 않습니다. */
function renderMarkdown(target, raw) {
  const escaped = raw
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  target.innerHTML = escaped
    .replace(/```([\s\S]*?)```/g, (_, code) => `<pre>${code.trim()}</pre>`)
    .replace(/`([^`\n]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\n/g, "<br />");
}

/* ------------------------------------------------------------------ 채팅 */

async function send(text) {
  if (state.streaming || !text.trim()) return;

  state.history.push({ role: "user", content: text });
  renderMarkdown(bubble("user"), text);

  state.streaming = true;
  el.send.disabled = true;
  el.stop.classList.remove("hidden");
  state.controller = new AbortController();

  // 답변 말풍선은 첫 토큰이 올 때 만듭니다. 미리 만들어 두면 도구 활동 줄이 그
  // 아래에 붙어, 실제로는 먼저 일어난 일이 나중에 일어난 것처럼 보입니다.
  let target = null;
  const ensureBubble = () => (target ??= bubble("assistant"));
  let answer = "";

  try {
    const response = await fetch("./api/chat", {
      method: "POST",
      headers: headers({ "Content-Type": "application/json" }),
      body: JSON.stringify({ messages: state.history, systemPrompt: state.systemPrompt }),
      signal: state.controller.signal,
    });

    if (response.status === 401) {
      await askPassword();
      state.history.pop();
      return;
    }
    if (response.status === 503) {
      // 서버가 "아직 준비 안 됨"이라고 답했습니다. 원인과 조치를 그대로 보여 줍니다.
      const { detail } = await response.json();
      const node = ensureBubble();
      node.classList.add("error");
      node.textContent = [detail.message, ...(detail.problems || []).map((p) => `· ${p.title}: ${p.detail}\n  → ${p.fix}`)].join("\n");
      await loadStatus({ autoOpen: true });
      state.history.pop();
      return;
    }
    if (!response.ok) throw new Error(`HTTP ${response.status}: ${await response.text()}`);

    for await (const event of readSSE(response)) {
      if (event.type === "token") {
        answer += event.text;
        renderMarkdown(ensureBubble(), answer);
        el.chat.scrollTop = el.chat.scrollHeight;
      } else if (event.type === "tool_call") {
        activity(`도구 호출: ${event.name}`, JSON.stringify(event.arguments, null, 2));
      } else if (event.type === "tool_result") {
        activity(`도구 결과: ${event.name}`, event.preview);
      } else if (event.type === "mode") {
        setToolMode(event.mode);
      } else if (event.type === "error") {
        const node = ensureBubble();
        node.classList.add("error");
        node.textContent = event.message;
      }
    }

    if (answer) state.history.push({ role: "assistant", content: answer });
  } catch (error) {
    if (error.name !== "AbortError") {
      const node = ensureBubble();
      node.classList.add("error");
      node.textContent = String(error);
    }
  } finally {
    state.streaming = false;
    state.controller = null;
    el.send.disabled = false;
    el.stop.classList.add("hidden");
  }
}

/* SSE를 직접 읽습니다. EventSource는 GET만 되고 헤더를 못 붙여서 쓸 수 없습니다. */
async function* readSSE(response) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary;
    while ((boundary = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      for (const line of frame.split("\n")) {
        if (!line.startsWith("data:")) continue;
        try {
          yield JSON.parse(line.slice(5).trim());
        } catch {
          /* 부분 프레임은 건너뜁니다 */
        }
      }
    }
  }
}

/* ------------------------------------------------------------------ 문서 */

async function refreshDocuments() {
  try {
    const response = await fetch("./api/documents", { headers: headers() });
    const data = await response.json();
    el.docsList.textContent = data.enabled === false ? data.text : data.text || "(없음)";
  } catch (error) {
    el.docsList.textContent = `목록을 불러오지 못했습니다: ${error}`;
  }
}

async function uploadFiles(files) {
  if (!files.length) return;
  const form = new FormData();
  for (const file of files) form.append("files", file);

  el.docsLog.textContent = "올리는 중…";
  try {
    const response = await fetch("./api/documents", { method: "POST", headers: headers(), body: form });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
    el.docsLog.textContent = data.results
      .map((r) => `${r.ok ? "✓" : "✗"} ${r.source} — ${r.message}`)
      .join("\n");
    await refreshDocuments();
  } catch (error) {
    el.docsLog.textContent = String(error);
  }
}

/* ------------------------------------------------------------------ 부팅 */

function setToolMode(mode) {
  el.toolMode.textContent = TOOL_MODE_LABEL[mode] || mode;
  el.toolMode.dataset.mode = mode;
}

/* 상태 —— 무엇이 준비됐고 무엇이 안 됐는지를 첫 화면에서 말해 주는 부분.
   문제가 있으면 저절로 펼칩니다. 감춰 두면 없는 기능처럼 보입니다. */
async function loadStatus({ autoOpen = false } = {}) {
  let status;
  try {
    status = await (await fetch("./api/status")).json();
  } catch (error) {
    el.statusLabel.textContent = "확인 실패";
    el.statusDotBadge.className = "state-dot fail";
    return;
  }

  el.statusLabel.textContent = STATUS_LABEL[status.overall] || status.overall;
  el.statusDotBadge.className = `state-dot ${status.overall}`;
  el.statusDot.classList.toggle("ok", status.overall !== "fail");
  el.statusDot.classList.toggle("bad", status.overall === "fail");

  el.statusList.replaceChildren(
    ...status.checks.map((check) => {
      const item = document.createElement("li");
      item.className = "status-item";

      const dot = document.createElement("span");
      dot.className = `state-dot ${check.state}`;

      const body = document.createElement("div");
      const title = document.createElement("h3");
      title.textContent = check.title;
      const detail = document.createElement("p");
      detail.textContent = check.detail;
      body.append(title, detail);

      if (check.fix && check.state !== "ok") {
        const fix = document.createElement("p");
        fix.className = "fix";
        fix.textContent = check.fix;
        body.append(fix);
      }

      item.append(dot, body);
      return item;
    }),
  );

  // 대화할 수 없으면 입력창을 막고 이유를 바로 아래에 적습니다.
  el.send.disabled = !status.chatReady || state.streaming;
  el.input.disabled = !status.chatReady;
  el.blockedNote.classList.toggle("hidden", status.chatReady);
  if (!status.chatReady) el.blockedNote.textContent = `대화를 시작할 수 없습니다 — ${status.summary}`;

  if (autoOpen && status.overall !== "ok") openStatus(true);
  return status;
}

function openStatus(open) {
  el.statusPanel.classList.toggle("hidden", !open);
  el.statusToggle.setAttribute("aria-expanded", String(open));
}

async function loadConfig() {
  try {
    const config = await (await fetch("./api/config")).json();
    el.modelName.textContent = config.model
      ? config.model + (config.modelSource === "auto" ? " (자동 선택)" : "")
      : "모델 미정";
    setToolMode(config.toolMode);
    if (config.passwordRequired && !state.password) await askPassword();
  } catch (error) {
    el.modelName.textContent = "설정을 불러오지 못했습니다";
  }
}

function askPassword() {
  return new Promise((resolve) => {
    el.passwordDialog.showModal();
    el.passwordDialog.addEventListener(
      "close",
      () => {
        state.password = el.passwordInput.value;
        sessionStorage.setItem("accessPassword", state.password);
        resolve();
      },
      { once: true },
    );
  });
}

el.composer.addEventListener("submit", (event) => {
  event.preventDefault();
  const text = el.input.value;
  el.input.value = "";
  el.input.style.height = "auto";
  send(text);
});

el.input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    el.composer.requestSubmit();
  }
});

el.input.addEventListener("input", () => {
  el.input.style.height = "auto";
  el.input.style.height = `${Math.min(el.input.scrollHeight, 200)}px`;
});

el.stop.addEventListener("click", () => state.controller?.abort());

el.docsToggle.addEventListener("click", () => {
  el.promptPanel.classList.add("hidden");          // 두 패널은 같은 자리를 씁니다
  el.docsPanel.classList.toggle("hidden");
  if (!el.docsPanel.classList.contains("hidden")) refreshDocuments();
});

/* ------------------------------------------------------------ 지시(프롬프트) */

function renderPromptCount() {
  const n = el.promptInput.value.length;
  el.promptCount.textContent = `${n} / ${MAX_PROMPT_CHARS}`;
  el.promptCount.style.color = n > MAX_PROMPT_CHARS ? "var(--danger)" : "";
  el.promptSave.disabled = n > MAX_PROMPT_CHARS;
}

function markPromptState(saved) {
  // 지시가 걸려 있으면 버튼에 표시합니다. 접힌 패널 안의 설정은 잊히기 쉽습니다 —
  // 답이 이상할 때 여기를 먼저 의심할 수 있어야 합니다.
  el.promptToggle.textContent = state.systemPrompt ? "지시 ●" : "지시";
  el.promptToggle.title = state.systemPrompt ? "이 브라우저에 지시가 저장되어 있습니다" : "";
  if (saved !== undefined) {
    el.promptSave.textContent = saved ? "저장됨" : "저장";
    if (saved) setTimeout(() => (el.promptSave.textContent = "저장"), 1200);
  }
}

el.promptToggle.addEventListener("click", () => {
  el.docsPanel.classList.add("hidden");
  el.promptPanel.classList.toggle("hidden");
  if (!el.promptPanel.classList.contains("hidden")) {
    el.promptInput.value = state.systemPrompt;
    renderPromptCount();
    el.promptInput.focus();
  }
});

el.promptInput.addEventListener("input", renderPromptCount);

el.promptSave.addEventListener("click", () => {
  state.systemPrompt = el.promptInput.value.slice(0, MAX_PROMPT_CHARS);
  localStorage.setItem("systemPrompt", state.systemPrompt);
  markPromptState(true);
});

el.promptClear.addEventListener("click", () => {
  state.systemPrompt = "";
  localStorage.removeItem("systemPrompt");
  el.promptInput.value = "";
  renderPromptCount();
  markPromptState(true);
});

el.fileInput.addEventListener("change", (event) => {
  uploadFiles([...event.target.files]);
  event.target.value = "";
});

document.querySelector(".upload .button").addEventListener("click", () => el.fileInput.click());

el.statusToggle.addEventListener("click", () => openStatus(el.statusPanel.classList.contains("hidden")));
el.statusRefresh.addEventListener("click", () => loadStatus());

markPromptState();
loadConfig();
loadStatus({ autoOpen: true });
