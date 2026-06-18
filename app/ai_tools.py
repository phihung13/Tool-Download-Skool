#!/usr/bin/env python3
"""
Dich tieng Viet + Tom tat/To-do bang AI cho noi dung khoa hoc.

  python ai_tools.py --course X --translate   # dich _TongHop.md -> _TongHop.vi.md
  python ai_tools.py --course X --summary     # tom tat + to-do (tieng Viet) -> _TomTat.md
  python ai_tools.py --check                  # xem dang dung dich vu nao

Dich vu (tu chon, theo thu tu uu tien):
  1) Claude API  -> API key dat o app (nut "Xuat & Bao cao") HOAC bien moi truong
     ANTHROPIC_API_KEY. Chat luong tot nhat; dich + tom tat + to-do deu dung duoc.
     Model qua ANTHROPIC_MODEL (mac dinh sonnet).
  2) deep-translator (Google mien phi) -> chi DICH; can: pip install deep-translator.

Tom tat/To-do bat buoc Claude API. Goi API qua `requests` (khong can SDK rieng).
"""
import argparse, os, time, json
from pathlib import Path
import config as C
import export as E

API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
CHUNK = 7000          # ky tu moi lan goi (cat theo doan de dich/tom tat on dinh)
SETTINGS_FILE = Path(__file__).resolve().parent / ".settings.json"   # luu API key tren may (gitignore)


# ----------------------------- cai dat (API key) -----------------------------
def load_settings():
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_setting(key, value):
    s = load_settings(); s[key] = value
    SETTINGS_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")


def get_api_key():
    """Uu tien bien moi truong, roi den key da luu trong app."""
    return (os.environ.get("ANTHROPIC_API_KEY") or load_settings().get("anthropic_api_key") or "").strip()


def api_key_source():
    if os.environ.get("ANTHROPIC_API_KEY"): return "env"
    if load_settings().get("anthropic_api_key"): return "app"
    return None


# ----------------------------- nha cung cap -----------------------------
def have_api():
    return bool(get_api_key())


def have_google():
    import importlib.util
    return importlib.util.find_spec("deep_translator") is not None


def status():
    return {"claude": have_api(), "google": have_google(), "model": DEFAULT_MODEL,
            "source": api_key_source()}


def _claude(messages, system=None, model=None, max_tokens=4096):
    import requests
    key = get_api_key()
    if not key:
        raise RuntimeError("Chua co API key Claude. Vao 'Xuat & Bao cao' -> dan API key, hoac dat bien ANTHROPIC_API_KEY.")
    body = {"model": model or DEFAULT_MODEL, "max_tokens": max_tokens, "messages": messages}
    if system:
        body["system"] = system
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    last = ""
    for a in range(4):
        try:
            r = requests.post(API_URL, headers=headers, json=body, timeout=180)
        except Exception as e:
            last = str(e); time.sleep(5 * (a + 1)); continue
        if r.status_code == 200:
            data = r.json()
            return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()
        last = f"{r.status_code}: {r.text[:300]}"
        if r.status_code in (429, 500, 502, 503, 529):
            time.sleep(6 * (a + 1)); continue
        break
    raise RuntimeError(f"Claude API loi -> {last}")


# ----------------------------- cat doan -----------------------------
def chunks(text, size=CHUNK):
    text = text or ""
    if len(text) <= size:
        return [text] if text.strip() else []
    out, buf = [], ""
    for para in text.split("\n\n"):
        if len(buf) + len(para) + 2 > size and buf:
            out.append(buf); buf = ""
        if len(para) > size:                      # doan qua dai -> cat tho
            for i in range(0, len(para), size):
                out.append(para[i:i + size])
        else:
            buf += (("\n\n" if buf else "") + para)
    if buf.strip():
        out.append(buf)
    return out


# ----------------------------- DICH -----------------------------
SYS_TRANSLATE = ("Ban la bien dich vien chuyen nghiep. Dich sang TIENG VIET tu nhien, "
                 "de hieu. GIU NGUYEN dinh dang Markdown (tieu de #, danh sach, **dam**, "
                 "lien ket, code). Khong them loi binh, chi tra ve ban dich.")


def translate_text(text, log=print):
    if not (text or "").strip():
        return text
    if have_api():
        parts = []
        cs = chunks(text)
        for i, c in enumerate(cs, 1):
            log(f"   dich (Claude) {i}/{len(cs)}...")
            parts.append(_claude([{"role": "user", "content": c}], system=SYS_TRANSLATE, max_tokens=8000))
        return "\n\n".join(parts)
    if have_google():
        from deep_translator import GoogleTranslator
        tr = GoogleTranslator(source="auto", target="vi")
        parts = []
        cs = chunks(text, 4500)                    # Google gioi han ~5000
        for i, c in enumerate(cs, 1):
            log(f"   dich (Google) {i}/{len(cs)}...")
            parts.append(tr.translate(c))
        return "\n\n".join(parts)
    raise RuntimeError("Chua co dich vu dich. Dat ANTHROPIC_API_KEY hoac: pip install deep-translator")


