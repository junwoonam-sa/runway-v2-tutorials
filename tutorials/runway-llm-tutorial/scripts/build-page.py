#!/usr/bin/env python3
"""docs/ 의 마크다운을 단일 HTML 페이지로 묶습니다.

손으로 HTML을 다시 쓰지 않는 이유: 문서를 고치면 페이지도 같이 고쳐져야 합니다.
같은 내용이 두 벌 있으면 반드시 갈라집니다.

    python scripts/build-page.py          # → dist/tutorial.html

변환기는 이 저장소의 마크다운만 다룹니다 — 범용 파서가 아닙니다. 헤딩, 문단,
목록, 체크리스트, 표, 코드 펜스, 인용(→ 콜아웃), 구분선, 인라인 강조까지.

결과물은 **파일 하나로 완결**됩니다. 웹 서버가 필요 없고, 더블클릭해서 바로 열리며,
메일로 보내거나 USB에 담아도 그대로 열립니다. 그래서 CSS·JS를 전부 안에 넣고
`<meta charset>` 도 직접 선언합니다 — 서버가 인코딩을 알려 주지 않는 상황
(file:// 로 여는 경우)에서 한글이 깨지지 않게 하려는 것입니다.

바깥에서 받아오는 것은 Google Fonts 하나뿐이고, 인터넷이 없으면 시스템 글꼴로
자연스럽게 내려앉습니다.
"""

from __future__ import annotations

import html
import posixpath
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
OUT = ROOT / "dist" / "tutorial.html"

# 트랙 → 문서 목록. 각 문서는 (경로, 앵커, 사이드바 라벨, 단계 표시, 한 줄 설명).
#
# 트랙을 나눈 이유: 읽는 사람이 둘이기 때문입니다. 챗봇을 손에 넣으려는 사람과,
# 그게 어떻게 돌아가는지 알려는 사람은 필요한 것이 다릅니다. 같은 페이지에 섞어 두면
# 양쪽 다 불편해집니다.
TRACKS = [
    ("튜토리얼 소개", "완성하면 무엇을 쓰게 되는지, 그리고 알고 가면 안 막히는 것들", [
        ("intro/01-what-we-build.md",   "what",       "무엇을 만드나요?",     None, "완성된 챗봇이 하는 일과 전체 순서"),
        ("intro/02-runway.md",          "runway",     "애플리케이션 알고가기", None, "헷갈리면 계속 막히는 세 가지"),
    ]),
    ("0단계. 사전 준비", "챗봇이 쓸 API 키를 만들고 OpenBao에 저장합니다", [
        ("00-preparation/01-keys.md",   "prep-1",     "환경 정보 및 인증 키 발급", "0-1", "도메인·프로젝트 확인, LLM API 키 발급"),
        ("00-preparation/02-openbao.md","prep-2",     "OpenBao 시크릿 등록",  "0-2", "KV 엔진 만들고 키 저장"),
    ]),
    ("1단계. 개발 환경 설정", "저장 공간과 작업 화면을 만들고, 키 전달을 확인합니다", [
        ("01-dev-env/01-pvc.md",        "dev-1",      "PVC 생성",             "1-1", "저장 공간 만들기"),
        ("01-dev-env/02-code-server.md","dev-2",      "Code Server 배포",     "1-2", "브라우저에서 열리는 작업 화면"),
        ("01-dev-env/03-verify.md",     "dev-3",      "시크릿 확인",          "1-3", "OpenBao의 키가 실제로 오는지 눈으로"),
    ]),
    ("2단계. 문서 창고", "문서를 넣어 둘 벡터 DB를 만듭니다", [
        ("02-vector-db/01-deploy.md",   "vec-1",      "Qdrant 배포",          "2-1", "벡터 DB 설치와 주소 만들기"),
        ("02-vector-db/02-verify.md",   "vec-2",      "창고 연결 확인",       "2-2", "주소가 실제로 통하는지"),
    ]),
    ("3단계. 챗봇 배포", "리포지토리를 등록하고 차트를 골라 배포합니다", [
        ("03-chatbot/01-deploy.md",     "bot-1",      "챗봇 배포",            "3-1", "리포지토리 등록 → 차트 → values → 배포"),
        ("03-chatbot/02-status.md",     "bot-2",      "상태 확인",            "3-2", "무엇이 준비됐는지 화면에서 읽기"),
    ]),
    ("4단계. 사용하기", "문서를 올리고, 에이전트가 스스로 검색하는 것을 봅니다", [
        ("04-use/01-chat.md",           "use-1",      "대화해 보기",          "4-1", "첫 메시지"),
        ("04-use/02-documents.md",      "use-2",      "문서 올리기",          "4-2", "창고에 문서 넣기"),
        ("04-use/03-agent.md",          "use-3",      "에이전트 동작 확인",   "4-3", "스스로 판단해서 도구를 부르는 것"),
    ]),
    ("5단계. 팀에 공개", "주소를 열기 전에 알아야 할 것", [
        ("05-share/01-publish.md",      "share-1",    "팀에 공개하기",        "5-1", "보안 고지, 비밀번호, 주소 열기"),
    ]),
    ("부록", "본 흐름을 끝낸 뒤에 필요하면 보는 문서", [
        ("appendix/a-self-build.md",    "app-a",      "자가 빌드",            "A",  "이미지와 차트를 직접 만들기"),
        ("appendix/b-code-tour.md",     "app-b",      "코드 살펴보기",        "B",  "안이 어떻게 도는지"),
        ("appendix/c-troubleshooting.md","app-c",     "문제 해결",            "C",  "증상 → 할 일"),
    ]),
]

