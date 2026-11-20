"""블로그 글 번역 — 한국어가 아닌 글을 로컬 모델(Ollama qwen3:14b, 5070 Ti)로 한국어로.

    python -m store.ingest.translate detect            # 언어 판정만(쓰기 없음) — 언어별 건수
    python -m store.ingest.translate run [--limit N]   # 번역 → DB post_translation + blog_content/<id>.json
    python -m store.ingest.translate run --dry-run --limit 1   # DB·파일에 안 쓰고 결과만 출력

- 언어는 post.lang(피드 설정값 — 일본 블로그도 'en')을 믿지 않고 본문 글자로 다시 판정한다.
- 번역 대상: 제목·요약·DB 본문, blog_content 파일이 있으면 그 전체 본문(content_ko)도.
- 코드 블록(```)·인라인 코드·URL·마크다운 문법은 건드리지 않는다. 문단 단위로 잘라 보낸다.
- 원문 해시(source_hash)가 같으면 건너뛴다 — 원문이 바뀐 글만 다시.
- 마이그레이션 018(post_translation)이 먼저 적용돼 있어야 한다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from store.db import conn as store_conn  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent.parent
BLOG_CONTENT = ROOT / "jd-viewer" / "public" / "blog_content"
OLLAMA = "http://127.0.0.1:11434/api/chat"
MODEL = "qwen3:14b"
CHUNK = 1800                         # 한 번에 보내는 원문 글자 수(문단 경계에서 자른다)
LANG_KO = {"en": "영어", "ja": "일본어", "zh": "중국어", "de": "독일어", "fr": "프랑스어", "es": "스페인어",
           "pt": "포르투갈어", "it": "이탈리아어", "nl": "네덜란드어", "vi": "베트남어", "ru": "러시아어", "id": "인도네시아어"}

# ── 언어 판정 ─────────────────────────────────────────────────────────────
_HANGUL = re.compile(r"[가-힣]")
_KANA = re.compile(r"[぀-ヿ]")
_HAN = re.compile(r"[一-鿿]")
_CYR = re.compile(r"[Ѐ-ӿ]")
_LATIN = re.compile(r"[A-Za-zÀ-ÿ]")
_STOP = {
    "en": "the and of to in is for that with on this are you we it as be by from",
    "de": "der die das und ist nicht mit für auf ein eine wir sie den von zu im",
    "fr": "le la les et des est une pour dans que qui nous sur pas avec du",
    "es": "el la los las y de que en para una con por es del se nuestro",
    "pt": "o a os as e de que em para uma com não do da são nosso",
    "it": "il la gli le e di che per una con non del della sono nostro",
    "nl": "de het een en van is dat op voor met niet wij zijn ook",
    "id": "dan yang di untuk dengan ini itu dari kami adalah tidak pada",
}
_STOP = {k: {w for w in v.split() if len(w) > 1} for k, v in _STOP.items()}   # 한 글자 낱말(a·o·e)은 언어를 못 가른다
_VI = re.compile(r"[ăâđêôơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ]")


def detect(text: str) -> str:
    """글자 체계로 먼저 가르고, 라틴 문자면 흔한 낱말로 언어를 가른다."""
    t = re.sub(r"```.*?```|`[^`]*`|https?://\S+", " ", text or "", flags=re.S)[:6000]
    n = {k: len(rx.findall(t)) for k, rx in (("ko", _HANGUL), ("kana", _KANA), ("han", _HAN), ("cyr", _CYR), ("lat", _LATIN))}
    letters = sum(n.values()) or 1
    if n["ko"] / letters > 0.15:
        return "ko"
    if n["kana"] / letters > 0.05:
        return "ja"
    if n["han"] / letters > 0.2:
        return "zh"
    if n["cyr"] / letters > 0.3:
        return "ru"
    if len(_VI.findall(t.lower())) > 5:
        return "vi"
    words = re.findall(r"[a-zà-ÿ]+", t.lower())
    if not words:
        return "en"
    score = {k: sum(w in s for w in words) for k, s in _STOP.items()}
    best = max(score, key=score.get)
    return best if score[best] > score["en"] * 1.3 else "en"


# ── 번역 ─────────────────────────────────────────────────────────────────
PROMPT = """너는 기술 블로그 번역가다. <원문> 안의 {src} 글을 한국어로 번역해서 번역문만 출력하라.
규칙: 제품·회사 이름과 코드·명령어·링크 주소·파일 경로는 그대로 둔다. 마크다운 문법(#, -, *, 표, [글](주소))은 유지한다.
문장은 '~다'로 끝나는 평서체로 쓴다('~합니다' 쓰지 않음). '귀하'·'당신'은 쓰지 않는다. 원문에 없는 말을 더하지 않는다.{names}

<원문>
{text}
</원문>

한국어 번역:"""


def _ask(prompt: str, out_limit: int) -> str:
    body = json.dumps({"model": MODEL, "stream": False, "think": False,
                       "options": {"temperature": 0.1, "num_ctx": 8192, "num_predict": out_limit},
                       "messages": [{"role": "user", "content": prompt}]}).encode("utf-8")
    req = urllib.request.Request(OLLAMA, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        out = json.load(r)["message"]["content"]
    return re.sub(r"<think>.*?</think>", "", out, flags=re.S).strip()


def _blocks(md: str) -> list[tuple[bool, str]]:
    """(번역할까, 조각) — 코드 블록은 통째로 번역하지 않는 조각."""
    out = []
    for i, part in enumerate(re.split(r"(```.*?```)", md, flags=re.S)):
        if not part:
            continue
        if i % 2:
            out.append((False, part))
            continue
        buf = ""
        for para in re.split(r"(\n\s*\n)", part):
            if len(buf) + len(para) > CHUNK and buf.strip():
                out.append((True, buf))
                buf = ""
            buf += para
        if buf:
            out.append((bool(buf.strip()), buf))
    return out


def _untranslated(src_text: str, out: str) -> bool:
    if not out or out.strip() == src_text.strip():
        return True
    letters = len(re.findall(r"[^\W\d_]", out)) or 1
    return len(_HANGUL.findall(out)) / letters < 0.2 and len(_HANGUL.findall(src_text)) == 0 and len(src_text) > 15


def fix_names(ko: str, names: list[str]) -> str:
    """'라azorpay' 처럼 이름 첫 글자만 한글로 바뀐 것을 되돌린다."""
    for n in names or []:
        if len(n) > 3 and " " not in n:
            ko = re.sub(r"[가-힣]" + re.escape(n[1:]), n, ko)
    return ko


def src_en(src: str) -> str:
    return {"en": "English", "ja": "Japanese", "zh": "Chinese", "de": "German", "fr": "French", "es": "Spanish",
            "pt": "Portuguese", "it": "Italian", "nl": "Dutch", "vi": "Vietnamese", "ru": "Russian", "id": "Indonesian"}.get(src, "foreign")


def _one(part: str, src: str, names: list[str] | None = None) -> str:
    """한 조각 번역 — 그대로 되돌려 주거나 한국어가 거의 없으면 한 번 더 묻는다."""
    keep = [n for n in (names or []) if n and n.lower() in part.lower()]
    hint = ("\n다음 이름은 소리 나는 대로 옮기지 말고 영문 그대로 쓴다: " + ", ".join(keep)) if keep else ""
    p = PROMPT.format(src=LANG_KO.get(src, "외국어"), text=part, names=hint)
    ko = _ask(p, out_limit=max(400, len(part) * 2))
    if _untranslated(part, ko):
        ko = _ask(p + "\n(반드시 한국어로)", out_limit=max(400, len(part) * 2)) or ko
    if src in ("ja", "zh") and _HAN.search(ko):         # 한자가 남았으면('고騰') 한 번 더 — 덜 남은 쪽을 쓴다
        again = _ask(p + "\n(한자를 하나도 남기지 말고 모두 한국어로)", out_limit=max(400, len(part) * 2))
        if again and len(_HAN.findall(again)) < len(_HAN.findall(ko)):
            ko = again
    if src == "ja" and len(_KANA.findall(ko)) > 2:   # 가나가 남았으면('はじめ에') 한 번 더 — 덜 남은 쪽
        again = _ask(p + "\n(일본어 가나를 하나도 남기지 말고 모두 한국어로)", out_limit=max(400, len(part) * 2))
        if again and len(_KANA.findall(again)) < len(_KANA.findall(ko)):
            ko = again
    if _untranslated(part, ko) or (src == "ja" and len(_KANA.findall(ko)) > 2):
        # 한국어 지시문에는 원문을 그대로 되돌려 주는 글이 있다(짧은 일본어 요약) — 영어 지시문으로 한 번 더
        names_en = (" Keep these names in English: " + ", ".join(keep) + ".") if keep else ""
        again = _ask(f"Translate the following {src_en(src)} text into natural Korean. Output only the Korean translation. "
                     f"Keep code, URLs and product names unchanged.{names_en}\n\n{part}", out_limit=max(400, len(part) * 2))
        if again and (len(_KANA.findall(again)) < len(_KANA.findall(ko)) or _untranslated(part, ko)) and not _untranslated(part, again):
            ko = again
    ko = re.sub(r"はじめに|はじめ에", "들어가며", ko)
    ko = fix_names(ko, keep)
    ko = re.sub(r"^\s*</?원문>\s*|\s*</?원문>\s*$", "", ko)
    if len(part) > 15 and part in ko:                 # '원문 → 번역' 꼴로 답하면 번역만
        ko = ko.split(part, 1)[1].strip().lstrip("→:-").strip() or ko
    return re.sub(r"귀하의\s*", "", ko).replace("귀하", "여러분")


def translate(text: str, src: str, names: list[str] | None = None) -> str:
    if not (text or "").strip():
        return ""
    out = []
    for go, part in _blocks(text):
        if not go or not re.search(r"[^\W\d_]", part):
            out.append(part)
            continue
        lead, trail = re.match(r"^\s*", part).group(), re.search(r"\s*$", part).group()
        ko = _one(part.strip(), src, names)
        out.append(lead + ko + trail)
    return "".join(out)


# ── 읽고 쓰기 ────────────────────────────────────────────────────────────
def _content_file(cid: str | None) -> tuple[Path | None, dict | None]:
    if not cid:
        return None, None
    p = BLOG_CONTENT / f"{cid}.json"
    try:
        return p, json.loads(p.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None, None


def _names(blog: str) -> list[str]:
    """블로그(회사) 이름 — 'Razorpay' 가 '라자르파이' 가 되지 않게 영문 그대로 두라고 알려 준다."""
    out = [blog] if blog else []
    out += [w for w in re.findall(r"[A-Za-z][\w.&-]+", blog or "") if len(w) > 2 and w.lower() not in ("blog", "engineering", "tech", "the")]
    return list(dict.fromkeys(out))


def _hash(*parts: str) -> str:
    return hashlib.sha1("\x1f".join(p or "" for p in parts).encode("utf-8")).hexdigest()


def _rows(cur) -> list[dict]:
    cur.execute("""SELECT p.id, p.content_id, p.title, p.summary, p.body, p.lang, p.blog_name, t.source_hash
                     FROM post p LEFT JOIN post_translation t ON t.post_id = p.id
                    ORDER BY (p.content_id IS NULL), p.published_at DESC NULLS LAST, p.id""")
    cols = [d[0] for d in cur.description]
    return [r if isinstance(r, dict) else dict(zip(cols, r)) for r in cur.fetchall()]


def _rows_of(cur) -> list[dict]:
    cols = [d[0] for d in cur.description]
    return [r if isinstance(r, dict) else dict(zip(cols, r)) for r in cur.fetchall()]


def cmd_detect() -> None:
    from collections import Counter
    with store_conn.connect() as c, c.cursor() as cur:
        cur.execute("SELECT id, lang, title, summary, body FROM post")
        got = Counter()
        for r in _rows_of(cur):
            got[(r["lang"], detect(" ".join((r["title"], r["summary"], r["body"]))))] += 1
    for (tag, det), n in got.most_common():
        print(f"표기 {tag or '-':3} → 판정 {det:3} {n}건")


LOCK = ROOT / "catch_capture" / "var" / "translate.lock"


def cmd_run(limit: int, dry: bool, cid: str = "") -> None:
    """한 번에 하나만 돈다 — 밀린 번역을 돌리는 중에 루프가 또 부르면 그 회차는 건너뛴다."""
    if LOCK.exists() and time.time() - LOCK.stat().st_mtime < 6 * 3600:
        print("번역이 이미 돌고 있다 — 건너뜀", flush=True)
        return
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    LOCK.write_text(str(time.time()))
    try:
        _run(limit, dry, cid)
    finally:
        LOCK.unlink(missing_ok=True)


def _run(limit: int, dry: bool, cid: str) -> None:
    done = 0
    with store_conn.connect() as c, c.cursor() as cur:
        rows = [r for r in _rows(cur) if not cid or r["content_id"] == cid]
        for r in rows:
            path, doc = _content_file(r["content_id"])
            full = (doc or {}).get("content") or ""
            src = detect(" ".join((r["title"], r["summary"], r["body"], full[:3000])))
            h = _hash(r["title"], r["summary"], r["body"], full)
            if r["source_hash"] == h:
                continue
            if limit and done >= limit:
                break
            t0 = time.time()
            if src == "ko":
                tr = {"title_ko": "", "summary_ko": "", "body_ko": "", "content_ko": ""}
            else:
                nm = _names(r["blog_name"])
                tr = {"title_ko": translate(r["title"], src, nm), "summary_ko": translate(r["summary"], src, nm),
                      "body_ko": "" if full else translate(r["body"], src, nm),       # 전체 본문이 있으면 그걸 번역한다(DB 본문은 그 앞부분)
                      "content_ko": translate(full, src, nm)}
            if dry:
                print(json.dumps({"id": r["id"], "src": src, **{k: v[:400] for k, v in tr.items()}}, ensure_ascii=False, indent=1))
            else:
                cur.execute("""INSERT INTO post_translation (post_id, src_lang, title_ko, summary_ko, body_ko, content_ko, source_hash, model, translated_at)
                               VALUES (%s,%s,%s,%s,%s,%s,%s,%s, now())
                               ON CONFLICT (post_id) DO UPDATE SET src_lang=EXCLUDED.src_lang, title_ko=EXCLUDED.title_ko,
                                 summary_ko=EXCLUDED.summary_ko, body_ko=EXCLUDED.body_ko, content_ko=EXCLUDED.content_ko,
                                 source_hash=EXCLUDED.source_hash, model=EXCLUDED.model, translated_at=now()""",
                            (r["id"], src, tr["title_ko"], tr["summary_ko"], tr["body_ko"], tr["content_ko"], h,
                             MODEL if src != "ko" else ""))
                c.commit()
                if path and tr["content_ko"]:            # 뷰어가 읽는 파일에도 — 원문 언어도 바로잡는다
                    doc.update(content_ko=tr["content_ko"], translated=True, lang=src, translated_by=MODEL)
                    tmp = path.with_suffix(".json.tmp")
                    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
                    tmp.replace(path)
            done += 1
            LOCK.touch()
            if src != "ko":
                print(f"[{done}] {r['id']} {src} {len(r['title']) + len(r['summary']) + len(r['body']) + len(full)}자 "
                      f"{time.time() - t0:.0f}초 · {tr['title_ko'][:50]}", flush=True)
    print(f"끝 — {done}건", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["detect", "run"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--cid", default="", help="이 글 하나만(content_id)")
    a = ap.parse_args()
    cmd_detect() if a.cmd == "detect" else cmd_run(a.limit, a.dry_run, a.cid)
