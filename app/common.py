import json, re, socket, sys, time
from pathlib import Path
import config as C

def setup_console():
    """Ep stdout/stderr sang UTF-8 de in ten folder co ky tu la (vd '▶') khong crash
       tren Windows (console mac dinh cp1252). Goi 1 lan o dau chuong trinh."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

EMOJI = re.compile("[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF"
                   "\u2190-\u21FF\u2B00-\u2BFF\u2300-\u23FF\uFE0F\u200D]")

def san(s):
    s = s or ""
    if C.STRIP_EMOJI: s = EMOJI.sub("", s)
    s = re.sub(r'[<>:"/\\|?*\n\r\t]', "", s)
    s = re.sub(r"\s+", " ", s).strip()[:120]
    return s.rstrip(" .") or "untitled"

def san_file(name):
    name = name or "file"
    if C.STRIP_EMOJI: name = EMOJI.sub("", name)
    name = re.sub(r'[<>:"/\\|?*\n\r\t]', "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:150].rstrip(" .") or "file"

def one_chapter(roots):
    if not roots: return {"title": "", "children": []}   # file vid_*.json rong ([]) -> bo qua an toan
    withkids = [r for r in roots if r.get("children")]
    main = withkids[0] if withkids else roots[0]
    for e in [r for r in roots if r is not main]:
        main.setdefault("children", []).append(e)
    return main

def walk(nodes, base, lessons=None):
    if lessons is None: lessons = []
    for i, n in enumerate(nodes, 1):
        folder = base / f"{i:02d} - {san(n['title'])}"
        kids = n.get("children") or []
        if kids: walk(kids, folder, lessons)
        else: lessons.append((folder, n))
    return lessons

def find_chapter_folder(ctitle):
    if not C.ROOT.exists(): return None
    for d in sorted([p for p in C.ROOT.iterdir() if p.is_dir()]):
        nm = d.name.split(" - ", 1)[-1] if " - " in d.name else d.name
        if nm == ctitle: return d
    return None

def load_best(pattern, score_fn):
    """Doc tat ca file khop pattern (de quy duoi DUMP_ROOT cua khoa), loai trung lap:
       moi chuong giu ban diem cao nhat. Tra ve list (ctitle, path, course_root)."""
    best = {}
    for f in sorted(C.DUMP_ROOT.rglob(pattern)):
        try:
            d = json.loads(f.read_bytes().decode("utf-8-sig"))
        except Exception as e:
            print(f"[skip] {f.name}: {e}"); continue
        if isinstance(d, dict): d = [d]
        course = one_chapter(d); ct = san(course["title"])
        sc = score_fn(course.get("children") or [])
        if ct not in best or sc > best[ct][0]:
            best[ct] = (sc, f, course)
    return [(ct, v[1], v[2]) for ct, v in sorted(best.items())]

# ---- mang ----
def online():
    try: socket.create_connection(("1.1.1.1", 53), timeout=4).close()
    except OSError: return False
    try: socket.gethostbyname("www.youtube.com"); return True
    except OSError: return False

def wait_online():
    if online(): return
    print("   [MANG] Mat ket noi - tam dung, cho mang...", flush=True)
    t = 0
    while not online():
        time.sleep(10); t += 10
        if t % 60 == 0: print(f"   [MANG] Van chua co mang... ({t}s)", flush=True)
    print("   [MANG] Co mang lai - tiep tuc.", flush=True)

def ffmpeg_dir():
    try:
        import ffmpeg_downloader as ffdl
        p = getattr(ffdl, "ffmpeg_path", None)
        if p: return str(Path(p).parent)
    except Exception: pass
    return None

# ---- tao + danh so folder chuong (cho khoa moi chua co folder nao) ----
def _existing_chapter_max():
    """So thu tu lon nhat trong cac folder chuong dang co (de danh so chuong moi tiep theo)."""
    mx = 0
    if not C.ROOT.exists(): return 0
    for d in C.ROOT.iterdir():
        if d.is_dir():
            m = re.match(r"\s*(\d+)\s*-", d.name)
            if m: mx = max(mx, int(m.group(1)))
    return mx

def load_chapter_order():
    """Thu tu chuong de danh so {ten chuong (da san) -> so}. Uu tien:
       1) file _chapters.json / _chapters.txt do extractor xuat (1 ten chuong / dong, dung thu tu)
       2) so trong ten file Chap<N>.json  (Chap1_.. -> chuong 1)
       3) {} (se danh so theo thu tu phat hien)."""
    # 1) _chapters.json / .txt
    for nm in ("_chapters.json", "_chapters.txt"):
        p = C.DUMP_ROOT / nm
        if p.exists():
            try:
                if nm.endswith(".json"):
                    arr = json.loads(p.read_bytes().decode("utf-8-sig"))
                    titles = [san(x["title"] if isinstance(x, dict) else x) for x in arr]
                else:
                    titles = [san(t) for t in p.read_text(encoding="utf-8-sig").splitlines() if t.strip()]
                return {t: i for i, t in enumerate(titles, 1)}
            except Exception:
                pass
    # 2) Chap<N>_*.json
    order = {}
    for f in sorted(C.DUMP_ROOT.rglob(C.CHAP_PATTERN)):
        m = re.search(r"Chap(\d+)", f.name)
        if not m: continue
        try:
            d = json.loads(f.read_bytes().decode("utf-8-sig"))
            if isinstance(d, dict): d = [d]
            ct = san(one_chapter(d)["title"])
            order.setdefault(ct, int(m.group(1)))
        except Exception:
            pass
    return order

def ensure_chapter_folder(ctitle, order):
    """Tra ve folder chuong; tao moi neu chua co (danh so theo order hoac tiep noi so lon nhat)."""
    chap = find_chapter_folder(ctitle)
    if chap is not None:
        return chap, False
    num = order.get(ctitle)
    if num is None:
        num = _existing_chapter_max() + 1
    chap = C.ROOT / f"{num:02d} - {ctitle}"
    chap.mkdir(parents=True, exist_ok=True)
    return chap, True