CHAPTERS = [entry for _, _, entries in TRACKS for entry in entries]

# 문서끼리 거는 링크를 페이지 안 앵커로 바꾸기 위한 표. 키는 docs/ 기준 경로입니다.
#
# 파일명만으로 찾으면 안 됩니다 — `02-vector-db/01-deploy.md` 와
# `03-chatbot/01-deploy.md` 처럼 같은 파일명이 여러 폴더에 있습니다. 그래서 링크를
# **그 문서의 위치 기준으로 정규화**한 뒤 찾습니다.
DOC_ANCHORS = {name: anchor for name, anchor, *_ in CHAPTERS}

# 코드 펜스에 언어가 붙어 있으면 실행할 수 있는 명령으로 보고 복사 버튼을 답니다.
# 언어 없는 펜스는 다이어그램이나 출력 예시라 복사할 것이 없습니다.
COPYABLE = {"bash", "sh", "yaml", "json", "python", "js", "javascript"}


# ---------------------------------------------------------------- 인라인

def inline(text: str, doc_dir: str = "") -> str:
    """인라인 마크업. 코드 스팬을 먼저 떼어 내 그 안이 다시 해석되지 않게 합니다.

    `doc_dir`는 이 텍스트가 들어 있는 문서의 위치(docs/ 기준)입니다. 상대 링크를
    정규화하는 데 씁니다.
    """
    spans: list[str] = []

    def stash(match: re.Match) -> str:
        spans.append(html.escape(match.group(1)))
        return f"\x00{len(spans) - 1}\x00"

    text = re.sub(r"`([^`]+)`", stash, text)
    text = html.escape(text)

    # 링크. 다른 문서로 가는 것은 페이지 안 앵커로, 저장소 파일로 가는 것은
    # 코드 스팬으로 바꿉니다 — 단일 페이지에서는 열 수 없는 경로입니다.
    def link(match: re.Match) -> str:
        label, target = match.group(1), match.group(2)
        base = target.split("#")[0]
        if target.startswith("http"):
            return f'<a href="{target}" target="_blank" rel="noopener">{label}</a>'

        resolved = posixpath.normpath(posixpath.join(doc_dir, base)) if base else ""
        if resolved in DOC_ANCHORS:
            return f'<a href="#{DOC_ANCHORS[resolved]}">{label}</a>'
        if posixpath.basename(base) == "README.md":
            return f'<a href="#top">{label}</a>'
        return f'<code class="path">{resolved.lstrip("./")}</code>'

    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)

    for i, span in enumerate(spans):
        text = text.replace(f"\x00{i}\x00", f"<code>{span}</code>")
    return text


# ---------------------------------------------------------------- 블록

