#!/usr/bin/env python3
"""
Tao "bundle bao cao" cho 1 khoa (1 chuong top-level cua SkoolCourse / 1 course folder):
  - Transcript_VI.md     : transcript GOP ca khoa, dich tieng Viet (Google).
  - PhuDe_SongNgu.srt     : phu de SONG NGU - giu .srt goc (timestamp), them dong tieng Viet
                            DUOI dong tieng Anh. Gop cac bai thanh 1 file (offset thoi gian).

Dich bang deep-translator (Google, mien phi). Gom cum phu de -> dich theo lo (newline) ->
tach lai; neu lech so dong thi tu dich lai tung dong (an toan).

  python report_bundle.py --section "01 - AI Foundations" --out "E:\\SkoolProject\\BaoCao\\01 - AI Foundations"
  python report_bundle.py --root "E:\\SkoolProject\\courses\\X" --out "..."   # course folder rieng
"""
import argparse, re, time
from pathlib import Path
import config as C
import export as E

BATCH_CHARS = 3500          # tran ky tu moi lan goi Google
SLEEP = 0.25                 # nghi giua cac lo (nhe tay tranh chan)
GAP_MS = 1500               # khoang lang chen giua cac bai khi gop srt


def _tr():
    from deep_translator import GoogleTranslator
    return GoogleTranslator(source="auto", target="vi")


def translate_lines(lines, log=print):
    """Dich list cau, GIU dung so phan tu. Gom lo theo BATCH_CHARS, tach lai theo newline."""
    tr = _tr()
    out = [None] * len(lines)
    i = 0
    n = len(lines)
    done = 0
    while i < n:
        # gom 1 lo
        j = i; size = 0; batch = []
        while j < n and (size + len(lines[j]) + 1 <= BATCH_CHARS or not batch):
            batch.append(lines[j]); size += len(lines[j]) + 1; j += 1
        joined = "\n".join(x if x.strip() else "." for x in batch)
        try:
            res = tr.translate(joined) or ""
            parts = res.split("\n")
        except Exception:
            parts = []
        if len(parts) == len(batch):
            for k, p in enumerate(parts): out[i + k] = p
        else:
            # lech -> dich tung dong (an toan), bo qua dong rong
            for k, src in enumerate(batch):
                if not src.strip(): out[i + k] = ""
                else:
                    try: out[i + k] = tr.translate(src) or src
                    except Exception: out[i + k] = src
                time.sleep(SLEEP)
        done += len(batch); i = j
        if log: log(f"   dich {done}/{n} dong...")
        time.sleep(SLEEP)
    return [o if o is not None else "" for o in out]


# ----------------------------- SRT -----------------------------
TS = re.compile(r"(\d\d):(\d\d):(\d\d),(\d\d\d)\s*-->\s*(\d\d):(\d\d):(\d\d),(\d\d\d)")

def _to_ms(h, m, s, ms): return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(ms)
def _fmt(ms):
    ms = max(0, int(ms)); h = ms // 3600000; ms %= 3600000
    m = ms // 60000; ms %= 60000; s = ms // 1000; ms %= 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def parse_srt(text):
    """Tra ve list (start_ms, end_ms, text)."""
    cues = []
    for block in re.split(r"\n\s*\n", text.replace("\r", "")):
        lines = [l for l in block.split("\n") if l.strip() != ""]
        if not lines: continue
        ts_idx = 0
        if not TS.search(lines[0]) and len(lines) > 1 and TS.search(lines[1]): ts_idx = 1
        m = TS.search(lines[ts_idx]) if ts_idx < len(lines) else None
        if not m: continue
        start = _to_ms(*m.group(1, 2, 3, 4)); end = _to_ms(*m.group(5, 6, 7, 8))
        body = " ".join(lines[ts_idx + 1:]).strip()
        cues.append((start, end, body))
    return cues


def lesson_order(root):
    """Cac bai (folder la) theo thu tu, kem tieu de + duong dan srt."""
    items = []
    for b in E.lesson_blocks(root):
        if b["kind"] != "lesson": continue
        srt = b["path"] / "video.srt"
        items.append((b["title"], srt if srt.exists() else None))
    return items


def build(root, out, log=print):
    root = Path(root); out = Path(out); out.mkdir(parents=True, exist_ok=True)
    lessons = lesson_order(root)
    # gom tat ca cue (kem chi muc bai) de dich 1 luot
    all_texts = []; per_lesson = []   # per_lesson: (title, [(start,end,idx_in_all)])
    for title, srt in lessons:
        cues = parse_srt(srt.read_text(encoding="utf-8", errors="replace")) if srt else []
        refs = []
        for (s, e, t) in cues:
            refs.append((s, e, len(all_texts))); all_texts.append(t)
        per_lesson.append((title, refs))
    n_with = sum(1 for _, s in lessons if s)
    log(f"{len(lessons)} bai ({n_with} co phu de) · {len(all_texts)} dong phu de -> dich...")
    vi = translate_lines(all_texts, log=log) if all_texts else []

    # --- SRT song ngu (gop, offset thoi gian) ---
    srt_out = []; idx = 1; offset = 0
    for title, refs in per_lesson:
        if not refs: continue
        # cue tieu de bai
        srt_out.append(f"{idx}\n{_fmt(offset)} --> {_fmt(offset+1500)}\n=== {title} ===\n"); idx += 1
        base = offset + 2000
        last = base
        for (s, e, k) in refs:
            st = base + s; en = base + e
            en_text = all_texts[k]; vn_text = vi[k] if k < len(vi) else ""
            srt_out.append(f"{idx}\n{_fmt(st)} --> {_fmt(en)}\n{en_text}\n{vn_text}\n"); idx += 1
            last = max(last, en)
        offset = last + GAP_MS
    (out / "PhuDe_SongNgu.srt").write_text("\n".join(srt_out), encoding="utf-8")

    # --- Transcript tieng Viet (gop theo bai) ---
    md = [f"# {C.COURSE or root.name} — Transcript (dịch tiếng Việt)", "",
          "*Bản dịch tự động (Google) — dùng để đọc nhanh; tham chiếu bản gốc khi cần.*", ""]
    for title, refs in per_lesson:
        md.append(f"## {title}"); md.append("")
        if not refs:
            md.append("*(bài này chưa có phụ đề — sẽ bổ sung sau khi bóc lời)*"); md.append(""); continue
        para = " ".join((vi[k] if k < len(vi) else "") for (_, _, k) in refs).strip()
        md.append(para); md.append("")
    (out / "Transcript_VI.md").write_text("\n".join(md), encoding="utf-8")
    log(f">> {out/'PhuDe_SongNgu.srt'}")
    log(f">> {out/'Transcript_VI.md'}")
    return out


def main():
    import common as K
    K.setup_console()
    ap = argparse.ArgumentParser(description="Tao bundle bao cao (transcript VI + srt song ngu)")
    ap.add_argument("--section", help="Ten chuong top-level duoi SkoolCourse, vd '01 - AI Foundations'")
    ap.add_argument("--root", help="Hoac duong dan folder khoa rieng (courses/X)")
    ap.add_argument("--out", required=True, help="Thu muc dau ra (folder khoa trong BaoCao)")
    a = ap.parse_args()
    root = Path(a.root) if a.root else (C.BASE / "SkoolCourse" / a.section)
    if a.section: C.COURSE = a.section.split(" - ", 1)[-1]
    build(root, a.out)


if __name__ == "__main__":
    main()