def translate_md_file(src, dst=None, log=print):
    src = Path(src)
    if not src.exists():
        raise FileNotFoundError(src)
    dst = Path(dst) if dst else src.with_suffix(".vi" + src.suffix)
    log(f"Dich {src.name} -> {dst.name}")
    dst.write_text(translate_text(src.read_text(encoding="utf-8", errors="replace"), log=log), encoding="utf-8")
    return dst


def run_translate(root, log=print):
    root = Path(root)
    md = root / "_TongHop.md"
    if not md.exists():
        log("Chua co _TongHop.md -> tao truoc...")
        E.run(root=root)
    if not md.exists():
        log("Khong co noi dung de dich."); return None
    out = translate_md_file(md, root / "_TongHop.vi.md", log=log)
    log(f">> Da dich: {out}")
    return out


# ----------------------------- TOM TAT + TO-DO -----------------------------
SYS_SUMMARY = (
    "Ban la tro ly dao tao cua Truong Viet Anh (he thong giao duc o Viet Nam). "
    "Doc noi dung mot CHUONG khoa hoc (tieng Anh) va viet bang TIENG VIET:\n"
    "1) Tom tat ngan gon cac y chinh (gach dau dong).\n"
    "2) Muc 'To-do ap dung cho Truong Viet Anh': cac viec cu the co the lam ngay, "
    "lien he boi canh truong hoc/giao duc Viet Nam.\n"
    "Ngan gon, ro rang, uu tien tinh ung dung. Tra ve Markdown.")


def _chapter_text(blocks, start):
    """Gom van ban (mo ta + transcript) cua 1 chuong top-level bat dau tu index start."""
    buf = []
    depth0 = blocks[start]["depth"]
    i = start + 1
    while i < len(blocks) and blocks[i]["depth"] > depth0:
        b = blocks[i]
        head = "#" * (b["depth"]) + " " + b["title"]
        buf.append(head)
        if b["desc"]:
            buf.append(b["desc"])
        if b["transcript"]:
            buf.append(b["transcript"])
        i += 1
    return "\n\n".join(buf), i


def summarize_course(root, log=print):
    if not have_api():
        raise RuntimeError("Tom tat/To-do can API key Claude. Vao 'Xuat & Bao cao' dan API key roi thu lai.")
    root = Path(root)
    title, blocks = E.gather_course(root)
    if not blocks:
        log("Khong co noi dung de tom tat."); return None
    # cac chuong top-level = depth nho nhat
    if not blocks:
        return None
    top = min(b["depth"] for b in blocks)
    out = [f"# Tóm tắt & To-do — {title}", ""]
    i = 0
    while i < len(blocks):
        b = blocks[i]
        if b["depth"] != top:
            i += 1; continue
        text, nxt = _chapter_text(blocks, i)
        # neu chuong la 1 bai don (khong co con) thi lay desc/transcript cua chinh no
        if not text.strip() and b["kind"] == "lesson":
            text = "\n\n".join(x for x in (b["desc"], b["transcript"]) if x)
        log(f"Tom tat chuong: {b['title']}")
        out.append(f"## {b['title']}")
        if text.strip():
            cs = chunks(text, 14000)               # context lon -> cat thua de an toan
            notes = []
            for j, c in enumerate(cs, 1):
                if len(cs) > 1:
                    log(f"   phan {j}/{len(cs)}...")
                notes.append(_claude([{"role": "user", "content": c}], system=SYS_SUMMARY, max_tokens=2000))
            out.append("\n\n".join(notes))
        else:
            out.append("*(chương chưa có nội dung)*")
        out.append("")
        i = nxt if nxt > i else i + 1
    dst = root / "_TomTat.md"
    dst.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
    log(f">> Tóm tắt + To-do: {dst}")
    return dst


def main():
    import common as K
    K.setup_console()
    ap = argparse.ArgumentParser(description="Dich / Tom tat noi dung khoa bang AI")
    ap.add_argument("--course", help="Ten khoa duoi courses/. Bo trong = SkoolCourse.")
    ap.add_argument("--translate", action="store_true", help="Dich _TongHop.md sang tieng Viet.")
    ap.add_argument("--summary", action="store_true", help="Tom tat + To-do (tieng Viet).")
    ap.add_argument("--check", action="store_true", help="Xem dich vu AI dang co.")
    a = ap.parse_args()
    if a.check:
        s = status()
        src = {"env": " (tu bien moi truong)", "app": " (luu trong app)"}.get(s["source"], "")
        print(f"Claude API : {'CO' if s['claude'] else 'KHONG'}{src} (model {s['model']})")
        print(f"Google dich: {'CO' if s['google'] else 'KHONG'}")
        return
    if a.course:
        C.set_course(a.course)
    if a.translate:
        run_translate(C.ROOT)
    if a.summary:
        summarize_course(C.ROOT)
    if not (a.translate or a.summary):
        print("Chon --translate va/hoac --summary (hoac --check).")


if __name__ == "__main__":
    main()