def convert(lines: list[str], anchor: str, doc_dir: str = "") -> tuple[str, list[tuple[str, str]]]:
    """마크다운 줄들을 HTML로. 사이드바용 (앵커, 제목) 목록도 함께 돌려줍니다."""
    out: list[str] = []
    subheads: list[tuple[str, str]] = []
    i = 0
    seen: dict[str, int] = {}

    def slug(title: str) -> str:
        base = re.sub(r"[^\w가-힣.-]+", "-", title.strip()).strip("-").lower() or "s"
        base = f"{anchor}-{base}"
        seen[base] = seen.get(base, 0) + 1
        return base if seen[base] == 1 else f"{base}-{seen[base]}"

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # --- 코드 펜스 -----------------------------------------------------
        if stripped.startswith("```"):
            lang = stripped[3:].strip()
            i += 1
            body: list[str] = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                body.append(lines[i])
                i += 1
            i += 1
            code = html.escape("\n".join(body))
            chip = f'<span class="code-lang">{html.escape(lang)}</span>' if lang else ""
            copy = '<button class="copy" type="button" aria-label="복사">복사</button>' if lang in COPYABLE else ""
            kind = "block" if lang else "block figure"
            out.append(f'<div class="code {kind}">{chip}{copy}<pre><code>{code}</code></pre></div>')
            continue

        # --- 그림 ------------------------------------------------------------
        # `![설명](../assets/x.svg)` 한 줄짜리 문단은 파일 내용을 **그대로** 페이지에
        # 넣습니다. <img>로 걸지 않는 이유: 그러면 SVG가 페이지의 색 토큰을 못 읽어
        # 다크 모드에서 선과 글자가 배경에 묻힙니다. 인라인이면 var(--ink)가 그대로
        # 먹고, 마크다운을 GitHub에서 볼 때는 이미지로 렌더됩니다 — 한 소스로 둘 다.
        figure = re.fullmatch(r"!\[([^\]]*)\]\(([^)]+\.svg)\)", stripped)
        if figure:
            src = DOCS / posixpath.normpath(posixpath.join(doc_dir, figure.group(2)))
            out.append(f'<figure class="diagram">{src.read_text(encoding="utf-8")}</figure>')
            i += 1
            continue

        # --- 헤딩 -----------------------------------------------------------
        if stripped.startswith("#"):
            level = len(stripped) - len(stripped.lstrip("#"))
            title = stripped[level:].strip()
            if level == 1:
                i += 1
                continue                          # 챕터 제목은 셸이 그립니다
            tag = min(level, 4)
            sid = slug(title)
            if level == 2:
                subheads.append((sid, title))
            out.append(f'<h{tag} id="{sid}">{inline(title, doc_dir)}</h{tag}>')
            i += 1
            continue

        # --- 구분선 ----------------------------------------------------------
        if stripped in ("---", "***", "___"):
            out.append('<hr />')
            i += 1
            continue

        # --- 인용 → 콜아웃 ----------------------------------------------------
        if stripped.startswith(">"):
            body = []
            while i < len(lines) and (lines[i].strip().startswith(">") or (body and not lines[i].strip())):
                if not lines[i].strip():
                    if i + 1 < len(lines) and lines[i + 1].strip().startswith(">"):
                        body.append("")
                        i += 1
                        continue
                    break
                body.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1

            text = "\n".join(body).strip()
            if text.startswith("⚠"):
                tone, label = "warn", "주의"
                text = text.lstrip("⚠").strip()
            elif text.startswith("**이 단계가 끝나면**"):
                tone, label = "goal", "이 단계가 끝나면"
                text = text.split("**", 2)[-1].strip()
            else:
                tone, label = "note", "알아 둘 것"
            out.append(f'<aside class="callout {tone}"><p class="callout-label">{label}</p>'
                       f'{convert(text.split(chr(10)), anchor, doc_dir)[0]}</aside>')
            continue

        # --- 표 ---------------------------------------------------------------
        if stripped.startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]):
            header = [c.strip() for c in stripped.strip("|").split("|")]
            i += 2
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            head = "".join(f"<th>{inline(c, doc_dir)}</th>" for c in header)
            body = "".join("<tr>" + "".join(f"<td>{inline(c, doc_dir)}</td>" for c in r) + "</tr>" for r in rows)
            out.append(f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>')
            continue

        # --- 체크리스트 --------------------------------------------------------
        if re.match(r"^\s*- \[[ x]\]", line):
            items = []
            while i < len(lines) and re.match(r"^\s*- \[[ x]\]", lines[i]):
                items.append(inline(re.sub(r"^\s*- \[[ x]\]\s*", "", lines[i]), doc_dir))
                i += 1
            body = "".join(f'<li><span class="tick" aria-hidden="true"></span><span>{t}</span></li>' for t in items)
            out.append(f'<ul class="checklist">{body}</ul>')
            continue

        # --- 목록 --------------------------------------------------------------
        bullet = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", line)
        if bullet:
            ordered = bool(re.match(r"\d+\.", bullet.group(2)))
            tag = "ol" if ordered else "ul"
            items: list[str] = []
            while i < len(lines):
                m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", lines[i])
                if m and len(m.group(1)) < 2:
                    items.append(inline(m.group(3), doc_dir))
                    i += 1
                elif lines[i].startswith("  ") and lines[i].strip() and items:
                    m2 = re.match(r"^\s*([-*]|\d+\.)\s+(.*)$", lines[i])
                    items[-1] += ("<br />" if m2 else " ") + inline(m2.group(2) if m2 else lines[i].strip(), doc_dir)
                    i += 1
                else:
                    break
            body = "".join(f"<li>{t}</li>" for t in items)
            out.append(f"<{tag}>{body}</{tag}>")
            continue

        # --- 문단 --------------------------------------------------------------
        if stripped:
            para = [stripped]
            i += 1
            while i < len(lines) and lines[i].strip() and not re.match(
                r"^\s*(#|\||>|```|---|[-*] |\d+\. )", lines[i]
            ):
                para.append(lines[i].strip())
                i += 1
            out.append(f"<p>{inline(' '.join(para), doc_dir)}</p>")
            continue

        i += 1

    return "\n".join(out), subheads


def strip_nav(text: str) -> str:
    """문서 끝의 '← 이전 | 다음 →' 줄을 뺍니다. 페이지에는 자체 내비가 있습니다."""
    return "\n".join(l for l in text.splitlines() if not re.match(r"^\s*(←|\[?\s*처음으로)", l))


# ---------------------------------------------------------------- 셸

def build() -> str:
    sections = []
    nav = []

    for track_index, (track_name, track_blurb, entries) in enumerate(TRACKS):
        nav.append(
            f'<li class="nav-track"><span class="nav-track-name">{html.escape(track_name)}</span></li>'
        )
        sections.append(f"""
<section id="track-{track_index}" class="track-divider">
  <span class="track-eyebrow">{html.escape(track_name)}</span>
  <p class="track-blurb">{html.escape(track_blurb)}</p>
</section>""")

        for name, anchor, label, stage, blurb in entries:
            raw = strip_nav((DOCS / name).read_text(encoding="utf-8"))
            body, subheads = convert(raw.splitlines(), anchor, posixpath.dirname(name))

            marker = (f'<span class="stage-num">{html.escape(stage)}</span>' if stage
                      else '<span class="stage-num muted">참고</span>')
            sections.append(f"""
<section id="{anchor}" class="chapter">
  <header class="chapter-head">
    {marker}
    <h2 class="chapter-title">{html.escape(label)}</h2>
    <p class="chapter-blurb">{html.escape(blurb)}</p>
  </header>
  <div class="prose">{body}</div>
</section>""")

            subs = "".join(f'<li><a href="#{sid}">{html.escape(t)}</a></li>' for sid, t in subheads)
            nav.append(f"""
<li class="nav-chapter">
  <a class="nav-top" href="#{anchor}">
    <span class="nav-marker">{html.escape(stage) if stage else '·'}</span>
    <span class="nav-label">{html.escape(label)}</span>
  </a>
  <ul class="nav-subs">{subs}</ul>
</li>""")

    return TEMPLATE.replace("{{NAV}}", "".join(nav)).replace("{{SECTIONS}}", "".join(sections))


TEMPLATE = r"""<meta charset="utf-8" />
<title>Runway LLM 챗봇 튜토리얼</title>
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans+KR:wght@300;400;500;600;700&display=swap" />

<style>
/* ---------------------------------------------------------------- 토큰
   밝은 팔레트가 기본이고, 다크는 토큰만 다시 정의합니다. 컴포넌트는 언제나
   토큰을 통해서만 색을 씁니다 — 미디어 쿼리 안에서 색을 처음 정의하면
   테마가 지정되지 않은 뷰어에서 한쪽 테마의 글자가 다른 쪽 바탕에 얹힙니다. */
:root {
  --ground:   #fbfcfd;
  --surface:  #f1f5f7;
  --sunken:   #e8eef1;
  --ink:      #0f171d;
  --ink-soft: #46555f;
  --ink-mute: #6d7d87;
  --line:     #d9e2e7;
  --line-soft:#e8eef1;

  --accent:      #0c6a72;
  --accent-soft: #d7ecec;
  --accent-ink:  #0a565d;

  --warn:      #9a5b00;
  --warn-soft: #fbf0dc;
  --danger:    #a3312a;
  --ok:        #16694c;
  --ok-soft:   #dcefe5;

  --radius: 3px;
  --measure: 66ch;
  --sans: "IBM Plex Sans KR", -apple-system, "Segoe UI", "Malgun Gothic", sans-serif;
  --mono: "IBM Plex Mono", "SFMono-Regular", Consolas, monospace;
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --ground:   #0c1216;
    --surface:  #131c22;
    --sunken:   #0a1014;
    --ink:      #e3ebf0;
    --ink-soft: #a9b8c1;
    --ink-mute: #7d8e99;
    --line:     #223038;
    --line-soft:#1a252c;

    --accent:      #52c4ca;
    --accent-soft: #10353a;
    --accent-ink:  #7fd8dc;

    --warn:      #e0a44a;
    --warn-soft: #33260f;
    --danger:    #ea8a80;
    --ok:        #5cc79b;
    --ok-soft:   #102f24;
  }
}

:root[data-theme="dark"] {
  --ground:   #0c1216;
  --surface:  #131c22;
  --sunken:   #0a1014;
  --ink:      #e3ebf0;
  --ink-soft: #a9b8c1;
  --ink-mute: #7d8e99;
  --line:     #223038;
  --line-soft:#1a252c;

  --accent:      #52c4ca;
  --accent-soft: #10353a;
  --accent-ink:  #7fd8dc;

  --warn:      #e0a44a;
  --warn-soft: #33260f;
  --danger:    #ea8a80;
  --ok:        #5cc79b;
  --ok-soft:   #102f24;
}

/* ---------------------------------------------------------------- 기본 */
* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--ground);
  color: var(--ink);
  font-family: var(--sans);
  font-weight: 400;
  font-size: 16px;
  line-height: 1.75;
  -webkit-font-smoothing: antialiased;
  word-break: keep-all;      /* 한국어 줄바꿈을 어절 단위로 */
}

a { color: var(--accent-ink); text-decoration-thickness: 1px; text-underline-offset: 2px; }
a:hover { color: var(--accent); }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 2px; }

/* ---------------------------------------------------------------- 레이아웃 */
.shell {
  display: grid;
  grid-template-columns: 268px minmax(0, 1fr);
  align-items: start;
  max-width: 1240px;
  margin: 0 auto;
}

.sidebar {
  position: sticky;
  top: 0;
  height: 100dvh;
  overflow-y: auto;
  padding: 28px 20px 40px 24px;
  border-right: 1px solid var(--line);
  display: flex;
  flex-direction: column;
  gap: 22px;
}

main { padding: 0 40px 120px; min-width: 0; }

/* ---------------------------------------------------------------- 사이드바 */
.brand { display: flex; flex-direction: column; gap: 2px; }
.brand-mark {
  font-family: var(--mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.16em;
  color: var(--accent);
}
.brand-name { font-size: 15px; font-weight: 600; letter-spacing: -0.01em; }
.brand-sub { font-size: 12px; color: var(--ink-mute); }

.nav { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 1px; }
.nav-chapter { position: relative; }

/* 트랙 구분 — 읽는 사람이 둘이라는 것을 목차에서 먼저 보이게 합니다. */
.nav-track { margin: 16px 0 5px; }
.nav-track:first-child { margin-top: 0; }
.nav-track-name {
  font-family: var(--mono);
  font-size: 9.5px;
  font-weight: 600;
  letter-spacing: 0.16em;
  color: var(--ink-mute);
  text-transform: uppercase;
}

.nav-top {
  display: grid;
  grid-template-columns: 22px 1fr;
  gap: 9px;
  align-items: center;
  padding: 5px 8px 5px 0;
  font-size: 13.5px;
  color: var(--ink-soft);
  text-decoration: none;
  border-radius: var(--radius);
}
.nav-top:hover { color: var(--ink); }

.nav-marker {
  font-family: var(--mono);
  font-size: 10.5px;
  font-weight: 600;
  text-align: center;
  line-height: 20px;
  height: 20px;
  border: 1px solid var(--line);
  border-radius: 2px;
  color: var(--ink-mute);
  background: var(--surface);
}

.nav-chapter.active > .nav-top { color: var(--ink); font-weight: 600; }
.nav-chapter.active .nav-marker {
  color: var(--ground);
  background: var(--accent);
  border-color: var(--accent);
}

.nav-subs {
  list-style: none;
  margin: 0 0 6px 31px;
  padding: 0 0 0 11px;
  border-left: 1px solid var(--line-soft);
  display: none;
  flex-direction: column;
}
.nav-chapter.active .nav-subs { display: flex; }
.nav-subs a {
  display: block;
  padding: 2.5px 0;
  font-size: 12.5px;
  line-height: 1.45;
  color: var(--ink-mute);
  text-decoration: none;
}
.nav-subs a:hover { color: var(--accent); }
.nav-subs a.here { color: var(--accent); }

.side-foot {
  margin-top: auto;
  padding-top: 18px;
  border-top: 1px solid var(--line-soft);
  font-size: 11.5px;
  color: var(--ink-mute);
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.theme-toggle {
  font: inherit;
  font-size: 11.5px;
  color: var(--ink-soft);
  background: none;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 4px 9px;
  cursor: pointer;
  align-self: flex-start;
}
.theme-toggle:hover { border-color: var(--accent); color: var(--accent); }

/* ---------------------------------------------------------------- 히어로 */
.hero { padding: 68px 0 20px; max-width: var(--measure); }
.eyebrow {
  font-family: var(--mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.14em;
  color: var(--accent);
  margin: 0 0 14px;
}
.hero h1 {
  font-size: clamp(30px, 4.6vw, 46px);
  line-height: 1.22;
  font-weight: 600;
  letter-spacing: -0.025em;
  margin: 0 0 18px;
  text-wrap: balance;
}
.hero .lede { font-size: 17.5px; color: var(--ink-soft); margin: 0 0 26px; }

.facts {
  display: flex;
  flex-wrap: wrap;
  gap: 0;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  overflow: hidden;
  margin-bottom: 34px;
}
.fact { flex: 1 1 130px; padding: 12px 16px; border-right: 1px solid var(--line); }
.fact:last-child { border-right: 0; }
.fact dt {
  font-family: var(--mono);
  font-size: 10px;
  letter-spacing: 0.1em;
  color: var(--ink-mute);
  margin-bottom: 3px;
}
.fact dd { margin: 0; font-size: 14px; font-weight: 500; font-variant-numeric: tabular-nums; }

.diagram {
  background: var(--sunken);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 20px 22px;
  overflow-x: auto;
  margin: 0 0 42px;
}
.diagram svg { display: block; width: 100%; max-width: 600px; height: auto; margin: 0 auto; }
.diagram pre {
  margin: 0;
  font-family: var(--mono);
  font-size: 12px;
  line-height: 1.6;
  color: var(--ink-soft);
}

/* ---------------------------------------------------------------- 본문 */
.chapter { max-width: var(--measure); padding-top: 34px; scroll-margin-top: 8px; }
.chapter + .chapter { border-top: 1px solid var(--line); margin-top: 56px; }

.track-divider {
  max-width: var(--measure);
  margin-top: 64px;
  padding: 22px 24px;
  border: 1px solid var(--line);
  border-left: 3px solid var(--accent);
  border-radius: 0 var(--radius) var(--radius) 0;
  background: var(--surface);
  scroll-margin-top: 8px;
}
.track-eyebrow {
  display: block;
  font-family: var(--mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.16em;
  color: var(--accent);
  text-transform: uppercase;
  margin-bottom: 6px;
}
.track-blurb { margin: 0; font-size: 15.5px; color: var(--ink); }
.track-divider + .chapter { border-top: 0; }

.chapter-head { margin-bottom: 34px; }
.stage-num {
  display: inline-block;
  font-family: var(--mono);
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.15em;
  color: var(--ground);
  background: var(--accent);
  padding: 3px 9px;
  border-radius: 2px;
  margin-bottom: 12px;
}
.stage-num.muted { color: var(--ink-soft); background: var(--surface); border: 1px solid var(--line); }

.chapter-title {
  font-size: clamp(25px, 3.2vw, 33px);
  line-height: 1.28;
  font-weight: 600;
  letter-spacing: -0.02em;
  margin: 0 0 8px;
  text-wrap: balance;
}
.chapter-blurb { margin: 0; color: var(--ink-mute); font-size: 15px; }

/* 본문은 .prose 안에서만. 챕터 헤더를 이 규칙들 밖에 두어야 타입 선택자가
   제목 클래스를 특정도로 이기는 사고가 나지 않습니다. */
.prose h2 {
  font-size: 21px;
  font-weight: 600;
  letter-spacing: -0.015em;
  line-height: 1.4;
  margin: 52px 0 14px;
  padding-top: 4px;
  scroll-margin-top: 16px;
  text-wrap: balance;
}
.prose h3 {
  font-size: 16.5px;
  font-weight: 600;
  margin: 34px 0 10px;
  scroll-margin-top: 16px;
  color: var(--ink);
}
.prose h4 { font-size: 15px; font-weight: 600; margin: 24px 0 8px; }

.prose > p, .prose li > p { margin: 0 0 16px; }
.prose ul, .prose ol { margin: 0 0 18px; padding-left: 1.35em; }
.prose li { margin-bottom: 6px; }
.prose li::marker { color: var(--ink-mute); }

.prose hr { border: 0; border-top: 1px solid var(--line-soft); margin: 40px 0; }

code {
  font-family: var(--mono);
  font-size: 0.855em;
  background: var(--surface);
  border: 1px solid var(--line-soft);
  border-radius: 2px;
  padding: 1px 5px;
  word-break: break-all;
}
code.path { color: var(--accent-ink); background: var(--accent-soft); border-color: transparent; }

/* ---------------------------------------------------------------- 코드 블록 */
.code {
  position: relative;
  background: var(--sunken);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  margin: 0 0 20px;
  overflow: hidden;
}
.code pre { margin: 0; padding: 15px 17px; overflow-x: auto; }
.code code {
  background: none;
  border: 0;
  padding: 0;
  font-size: 12.9px;
  line-height: 1.65;
  color: var(--ink);
  word-break: normal;
  white-space: pre;
}
.code.figure code { color: var(--ink-soft); font-size: 12.2px; line-height: 1.55; }

.code-lang {
  position: absolute;
  top: 0;
  right: 0;
  font-family: var(--mono);
  font-size: 9.5px;
  letter-spacing: 0.11em;
  text-transform: uppercase;
  color: var(--ink-mute);
  background: var(--surface);
  border-left: 1px solid var(--line);
  border-bottom: 1px solid var(--line);
  border-radius: 0 var(--radius) 0 var(--radius);
  padding: 2px 8px;
}
.copy {
  position: absolute;
  top: 26px;
  right: 6px;
  font-family: var(--mono);
  font-size: 10.5px;
  color: var(--ink-mute);
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 2px;
  padding: 2px 7px;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.12s ease;
}
.code:hover .copy, .copy:focus-visible { opacity: 1; }
.copy:hover { color: var(--accent); border-color: var(--accent); }
.copy.done { color: var(--ok); border-color: var(--ok); opacity: 1; }

/* ---------------------------------------------------------------- 표 */
.table-wrap {
  overflow-x: auto;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  margin: 0 0 22px;
}
table { border-collapse: collapse; width: 100%; font-size: 14px; }
thead th {
  text-align: left;
  font-weight: 600;
  font-size: 12px;
  letter-spacing: 0.02em;
  color: var(--ink-soft);
  background: var(--surface);
  padding: 9px 13px;
  white-space: nowrap;
  border-bottom: 1px solid var(--line);
}
tbody td {
  padding: 9px 13px;
  border-bottom: 1px solid var(--line-soft);
  vertical-align: top;
  line-height: 1.6;
}
tbody tr:last-child td { border-bottom: 0; }
tbody td:first-child { color: var(--ink); }
table code { font-size: 12px; }

/* ---------------------------------------------------------------- 콜아웃
   함정과 경고가 이 튜토리얼의 알맹이라, 가장 눈에 띄는 반복 장치로 둡니다. */
.callout {
  border-left: 2px solid var(--line);
  background: var(--surface);
  border-radius: 0 var(--radius) var(--radius) 0;
  padding: 14px 18px 2px;
  margin: 0 0 22px;
}
/* .prose 를 앞에 붙여 두 클래스로 만들면 .prose > p 같은 규칙을 특정도로
   이깁니다 — !important 없이. */
.prose .callout p.callout-label {
  font-family: var(--mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.13em;
  text-transform: uppercase;
  color: var(--ink-mute);
  margin: 0 0 6px;
}
.prose .callout p { margin: 0 0 12px; }
.prose .callout ul, .prose .callout ol { margin-bottom: 12px; }
.prose .callout .code { margin-bottom: 14px; }

.callout.warn { border-left-color: var(--warn); background: var(--warn-soft); }
.callout.goal { border-left-color: var(--accent); background: var(--accent-soft); }
/* 라벨 색은 위의 .prose .callout p.callout-label 을 이겨야 하므로 같은 형태로 씁니다. */
.prose .callout.warn p.callout-label { color: var(--warn); }
.prose .callout.goal p.callout-label { color: var(--accent-ink); }

/* ---------------------------------------------------------------- 체크리스트 */
.prose .checklist {
  list-style: none;
  margin: 0 0 22px;
  padding: 16px 18px;
  border: 1px solid var(--line);
  border-left: 2px solid var(--ok);
  border-radius: 0 var(--radius) var(--radius) 0;
  background: var(--ok-soft);
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.prose .checklist li { display: flex; gap: 10px; align-items: flex-start; margin: 0; font-size: 14.5px; }
.tick {
  flex: none;
  width: 13px;
  height: 13px;
  margin-top: 6px;
  border: 1px solid var(--ok);
  border-radius: 2px;
  background: var(--ground);
}

/* ---------------------------------------------------------------- 반응형 */
.mobile-bar { display: none; }

@media (max-width: 980px) {
  .shell { grid-template-columns: 1fr; }
  .sidebar {
    position: static;
    height: auto;
    border-right: 0;
    border-bottom: 1px solid var(--line);
    padding: 18px 22px;
  }
  .nav-subs { display: none !important; }
  .nav { flex-direction: row; flex-wrap: wrap; gap: 4px 14px; }
  .side-foot { margin-top: 14px; }
  main { padding: 0 22px 90px; }
  .hero { padding-top: 40px; }
}

@media (prefers-reduced-motion: reduce) {
  * { animation: none !important; transition: none !important; scroll-behavior: auto !important; }
}

html { scroll-behavior: smooth; }
</style>

<div class="shell">
  <nav class="sidebar" aria-label="목차">
    <div class="brand">
      <span class="brand-mark">RUNWAY 2.3.0</span>
      <span class="brand-name">LLM 챗봇 튜토리얼</span>
      <span class="brand-sub">에이전트 · MCP · 벡터 검색</span>
    </div>

    <ul class="nav">{{NAV}}</ul>

    <div class="side-foot">
      <button class="theme-toggle" type="button" id="theme">테마 전환</button>
      <span>키 발급부터 배포까지 · 약 5시간</span>
    </div>
  </nav>

  <main id="top">
    <header class="hero">
      <p class="eyebrow">RUNWAY 2.3.0 · 실습 가이드</p>
      <h1>문서를 읽고 답하는 LLM 챗봇을 Runway 위에 만들어 배포합니다</h1>
      <p class="lede">
        키 발급에서 시작해 개발 환경을 만들고, 앱을 짜고, 에이전트와 MCP를 붙이고,
        벡터 DB를 연결해, 커스텀 애플리케이션으로 배포하는 데까지 갑니다.
        각 단계 끝에 <strong>여기까지 되면 성공</strong> 확인 항목이 있습니다.
      </p>

      <dl class="facts">
        <div class="fact"><dt>단계</dt><dd>Stage 0 – 5</dd></div>
        <div class="fact"><dt>소요</dt><dd>약 5시간</dd></div>
        <div class="fact"><dt>필요 권한</dt><dd>프로젝트 member</dd></div>
        <div class="fact"><dt>벡터 DB</dt><dd>Qdrant</dd></div>
      </dl>

      <div class="diagram">
<pre>                                 ┌─────────────────────────────┐
브라우저 ──────────────────────▶ │  커스텀 애플리케이션 (파드)   │
                                 │                             │
                                 │  FastAPI  ── 정적 UI 서빙    │
                                 │     │                       │
                                 │     ├─ 에이전트 루프         │
                                 │     │                       │
                                 │     └─ stdio ──▶ MCP 서버    │ ← 같은 컨테이너 안
                                 └────────────────────┬────────┘    자식 프로세스
                                        │             │
                      LLM 게이트웨이 ◀──┘             └──▶ Qdrant (벡터 DB)
                      (LiteLLM)                            프로젝트 애플리케이션

시크릿은 OpenBao에서 /vault/secrets/*.env 로 주입 — 이미지에도 values에도 없음</pre>
      </div>
    </header>

    {{SECTIONS}}
  </main>
</div>

<script>
/* 코드 복사 */
document.querySelectorAll(".copy").forEach((button) => {
  button.addEventListener("click", async () => {
    const code = button.parentElement.querySelector("code").textContent;
    try {
      await navigator.clipboard.writeText(code);
      button.textContent = "복사됨";
      button.classList.add("done");
      setTimeout(() => { button.textContent = "복사"; button.classList.remove("done"); }, 1400);
    } catch {
      button.textContent = "실패";
      setTimeout(() => { button.textContent = "복사"; }, 1400);
    }
  });
});

/* 스크롤 추적 — 지금 읽고 있는 장과 절을 사이드바에 표시 */
const chapters = [...document.querySelectorAll(".chapter")];
const navItems = new Map([...document.querySelectorAll(".nav-chapter")].map((li) => [
  li.querySelector(".nav-top").getAttribute("href").slice(1), li,
]));
const subLinks = [...document.querySelectorAll(".nav-subs a")];

function track() {
  const line = window.scrollY + window.innerHeight * 0.28;

  let current = chapters[0];
  for (const chapter of chapters) if (chapter.offsetTop <= line) current = chapter;
  navItems.forEach((li, id) => li.classList.toggle("active", id === current.id));

  let here = null;
  for (const link of subLinks) {
    const target = document.getElementById(link.getAttribute("href").slice(1));
    if (target && target.offsetTop <= line) here = link;
    link.classList.remove("here");
  }
  if (here && here.closest(".nav-chapter").classList.contains("active")) here.classList.add("here");
}

let ticking = false;
addEventListener("scroll", () => {
  if (ticking) return;
  ticking = true;
  requestAnimationFrame(() => { track(); ticking = false; });
}, { passive: true });
track();

/* 테마 전환 — 뷰어의 시스템 설정을 출발점으로 삼고, 누르면 그 반대로 고정 */
const root = document.documentElement;
document.getElementById("theme").addEventListener("click", () => {
  const dark = root.getAttribute("data-theme") === "dark" ||
    (!root.hasAttribute("data-theme") && matchMedia("(prefers-color-scheme: dark)").matches);
  root.setAttribute("data-theme", dark ? "light" : "dark");
});
</script>
"""


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build(), encoding="utf-8")
    print(f"{OUT}  ({OUT.stat().st_size / 1024:.0f} KB)")
