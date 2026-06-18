"""
Cau hinh trung tam cho Skool Archiver.

Mac dinh: layout 1-khoa cu  ->  BASE/SkoolCourse  (giu nguyen cho khoa da tai).
Khi chay  --course "Ten khoa"  ->  BASE/courses/Ten khoa/   (JSON dump + output deu o day).

Co the override bang bien moi truong:
    SKOOL_BASE = duong dan goc (mac dinh E:\\SkoolProject)
"""
import os
from pathlib import Path

# ===================== DUONG DAN =====================
# config.py o ...\Archiver\app  ->  BASE = ...\SkoolProject  (len 2 cap: app -> Archiver -> SkoolProject).
# Khong hardcode o cung -> chay duoc tren may khac. Override bang bien moi truong SKOOL_BASE.
BASE = Path(os.environ.get("SKOOL_BASE") or Path(__file__).resolve().parents[2])

# Mac dinh = khoa cu (1 thu muc SkoolCourse). set_course()/set_root() se doi cac gia tri nay.
COURSE    = None
ROOT      = BASE / "SkoolCourse"   # noi chua cac folder chuong/bai + video
DUMP_ROOT = BASE                   # noi tim de quy cac file JSON dump (vid_/meta_/Chap_)

def set_course(name: str):
    """Tro pipeline vao 1 khoa cu the duoi BASE/courses/<name>/."""
    global COURSE, ROOT, DUMP_ROOT
    COURSE = name
    ROOT = BASE / "courses" / name
    DUMP_ROOT = ROOT
    ROOT.mkdir(parents=True, exist_ok=True)

def set_root(path):
    """Override truc tiep thu muc lam viec (ca JSON lan output deu o day)."""
    global ROOT, DUMP_ROOT
    ROOT = Path(path)
    DUMP_ROOT = Path(path)

# ===================== PATTERN JSON =====================
VID_PATTERN  = "vid_*.json"    # link video moi bai
META_PATTERN = "meta_*.json"   # mo ta + resources moi bai
CHAP_PATTERN = "Chap*.json"    # cay chuong (tuy chon - de danh so chuong khi tao folder)
STRIP_EMOJI  = True

# ===================== VIDEO =====================
DRY_RUN     = False
ONLY_HOSTS  = []               # [] = tat ca; ["stream.video.skool.com"] = chi native
ONLY_CHAPTER = None            # ten chuong (da san) -> chi tai chuong nay (GUI: tai 1 chuong)
ONLY_LESSON  = None            # duong dan tuong doi bai (vs course root) -> chi tai 1 bai
JS_RUNTIME = "node"            # JS runtime cho yt-dlp de vuot "Sign in to confirm you're not a bot"
                               #   (deno/node). "" = tat. Yeu cau cai san (Node.js hoac Deno).
YT_COOKIES_FILE    = ""        # duong dan cookies.txt (Netscape) neu can dang nhap; "" = tat
YT_COOKIES_BROWSER = ""        # "firefox" (Chrome/Edge ban moi bi DPAPI -> KHONG dung). "" = tat
MAX_TRIES  = 6                 # so lan thu lai moi video khi loi
RETRY_WAIT = 8                 # giay nghi giua cac lan thu

# ===================== TRANSCRIBE =====================
# Engine: "faster-whisper" (nhanh, nhe RAM, khuyen dung) | "openai-whisper" (du phong)
WHISPER_ENGINE  = "faster-whisper"
# faster-whisper: "distil-large-v3" (English-only, nhanh/nho nhat) | "large-v3-turbo" | "large-v3"
# openai-whisper: "turbo" | "large-v3" | "medium" ...
WHISPER_MODEL   = "distil-large-v3"
WHISPER_LANG    = "en"          # None = tu nhan dien
WHISPER_TASK    = "transcribe"  # "transcribe" (giu nguyen ngon ngu) | "translate" (dich SANG tieng Anh)
WHISPER_DEVICE  = "auto"        # "auto" -> cuda neu co GPU NVIDIA, nguoc lai cpu
WHISPER_COMPUTE = "int8"        # CPU: int8 (nhanh) ; GPU: float16
WATCH_INTERVAL  = 90            # giay giua moi vong quet cua watcher
WATCH_MIN_AGE   = 60            # video phai "yen" it nhat bao nhieu giay moi transcribe (tranh file dang ghi)

VIDEXT = (".mp4", ".webm", ".mkv", ".mov")
