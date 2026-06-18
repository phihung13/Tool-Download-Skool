"""
Quet tien do mot khoa tu vid_*.json + file video tren dia.

Module nay KHONG phu thuoc vao trang thai toan cuc (C.ROOT) -> nhan thang
duong dan thu muc khoa, nho the GUI quet duoc bat ky khoa nao ma khong phai
doi config. Dung chung cho: Buoc 1/3 (hien % hoan thanh + con bao nhieu bai),
nut "Tai tiep", va nut "Cuu bai native het han".

Native Skool dung token JWT (claim `exp`) song ~24h -> doc thang exp de biet
token het han ma KHONG can tai thu.
"""
import os, json, time, base64
from pathlib import Path
import common as K
import config as C

NATIVE_HOST = "stream.video.skool.com"


def video_in(folder):
    """Tra ve file video da tai (video.mp4/webm/...) neu co va > 0 byte."""
    for ext in C.VIDEXT:
        p = folder / ("video" + ext)
        try:
            if p.exists() and p.stat().st_size > 0:
                return p
        except OSError:
            pass
    return None


def host_of(url):
    if url and "://" in url:
        return url.split("/")[2].lower()
    return ""


def is_native(url):
    return NATIVE_HOST in (url or "")


def native_token_exp(url):
    """Doc claim `exp` (epoch) trong token JWT cua link native. None neu khong doc duoc."""
    if "token=" not in (url or ""):
        return None
    tok = url.split("token=", 1)[1].split("&", 1)[0]
    parts = tok.split(".")
    if len(parts) < 2:
        return None
    try:
        seg = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(seg.encode()))
        exp = payload.get("exp")
        return int(exp) if exp is not None else None
    except Exception:
        return None


def _chapter_folder(root, ctitle):
    """Tim folder chuong khop ten (phan sau ' - ') trong `root`."""
    if not root.exists():
        return None
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        nm = d.name.split(" - ", 1)[-1] if " - " in d.name else d.name
        if nm == ctitle:
            return d
    return None


def _count_urls(nodes):
    c = 0
    for n in nodes:
        if n.get("url"):
            c += 1
        c += _count_urls(n.get("children") or [])
    return c


def _best_chapters(root):
    """Gom ban tot nhat (nhieu link nhat) cho moi chuong tu cac vid_*.json."""
    best = {}
    for f in sorted(root.rglob("vid_*.json")):
        try:
            d = json.loads(f.read_bytes().decode("utf-8-sig"))
        except Exception:
            continue
        if isinstance(d, dict):
            d = [d]
        course = K.one_chapter(d)
        ct = K.san(course["title"])
        sc = _count_urls(course.get("children") or [])
        if ct not in best or sc > best[ct][0]:
            best[ct] = (sc, course)
    return best


def scan(root):
    """Quet 1 khoa. Tra ve dict:
       chapters: [{name, title, folder, done, total}]
       total, done, size (byte)
       missing:        [lesson chua co video]  moi cai {folder,url,host,native,chapter,title}
       native_expired: [lesson native + token het han + chua tai]  (con dump lai moi tai duoc)
       has_data: co vid_*.json hay khong
    """
    root = Path(root)
    now = time.time()
    best = _best_chapters(root)
    chapters = []
    total = done = 0
    size = 0
    missing = []
    native_expired = []
    for ct, (sc, course) in sorted(best.items()):
        chap = _chapter_folder(root, ct)
        cdone = ctot = 0
        lessons = K.walk(course.get("children") or [], chap or root)
        for folder, node in lessons:
            url = node.get("url")
            if not url:
                continue
            ctot += 1
            total += 1
            v = video_in(folder) if chap else None
            if v:
                cdone += 1
                done += 1
                try:
                    size += v.stat().st_size
                except OSError:
                    pass
            else:
                rec = {"folder": folder, "url": url, "host": host_of(url),
                       "native": is_native(url), "chapter": ct,
                       "title": node.get("title", "")}
                missing.append(rec)
                if rec["native"]:
                    exp = native_token_exp(url)
                    if exp is not None and exp < now:
                        native_expired.append(rec)
        chapters.append({"name": chap.name if chap else ct, "title": ct,
                         "folder": chap, "done": cdone, "total": ctot})
    return {"root": root, "has_data": bool(best), "chapters": chapters,
            "total": total, "done": done, "size": size,
            "missing": missing, "native_expired": native_expired}


def tree(root):
    """Cay day du cho GUI: list chuong, moi chuong co list bai.
       chuong: {name, title, folder, done, total, lessons:[...]}
       bai:    {folder, rel, title, url, host, native, done, size}
       rel = duong dan tuong doi vs course root (truyen cho main.py --lesson)."""
    root = Path(root)
    best = _best_chapters(root)
    chapters = []
    for ct, (sc, course) in sorted(best.items()):
        chap = _chapter_folder(root, ct)
        lessons = []; cdone = 0
        for folder, node in K.walk(course.get("children") or [], chap or root):
            url = node.get("url")
            if not url:
                continue
            v = video_in(folder) if chap else None
            done = bool(v); sz = 0
            if v:
                cdone += 1
                try: sz = v.stat().st_size
                except OSError: pass
            rel = str(folder).replace(str(root) + os.sep, "")   # luon la duong dan (khong dung ten bai)
            lessons.append({"folder": folder, "rel": rel, "title": node.get("title", ""),
                            "url": url, "host": host_of(url), "native": is_native(url),
                            "done": done, "size": sz})
        chapters.append({"name": chap.name if chap else ct, "title": ct, "folder": chap,
                         "done": cdone, "total": len(lessons), "lessons": lessons})
    return chapters


def remaining_chapter_titles(scan_result):
    """Ten (da san) cac chuong con thieu it nhat 1 bai -> de re-dump/cuu native."""
    seen = {}
    for rec in scan_result["missing"]:
        seen.setdefault(rec["chapter"], 0)
        seen[rec["chapter"]] += 1
    return seen


def expired_native_chapter_titles(scan_result):
    """Ten (da san) cac chuong co bai native het han token."""
    return sorted({rec["chapter"] for rec in scan_result["native_expired"]})
