#!/usr/bin/env python3
"""
Giao dien (GUI) hien dai cho Skool Archiver - CustomTkinter.
Mo bang: double-click GiaoDien.cmd
"""
import os, sys, time, queue, threading, subprocess
from pathlib import Path
import customtkinter as ctk
from tkinter import messagebox

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C
import progress as P
import common as K

HERE = Path(__file__).resolve().parent
ARCHIVER = HERE.parent
PY = sys.executable.replace("pythonw.exe", "python.exe")
NO_WIN = 0x08000000 if os.name == "nt" else 0
SENTINEL = "\x00DONE\x00"

# ===== palette (light, monochrome / black & white) =====
BG = "#F4F4F5"; SIDE = "#0A0A0B"; SIDE_HI = "#1C1C20"; CARD = "#FFFFFF"; CARD2 = "#ECECEE"
PRIMARY = "#111114"; PRIMARY_H = "#2C2C31"
SUCCESS = "#111114"; WARNING = "#52525B"; DANGER = "#3F3F46"
TEXT = "#18181B"; TEXT2 = "#71717A"; ON_SIDE = "#A1A1AA"; BORDER = "#E4E4E7"
FT = "Segoe UI"
STEPS = ["Chọn khóa", "Lấy khóa", "Tùy chọn", "Tải về"]
ICON = {"done": ("✓", "#111114"), "loading": ("⏳", "#52525B"), "pending": ("•", "#C7C7CC")}

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


def btn(parent, text, cmd, kind="primary", **kw):
    pal = {"primary": (PRIMARY, PRIMARY_H, "white"), "success": (PRIMARY, PRIMARY_H, "white"),
           "danger": (DANGER, "#27272A", "white"), "secondary": ("#E4E4E7", "#D4D4D8", TEXT),
           "ghost": ("transparent", CARD2, TEXT), "warn": (DANGER, "#27272A", "white")}
    fg, hov, tc = pal.get(kind, pal["primary"])
    opt = dict(corner_radius=9, height=40, font=(FT, 13, "bold"), fg_color=fg, hover_color=hov, text_color=tc)
    if kind == "ghost": opt["border_width"] = 0
    opt.update(kw)
    return ctk.CTkButton(parent, text=text, command=cmd, **opt)


def fmt_size(n):
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or u == "TB": return f"{int(n)} B" if u == "B" else f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} TB"


class App:
    def __init__(self, root):
        self.root = root
        self.proc = None; self.sb = None; self.q = queue.Queue(); self.ui_q = queue.Queue()
        self.chapters = []; self.course_name = None; self.mode = None
        self.admin = False; self._dumping = False; self._prog = []; self._lastref = 0.0
        self.step = 1; self.chap_widgets = {}
        self.purpose = "import"          # import | update | rescue (muc dich phien trinh duyet)
        self.known_titles = set()        # ten chuong da luu (de danh dau MOI khi cap nhat)
        self.live_titles = []            # thu tu chuong day du tu lan list gan nhat
        self.target_titles = set()       # chuong can re-dump (cuu native het han)
        self.last_scan = None            # ket qua progress.scan gan nhat
        self.scan_cache = {}             # {display item -> scan} cho Buoc 1 (de hien dung luong khi xoa)
        self._cfg_lock = threading.Lock()  # serialize khi tam set config.C (tao folder)
        self._in_err = False             # tranh de quy man hinh loi

        root.title("Skool Archiver"); root.geometry("820x620"); root.minsize(580, 420)
        root.configure(fg_color=BG)
        root.grid_columnconfigure(1, weight=1); root.grid_rowconfigure(0, weight=1)

        # ---------- sidebar ----------
        side = ctk.CTkFrame(root, width=206, corner_radius=0, fg_color=SIDE)
        side.grid(row=0, column=0, sticky="nsw"); side.grid_propagate(False)
        ctk.CTkLabel(side, text="📦  Skool Archiver", font=(FT, 18, "bold"), text_color="white").pack(anchor="w", padx=22, pady=(26, 4))
        ctk.CTkLabel(side, text="Lưu trữ khóa học Skool", font=(FT, 11), text_color=ON_SIDE).pack(anchor="w", padx=22, pady=(0, 22))
        self.step_box = ctk.CTkFrame(side, fg_color="transparent"); self.step_box.pack(fill="x", padx=14)
        self.badge = ctk.CTkLabel(side, text="", font=(FT, 12, "bold"), text_color="white"); self.badge.pack(side="bottom", anchor="w", padx=22, pady=(0, 8))
        btn(side, "⚙  Kiểm tra môi trường", self.show_check, kind="ghost", text_color="white", hover_color=SIDE_HI, anchor="w").pack(side="bottom", fill="x", padx=14, pady=(0, 6))
        btn(side, "📄  Xuất & Báo cáo", self.show_report, kind="ghost", text_color="white", hover_color=SIDE_HI, anchor="w").pack(side="bottom", fill="x", padx=14, pady=(0, 2))

        # ---------- main ----------
        main = ctk.CTkFrame(root, corner_radius=0, fg_color=BG); main.grid(row=0, column=1, sticky="nsew")
        main.grid_rowconfigure(0, weight=1); main.grid_columnconfigure(0, weight=1)
        # Vung noi dung CUON DOC -> man hinh thap mac may cung khong giau widget, tu hien thanh keo.
        self.content = ctk.CTkScrollableFrame(main, fg_color="transparent", corner_radius=0,
                                              scrollbar_button_color=BORDER, scrollbar_button_hover_color=TEXT2)
        self.content.grid(row=0, column=0, sticky="nsew", padx=(20, 6), pady=(14, 4))
        logwrap = ctk.CTkFrame(main, fg_color="transparent"); logwrap.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 12))
        ctk.CTkLabel(logwrap, text="Nhật ký", font=(FT, 11, "bold"), text_color=TEXT2).pack(anchor="w")
        self.log = ctk.CTkTextbox(logwrap, height=80, font=("Consolas", 11), fg_color=CARD, text_color=TEXT, corner_radius=10)
        self.log.pack(fill="x"); self.log.configure(state="disabled")

        root.report_callback_exception = self._tk_err   # KHONG bao gio de man hinh trang/ket vi loi nuot im
        root.bind_all("<Control-Alt-t>", self.toggle_admin); root.bind_all("<Control-Alt-T>", self.toggle_admin)
        self.render_sidebar(); self.show_step1()
        self.root.after(120, self.poll)

    # ---------- bat MOI loi giao dien -> ghi log + man hinh phuc hoi (khong bao gio trang/ket) ----------
    def _tk_err(self, exc, val, tb):
        import traceback
        full = "".join(traceback.format_exception(exc, val, tb))
        try:
            (ARCHIVER / "logs").mkdir(parents=True, exist_ok=True)
            with (ARCHIVER / "logs" / "gui_error.log").open("a", encoding="utf-8") as f:
                f.write(full + "\n")
        except Exception: pass
        try: self.write("[LỖI GIAO DIỆN] " + (str(val) or exc.__name__))
        except Exception: pass
        if self._in_err: return            # dang hien man hinh loi -> dung de quy
        self._in_err = True
        try: self._show_error(str(val) or exc.__name__, full)
        except Exception: pass
        finally: self._in_err = False

    def _show_error(self, short, full):
        self.clear()
        self.head("Đã xảy ra lỗi", "App gặp trục trặc ở thao tác vừa rồi nhưng vẫn chạy bình thường. Bấm nút bên dưới để tiếp tục.")
        card = self.card()
        ctk.CTkLabel(card, text=short, font=(FT, 13, "bold"), text_color=DANGER, wraplength=520, justify="left").pack(anchor="w", padx=16, pady=(12, 4))
        box = ctk.CTkTextbox(card, height=150, font=("Consolas", 10), fg_color="#FFF7ED", text_color="#7C2D12", corner_radius=8)
        box.pack(fill="x", padx=12, pady=(2, 12)); box.insert("end", full[-2500:]); box.configure(state="disabled")
        row = ctk.CTkFrame(self.content, fg_color="transparent"); row.pack(fill="x", pady=10)
        btn(row, "←  Về đầu", self.show_step1, kind="ghost", width=120).pack(side="left")
        btn(row, "📁  Mở thư mục log", lambda: self._open_path(ARCHIVER / "logs"), kind="secondary", width=170).pack(side="left", padx=8)

    def _open_path(self, p):
        try: os.startfile(str(p))
        except Exception: pass

    # ---------- sidebar steps ----------
    def render_sidebar(self):
        for w in self.step_box.winfo_children(): w.destroy()
        for i, name in enumerate(STEPS, 1):
            active = (i == self.step)
            fr = ctk.CTkFrame(self.step_box, fg_color=(SIDE_HI if active else "transparent"), corner_radius=9)
            fr.pack(fill="x", pady=3)
            dot = ctk.CTkLabel(fr, text=str(i), width=26, height=26, corner_radius=13,
                               fg_color=("white" if active else "#2A2A2E"),
                               text_color=("#0A0A0B" if active else ON_SIDE), font=(FT, 12, "bold"))
            dot.pack(side="left", padx=(8, 10), pady=8)
            ctk.CTkLabel(fr, text=name, font=(FT, 13, "bold" if active else "normal"),
                         text_color=("white" if active else ON_SIDE)).pack(side="left")

    def set_step(self, n):
        self.step = n; self.render_sidebar()

    # ---------- helpers ----------
    def clear(self):
        for w in self.content.winfo_children(): w.destroy()
        self.chap_widgets = {}
        # Xoa cac tham chieu widget cua man hinh cu -> hasattr() guard moi noi chinh xac (tranh dung widget da huy)
        for a in ("mgr_scroll", "mgr_status", "chap_scroll", "chap_hdr", "sum_lbl", "native_banner",
                  "status4", "pct_lbl", "pb4", "run_lbl", "done_row", "trans_lbl", "trans_pb", "tl_lbl",
                  "dump_status", "dump_pb", "b_start", "b_all", "b_dump", "b_list", "b_open", "chap_box", "dump_row"):
            if hasattr(self, a): delattr(self, a)

    def toggle_admin(self, *_):
        self.admin = not self.admin
        self.badge.configure(text="🔧 TEST MODE" if self.admin else "")
        self.write("== Chế độ TEST: BẬT (tải sẽ KHÔNG tải thật) ==" if self.admin else "== Chế độ TEST: TẮT ==")

    def head(self, text, sub=""):
        ctk.CTkLabel(self.content, text=text, font=(FT, 22, "bold"), text_color=TEXT).pack(anchor="w", pady=(0, 2))
        if sub:
            ctk.CTkLabel(self.content, text=sub, font=(FT, 13), text_color=TEXT2, justify="left", wraplength=520).pack(anchor="w", pady=(0, 12))

    def card(self):
        c = ctk.CTkFrame(self.content, fg_color=CARD, corner_radius=14, border_width=1, border_color=BORDER)
        c.pack(fill="x", pady=8); return c

    def write(self, s):
        self._flush_log([s.rstrip("\n")])

    def _flush_log(self, lines):
        """Ghi NHIEU dong 1 lan (giam giat). Gop cac dong tien do '[download] x%' lien tiep
           thanh 1 dong (yt-dlp --newline phun hang tram dong/giay)."""
        merged = []
        for s in lines:
            prog = s.startswith("[download]") and "%" in s
            if prog and merged and merged[-1][1]:
                merged[-1] = (s, True)          # de len dong tien do truoc do
            else:
                merged.append((s, prog))
        self.log.configure(state="normal")
        for s, _ in merged:
            self.log.insert("end", s + "\n")
        # cat bot cho nhe (giu ~400 dong cuoi)
        try:
            n = int(self.log.index("end-1c").split(".")[0])
            if n > 600:
                self.log.delete("1.0", f"{n - 400}.0")
        except Exception:
            pass
        self.log.see("end"); self.log.configure(state="disabled")

    def course_root(self, name=None):
        name = name or self.course_name
        if not name or str(name).startswith("SkoolCourse"): return C.BASE / "SkoolCourse"
        return C.BASE / "courses" / name

    def existing_courses(self):
        items = []
        if (C.BASE / "SkoolCourse").exists(): items.append("SkoolCourse (đã có sẵn)")
        cdir = C.BASE / "courses"
        if cdir.exists(): items += sorted(p.name for p in cdir.iterdir() if p.is_dir())
        return items

    def item_course(self, item):
        """Display item -> ten khoa (None = SkoolCourse cu)."""
        return None if (not item or item.startswith("SkoolCourse")) else item

    def item_root(self, item):
        return self.course_root(self.item_course(item))

    # ---------- chay nen + tra ket qua ve luong giao dien ----------
    def run_async(self, fn, cb):
        """Chay fn() o thread phu, day cb(ket_qua) vao ui_q de poll() goi tren main thread."""
        def work():
            try: r = fn()
            except Exception as e: r = e
            self.ui_q.put(lambda: cb(r))
        threading.Thread(target=work, daemon=True).start()

    # ---------- tien do theo chuong ----------
    def _video_in(self, folder):
        for ext in C.VIDEXT:
            p = folder / ("video" + ext)
            try:
                if p.exists() and p.stat().st_size > 0: return p
            except OSError: pass
        return None

    def build_progress(self):
        import json, common as K
        self._prog = []; root = self.course_root()
        if not root.exists(): return
        def chap_folder(ct):
            for d in sorted([p for p in root.iterdir() if p.is_dir()]):
                nm = d.name.split(" - ", 1)[-1] if " - " in d.name else d.name
                if nm == ct: return d
        def cu(ns):
            c = 0
            for n in ns: c += (1 if n.get("url") else 0) + cu(n.get("children") or [])
            return c
        best = {}
        for f in sorted(root.rglob("vid_*.json")):
            try: d = json.loads(f.read_bytes().decode("utf-8-sig"))
            except Exception: continue
            if isinstance(d, dict): d = [d]
            course = K.one_chapter(d); ct = K.san(course["title"]); sc = cu(course.get("children") or [])
            if ct not in best or sc > best[ct][0]: best[ct] = (sc, course)
        for ct, (sc, course) in sorted(best.items()):
            chap = chap_folder(ct)
            if not chap: continue
            lessons = [fd for fd, n in K.walk(course.get("children") or [], chap) if n.get("url")]
            self._prog.append({"name": chap.name, "lessons": lessons})

    def scan_progress(self):
        rows = []; dtot = etot = 0; size = 0
        for ch in self._prog:
            done = 0
            for folder in ch["lessons"]:
                v = self._video_in(folder)
                if v:
                    done += 1
                    try: size += v.stat().st_size
                    except OSError: pass
            exp = len(ch["lessons"]); stt = "done" if (exp and done >= exp) else ("loading" if done > 0 else "pending")
            rows.append({"name": ch["name"], "done": done, "exp": exp, "status": stt}); dtot += done; etot += exp
        return rows, dtot, etot, size

    # ====================== KIỂM TRA MÔI TRƯỜNG ======================
    def _ffmpeg_ok(self):
        import shutil
        if shutil.which("ffmpeg"): return True
        try:
            import ffmpeg_downloader as ffdl
            return bool(getattr(ffdl, "ffmpeg_path", None))
        except Exception: return False

    def _chromium_ok(self):
        base = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
        try: return base.exists() and any(base.glob("chromium-*"))
        except Exception: return False

    def check_env(self):
        import shutil, importlib.util
        def has(m): return importlib.util.find_spec(m) is not None
        sc = Path(PY).parent
        items = [("Python", True, f"{sys.version_info.major}.{sys.version_info.minor}", None)]
        node = shutil.which("node")
        items.append(("Node.js (cho YouTube)", bool(node), node or "thiếu", None if node else ("Tải Node.js", "node")))
        ff = self._ffmpeg_ok(); items.append(("ffmpeg", ff, "OK" if ff else "thiếu", None if ff else ("Cài ffmpeg", [str(sc / "ffdl.exe"), "install", "--add-path"])))
        for mod, label, pn in [("yt_dlp", "yt-dlp", "yt-dlp"), ("faster_whisper", "faster-whisper", "faster-whisper"), ("playwright", "Playwright", "playwright"), ("customtkinter", "CustomTkinter", "customtkinter")]:
            ok = has(mod); items.append((label, ok, "OK" if ok else "thiếu", None if ok else (f"Cài {label}", [PY, "-m", "pip", "install", "-U", pn])))
        ch = self._chromium_ok(); items.append(("Trình duyệt Chromium", ch, "OK" if ch else "thiếu", None if ch else ("Cài Chromium", [PY, "-m", "playwright", "install", "chromium"])))
        return items

    def env_missing(self): return [i for i in self.check_env() if not i[1]]

    def show_check(self):
        self.clear()
        self.head("Kiểm tra môi trường", "Các thành phần app cần. Cái nào thiếu có nút cài ngay bên cạnh (Node.js phải tải tay rồi mở lại app).")
        card = self.card()
        for name, ok, detail, fix in self.check_env():
            row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=14, pady=6)
            ctk.CTkLabel(row, text=("✓" if ok else "✗"), text_color=(SUCCESS if ok else DANGER), font=(FT, 15, "bold"), width=22).pack(side="left")
            ctk.CTkLabel(row, text=name, font=(FT, 13), text_color=TEXT, width=210, anchor="w").pack(side="left", padx=6)
            ctk.CTkLabel(row, text=detail, font=(FT, 11), text_color=TEXT2).pack(side="left")
            if (not ok) and fix: btn(row, fix[0], (lambda p=fix[1]: self.do_fix(p)), width=130).pack(side="right")
        row = ctk.CTkFrame(self.content, fg_color="transparent"); row.pack(fill="x", pady=12)
        btn(row, "←  Quay lại", self.show_step1, kind="ghost", width=110).pack(side="left")
        btn(row, "↻  Kiểm tra lại", self.show_check, kind="ghost", width=130).pack(side="left", padx=6)
        if [i for i in self.check_env() if not i[1] and i[3]]:
            btn(row, "⚙  Cài tất cả còn thiếu", self.fix_all).pack(side="right")

    def do_fix(self, payload):
        import webbrowser
        if payload == "node":
            webbrowser.open("https://nodejs.org/en/download"); messagebox.showinfo("Node.js", "Tải bản LTS, cài xong rồi MỞ LẠI app.")
        else: self.start(payload, "CÀI ĐẶT", on_done=self.show_check)

    def fix_all(self):
        import webbrowser
        cmds = []
        for name, ok, detail, fix in self.check_env():
            if ok or not fix: continue
            if fix[1] == "node": webbrowser.open("https://nodejs.org/en/download")
            else: cmds.append(fix[1])
        self._fix_queue = cmds; self.write("Đang cài các thành phần còn thiếu..."); self._run_next_fix()

    def _run_next_fix(self):
        if not getattr(self, "_fix_queue", None): self.show_check(); return
        self.start(self._fix_queue.pop(0), "CÀI ĐẶT", on_done=self._run_next_fix)

    # ====================== XUẤT & BÁO CÁO (Nhóm A) ======================
    def show_report(self):
        self.clear()
        self.head("Xuất & Báo cáo", "Gộp nội dung khóa thành 1 file, dịch tiếng Việt, và tóm tắt + to-do bằng AI — để đọc hoặc gửi báo cáo.")
        items = self.existing_courses()
        card = self.card()
        if items:
            ctk.CTkLabel(card, text="Chọn khóa", font=(FT, 12, "bold"), text_color=TEXT2).pack(anchor="w", padx=16, pady=(12, 4))
            self.rep_var = ctk.StringVar(value=items[0])
            for it in items:
                ctk.CTkRadioButton(card, text=it, variable=self.rep_var, value=it, font=(FT, 13), text_color=TEXT,
                                   fg_color=PRIMARY, hover_color=PRIMARY_H).pack(anchor="w", padx=18, pady=4)
            ctk.CTkFrame(card, fg_color="transparent", height=6).pack()
        else:
            ctk.CTkLabel(card, text="(Chưa có khóa nào — hãy tải một khóa trước)", font=(FT, 12), text_color=TEXT2).pack(padx=16, pady=16)
            self.rep_var = ctk.StringVar(value="")

        self._render_apikey()

        try:
            import ai_tools; st = ai_tools.status()
        except Exception: st = {"claude": False, "google": False, "model": "", "source": None}
        tline = ("Dịch: " + ("Claude ✓" if st["claude"] else ("Google miễn phí ✓" if st["google"] else "✗ chưa có"))
                 + "    ·    Tóm tắt/To-do: " + ("Claude ✓" if st["claude"] else "✗ cần API key Claude (điền ở trên)"))
        ctk.CTkLabel(self.content, text=tline, font=(FT, 11), text_color=TEXT2, justify="left", wraplength=540).pack(anchor="w", pady=(2, 8))

        act = self.card()
        ctk.CTkLabel(act, text="Việc cần làm", font=(FT, 12, "bold"), text_color=TEXT2).pack(anchor="w", padx=16, pady=(12, 6))
        r1 = ctk.CTkFrame(act, fg_color="transparent"); r1.pack(fill="x", padx=14, pady=(0, 4))
        btn(r1, "📄  Gộp & xuất Word", self.do_export, width=210).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(r1, text="Gộp mô tả + lời giảng → 1 file .md và .docx", font=(FT, 11), text_color=TEXT2).pack(side="left")
        r2 = ctk.CTkFrame(act, fg_color="transparent"); r2.pack(fill="x", padx=14, pady=4)
        btn(r2, "🌐  Dịch tiếng Việt", self.do_translate, kind="secondary", width=210).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(r2, text="Dịch file tổng hợp sang tiếng Việt", font=(FT, 11), text_color=TEXT2).pack(side="left")
        r3 = ctk.CTkFrame(act, fg_color="transparent"); r3.pack(fill="x", padx=14, pady=(4, 12))
        btn(r3, "📝  Tóm tắt + To-do (AI)", self.do_summary, kind="secondary", width=210).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(r3, text="Tóm tắt từng chương + việc áp dụng cho Trường Việt Anh", font=(FT, 11), text_color=TEXT2).pack(side="left")

        row = ctk.CTkFrame(self.content, fg_color="transparent"); row.pack(fill="x", pady=12)
        btn(row, "←  Quay lại", self.show_step1, kind="ghost", width=110).pack(side="left")
        btn(row, "📁  Mở thư mục khóa", self.open_report_folder, kind="secondary", width=190).pack(side="right")

    # ---------- API key Claude (điền sống trong app) ----------
    def _mask_key(self, k):
        if not k: return ""
        return (k[:10] + "…" + k[-4:]) if len(k) > 18 else "••••"

    def _render_apikey(self):
        import ai_tools
        card = self.card()
        ctk.CTkLabel(card, text="Khóa API Claude  (cho Dịch chất lượng cao & Tóm tắt/To-do)",
                     font=(FT, 12, "bold"), text_color=TEXT2).pack(anchor="w", padx=16, pady=(12, 4))
        if ai_tools.api_key_source() == "env":
            ctk.CTkLabel(card, text="✓ Đang dùng API key từ biến môi trường ANTHROPIC_API_KEY.",
                         font=(FT, 12), text_color=SUCCESS).pack(anchor="w", padx=16, pady=(0, 12))
            return
        saved = ai_tools.get_api_key()
        if saved:
            ctk.CTkLabel(card, text=f"✓ Đã lưu trên máy này: {self._mask_key(saved)}",
                         font=(FT, 12), text_color=SUCCESS).pack(anchor="w", padx=16, pady=(0, 6))
        row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=14, pady=(0, 4))
        self.apikey_var = ctk.StringVar(value="")
        ent = ctk.CTkEntry(row, textvariable=self.apikey_var, font=("Consolas", 12), show="•",
                           placeholder_text="Dán API key (sk-ant-…) rồi bấm Lưu")
        ent.pack(side="left", fill="x", expand=True, padx=(0, 8))
        btn(row, "💾  Lưu", self.save_api_key, width=90).pack(side="left")
        if saved:
            btn(row, "Xóa", self.clear_api_key, kind="ghost", width=64).pack(side="left", padx=(6, 0))
        ctk.CTkLabel(card, text="Lấy ở console.anthropic.com → API Keys. Key chỉ lưu trên máy này (file .settings.json), chỉ gửi tới API Claude.",
                     font=(FT, 11), text_color=TEXT2, justify="left", wraplength=540).pack(anchor="w", padx=16, pady=(2, 12))

    def save_api_key(self):
        import ai_tools
        k = self.apikey_var.get().strip()
        if not k:
            messagebox.showinfo("Trống", "Hãy dán API key trước khi lưu."); return
        if not k.startswith("sk-") and not messagebox.askyesno("Khác thường", "Key không bắt đầu bằng “sk-”. Vẫn lưu?"):
            return
        ai_tools.save_setting("anthropic_api_key", k)
        self.write("✓ Đã lưu API key Claude (trên máy này).")
        self.show_report()

    def clear_api_key(self):
        import ai_tools
        if not messagebox.askyesno("Xóa key", "Xóa API key đã lưu trên máy này?"): return
        ai_tools.save_setting("anthropic_api_key", "")
        self.write("Đã xóa API key.")
        self.show_report()

    def _report_args(self):
        v = self.rep_var.get().strip() if hasattr(self, "rep_var") else ""
        if not v:
            messagebox.showinfo("Chưa chọn", "Hãy chọn một khóa."); return None, None
        course = self.item_course(v)
        return course, (["--course", course] if course else [])

    def open_report_folder(self):
        course, _ = self._report_args()
        if course is None and not (hasattr(self, "rep_var") and self.rep_var.get()): return
        r = self.course_root(course); r.mkdir(parents=True, exist_ok=True)
        try: os.startfile(str(r))
        except Exception as e: messagebox.showerror("Lỗi", f"Không mở được thư mục: {e}")

    def do_export(self):
        course, args = self._report_args()
        if args is None: return
        self.start([PY, "export.py"] + args + ["--docx"], "GỘP & XUẤT WORD")

    def do_translate(self):
        course, args = self._report_args()
        if args is None: return
        try:
            import ai_tools
            if not (ai_tools.have_api() or ai_tools.have_google()):
                messagebox.showinfo("Chưa có dịch vụ dịch",
                                    "Cần một trong hai:\n• Dán API key Claude vào ô bên trên rồi Lưu, hoặc\n• Cài bản miễn phí: pip install deep-translator"); return
        except Exception: pass
        self.start([PY, "ai_tools.py"] + args + ["--translate"], "DỊCH TIẾNG VIỆT")

    def do_summary(self):
        course, args = self._report_args()
        if args is None: return
        try:
            import ai_tools
            if not ai_tools.have_api():
                messagebox.showinfo("Cần API key Claude",
                                    "Tóm tắt + To-do cần API key Claude.\nDán API key vào ô bên trên rồi bấm Lưu."); return
        except Exception: pass
        self.start([PY, "ai_tools.py"] + args + ["--summary"], "TÓM TẮT + TO-DO")

    # ====================== BƯỚC 1 ======================
    def show_step1(self):
        self.set_step(1); self.clear(); self.purpose = "import"
        self.head("Bạn muốn tải khóa nào?", "Chọn khóa đã có rồi bấm Tiếp tục để tải tiếp phần còn thiếu, hoặc thêm khóa mới từ Skool.")
        try: miss = self.env_missing()
        except Exception: miss = []
        if miss:
            ban = ctk.CTkFrame(self.content, fg_color="#F4F4F5", corner_radius=12, border_width=1, border_color="#D4D4D8"); ban.pack(fill="x", pady=(0, 8))
            ctk.CTkLabel(ban, text="⚠  Thiếu: " + ", ".join(m[0].split(" (")[0] for m in miss), text_color=TEXT, font=(FT, 12, "bold")).pack(side="left", padx=14, pady=10)
            btn(ban, "Kiểm tra & cài", self.show_check, kind="warn", width=140).pack(side="right", padx=10, pady=8)
        items = self.existing_courses(); card = self.card(); self.prog_labels = {}
        if items:
            ctk.CTkLabel(card, text="Khóa đã có", font=(FT, 12, "bold"), text_color=TEXT2).pack(anchor="w", padx=16, pady=(12, 4))
            self.pick_var = ctk.StringVar(value=items[0])
            for it in items:
                rowf = ctk.CTkFrame(card, fg_color="transparent"); rowf.pack(fill="x", padx=18, pady=4)
                ctk.CTkRadioButton(rowf, text=it, variable=self.pick_var, value=it, font=(FT, 13), text_color=TEXT,
                                   fg_color=PRIMARY, hover_color=PRIMARY_H).pack(side="left")
                lbl = ctk.CTkLabel(rowf, text="đang tính…", font=("Consolas", 11), text_color=TEXT2); lbl.pack(side="right")
                self.prog_labels[it] = lbl
            ctk.CTkFrame(card, fg_color="transparent", height=8).pack()
            self._scan_all_async(items)
        else:
            ctk.CTkLabel(card, text="(Chưa có khóa nào — hãy thêm khóa mới)", font=(FT, 12), text_color=TEXT2).pack(padx=16, pady=16)
            self.pick_var = ctk.StringVar(value="")
        row = ctk.CTkFrame(self.content, fg_color="transparent"); row.pack(fill="x", pady=14)
        btn(row, "➕  Thêm khóa mới", self.go_import, width=180).pack(side="left")
        if items:
            btn(row, "🗑  Xóa khóa", self.delete_course, kind="danger", width=110).pack(side="left", padx=(8, 0))
            btn(row, "Tiếp tục  →", self.use_existing, kind="success", width=130).pack(side="right", padx=(8, 0))
            btn(row, "🔄  Cập nhật", self.check_updates, kind="secondary", width=140).pack(side="right")

    def _fmt_prog(self, s):
        if isinstance(s, Exception) or not s or not s.get("has_data"): return "chưa có dữ liệu"
        done, tot = s["done"], s["total"]
        if tot and done >= tot: return f"✓ đủ {tot} bài · {fmt_size(s['size'])}"
        nat = len(s.get("native_expired") or [])
        tag = f" · {nat} native hết hạn" if nat else ""
        return f"{done}/{tot} bài · còn {tot - done} · {fmt_size(s['size'])}{tag}"

    def _scan_all_async(self, items):
        for it in items:
            def cb(s, it=it):
                if not isinstance(s, Exception): self.scan_cache[it] = s
                lbl = self.prog_labels.get(it)
                if lbl is not None and lbl.winfo_exists(): lbl.configure(text=self._fmt_prog(s))
            self.run_async(lambda it=it: P.scan(self.item_root(it)), cb)

    def use_existing(self):
        v = self.pick_var.get().strip()
        if not v: return
        self.mode = "existing"; self.course_name = self.item_course(v); self.show_manager()

    def go_import(self): self.mode = "new"; self.purpose = "import"; self.show_step2()

    # ---------- B3: kiem tra cap nhat khoa ----------
    def _saved_titles(self, root):
        """Ten chuong da luu (tu _chapters.json) -> de danh dau chuong MOI khi cap nhat."""
        import json
        titles = set(); cj = Path(root) / "_chapters.json"
        try:
            if cj.exists():
                for t in json.loads(cj.read_text(encoding="utf-8-sig")):
                    titles.add(K.san(t if isinstance(t, str) else t.get("title", "")))
        except Exception: pass
        return titles

    def check_updates(self):
        v = self.pick_var.get().strip()
        if not v: return
        self.mode = "existing"; self.course_name = self.item_course(v); self.purpose = "update"
        self.known_titles = self._saved_titles(self.item_root(v))
        self.show_step2()

    # ---------- xoa khoa ----------
    def _trash_available(self):
        import importlib.util
        return importlib.util.find_spec("send2trash") is not None

    def delete_course(self):
        if self.proc:
            messagebox.showinfo("Đang bận", "Đang có tác vụ chạy — hãy dừng trước khi xóa."); return
        v = self.pick_var.get().strip()
        if not v:
            messagebox.showinfo("Chưa chọn", "Hãy chọn một khóa để xóa."); return
        root = self.item_root(v)
        if not root.exists():
            messagebox.showinfo("Không có", "Khóa này không còn thư mục trên máy."); self.show_step1(); return
        s = self.scan_cache.get(v)
        info = f"~{s['total']} bài · {fmt_size(s['size'])}" if s else "(chưa tính dung lượng)"
        trash = self._trash_available()
        where = "chuyển vào Thùng rác (khôi phục được)" if trash else "XÓA VĨNH VIỄN — KHÔNG hoàn tác được"
        if not messagebox.askyesno(
                "Xóa khóa",
                f"Xóa khóa:\n   {v}\n   {root}\n\n{info}\n\nApp sẽ {where}.\nTiếp tục?",
                icon="warning"):
            return
        self.write(f"Đang xóa khóa: {v} …")
        def work():
            try:
                if trash:
                    from send2trash import send2trash as s2t; s2t(str(root))
                else:
                    import shutil; shutil.rmtree(root, ignore_errors=False)
                self.ui_q.put(lambda: self._after_delete(v, True, ""))
            except Exception as e:
                self.ui_q.put(lambda e=e: self._after_delete(v, False, str(e)))
        threading.Thread(target=work, daemon=True).start()

    def _after_delete(self, v, ok, err):
        if ok:
            self.write(f"✓ Đã xóa khóa: {v}")
            self.scan_cache.pop(v, None)
            messagebox.showinfo("Đã xóa", f"Đã xóa khóa: {v}")
        else:
            self.write(f"[LỖI xóa] {err}")
            messagebox.showerror("Lỗi", f"Không xóa được khóa:\n{err}")
        self.show_step1()

    # ====================== BƯỚC 2 ======================
    def show_step2(self):
        self.set_step(2); self.clear()
        cn = self.course_name or "SkoolCourse"
        heads = {
            "import": ("Lấy khóa mới từ Skool",
                       "Làm theo 3 nút. App mở một cửa sổ trình duyệt riêng — bạn đăng nhập và mở đúng khóa, app tự lấy danh sách."),
            "update": (f"Kiểm tra cập nhật: {cn}",
                       "Mở đúng khóa rồi bấm Lấy danh sách. Chương MỚI sẽ được tick sẵn — bấm tải để bổ sung phần mới."),
            "rescue": (f"Cứu bài native hết hạn: {cn}",
                       "Mở đúng khóa rồi bấm Lấy danh sách. App tự lấy lại token các chương cần cứu rồi tải lại."),
        }
        h, sub = heads.get(self.purpose, heads["import"])
        self.head(h, sub)
        f = ctk.CTkFrame(self.content, fg_color="transparent"); f.pack(fill="x")
        self.b_open = btn(f, "1.   Mở Skool & đăng nhập", self.do_open, height=44); self.b_open.pack(fill="x", pady=5)
        lbl2 = "2.   Lấy danh sách & " + ("cứu native" if self.purpose == "rescue" else "chương")
        self.b_list = btn(f, lbl2, self.do_list, kind="secondary", height=44, state="disabled"); self.b_list.pack(fill="x", pady=5)
        self.chap_box = ctk.CTkFrame(self.content, fg_color=CARD, corner_radius=14)   # cuon theo trang ngoai
        self.dump_row = ctk.CTkFrame(self.content, fg_color="transparent")
        btn(self.content, "←  Quay lại", self.show_step1, kind="ghost", width=110).pack(anchor="w", pady=8)

    def do_open(self):
        if self.sb is None:
            self.write("Đang mở trình duyệt (lần đầu hơi lâu)...")
            try:
                from skool_browser import SkoolBrowser; self.sb = SkoolBrowser()
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không mở được trình duyệt: {e}")
        else: self.sb.open()

    def do_list(self):
        if self.sb: self.write("Đang đọc danh sách chương..."); self.sb.list_chapters()

    def render_chapters(self, group, chapters):
        for w in self.chap_box.winfo_children(): w.destroy()
        for w in self.dump_row.winfo_children(): w.destroy()
        self.chap_box.pack(fill="x", pady=8); self.dump_row.pack(fill="x", pady=4)
        upd = (self.purpose == "update")
        n_new = sum(1 for c in chapters if K.san(c["title"]) not in self.known_titles) if upd else len(chapters)
        cap = (f"Khóa: {group} — {n_new} chương MỚI (đã tick sẵn)" if upd
               else f"Khóa: {group} — chọn chương cần tải")
        ctk.CTkLabel(self.chap_box, text=cap, font=(FT, 12, "bold"), text_color=PRIMARY).pack(anchor="w", padx=6, pady=(4, 6))
        self.chapters = []
        for c in chapters:
            is_new = (not upd) or (K.san(c["title"]) not in self.known_titles)
            var = ctk.BooleanVar(value=is_new)
            label = c["title"] + ("   • MỚI" if (upd and is_new) else "")
            tc = PRIMARY if (upd and is_new) else TEXT
            ctk.CTkCheckBox(self.chap_box, text=label, variable=var, font=(FT, 13), text_color=tc, fg_color=PRIMARY, hover_color=PRIMARY_H).pack(anchor="w", padx=8, pady=3)
            self.chapters.append({"id": c["id"], "title": c["title"], "var": var})
        nm = ctk.CTkFrame(self.dump_row, fg_color="transparent"); nm.pack(fill="x", pady=(2, 0))
        ctk.CTkLabel(nm, text="Đặt tên khóa:", font=(FT, 13), text_color=TEXT).pack(side="left")
        self.name_var = ctk.StringVar(value=(self.course_name or group) if upd else group)
        ctk.CTkEntry(nm, textvariable=self.name_var, font=(FT, 13), width=260).pack(side="left", padx=10)
        dump_label = ("3.   Tải bổ sung các chương đã chọn  →" if upd else "3.   Tải dữ liệu các chương đã chọn  →")
        self.b_dump = btn(self.dump_row, dump_label, self.do_dump, height=44); self.b_dump.pack(fill="x", pady=8)
        self.dump_status = ctk.CTkLabel(self.dump_row, text="", font=(FT, 12, "bold"), text_color=PRIMARY); self.dump_status.pack(anchor="w")
        self.dump_pb = ctk.CTkProgressBar(self.dump_row, height=12, corner_radius=6, progress_color=PRIMARY); self.dump_pb.set(0)

    def do_dump(self):
        if self._dumping: return
        sel = [c for c in self.chapters if c["var"].get()]
        if not sel: messagebox.showinfo("Chưa chọn", "Hãy tick ít nhất 1 chương."); return
        name = self.name_var.get().strip()
        if not name: messagebox.showinfo("Thiếu tên", "Hãy đặt tên khóa."); return
        if self.purpose == "update":
            out = self.course_root(self.course_name)        # cap nhat -> ghi vao dung khoa cu
        else:
            self.course_name = name; out = C.BASE / "courses" / name
        self._dumping = True
        self.b_dump.configure(state="disabled", text="⏳   Đang lấy dữ liệu...")
        self.dump_status.configure(text=f"Đang lấy dữ liệu: 0/{len(sel)} chương"); self.dump_pb.pack(fill="x", pady=(2, 6)); self.dump_pb.set(0)
        self.write(f"Đang lấy dữ liệu {len(sel)} chương vào: {out}")
        self.sb.dump([{"id": c["id"], "title": c["title"]} for c in sel], out, all_titles=self.live_titles or None)

    # ====================== BƯỚC 3 ======================
    def show_step3(self):
        self.set_step(3); self.clear(); self.purpose = "import"
        nm = self.course_name or "SkoolCourse (khóa hiện tại)"
        self.head(f"Tải khóa: {nm}", "App chỉ tải phần còn thiếu (bài đã có sẽ bỏ qua). Có thể bật phụ đề tiếng Anh chạy ngầm sau khi tải.")
        sumcard = self.card()
        self.sum_lbl = ctk.CTkLabel(sumcard, text="⏳  Đang kiểm tra tiến độ…", font=(FT, 13), text_color=TEXT2, justify="left", wraplength=520)
        self.sum_lbl.pack(anchor="w", padx=16, pady=12)
        self.native_banner = ctk.CTkFrame(self.content, fg_color="transparent"); self.native_banner.pack(fill="x")
        card = self.card()
        self.opt_sub = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(card, text="Tạo phụ đề tiếng Anh (chạy ngầm sau khi tải xong)", variable=self.opt_sub, font=(FT, 13), text_color=TEXT, fg_color=PRIMARY, hover_color=PRIMARY_H).pack(anchor="w", padx=16, pady=(12, 4))
        self.opt_clean = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(card, text="🔁 Tự thử lại đến khi tải đủ (chờ nếu bị Skool/YouTube giới hạn)", variable=self.opt_clean, font=(FT, 13), text_color=TEXT, fg_color=PRIMARY, hover_color=PRIMARY_H).pack(anchor="w", padx=16, pady=(0, 12))
        self.opt_test = ctk.BooleanVar(value=self.admin)
        if self.admin:
            ctk.CTkCheckBox(card, text="🔧 Chế độ TEST — chỉ kiểm tra, KHÔNG tải thật (dry-run)", variable=self.opt_test, font=(FT, 13, "bold"), text_color="#9A6700", fg_color=WARNING, hover_color="#B98700").pack(anchor="w", padx=16, pady=(0, 12))
        row = ctk.CTkFrame(self.content, fg_color="transparent"); row.pack(fill="x", pady=16)
        btn(row, "←  Quay lại", self.show_step1, kind="ghost", width=110).pack(side="left")
        self.b_start = btn(row, "▶   Bắt đầu tải", self.start_download, kind="success", width=210, height=46); self.b_start.pack(side="right")
        self._scan_current_async()

    def _scan_current_async(self):
        def cb(s):
            self.last_scan = None if isinstance(s, Exception) else s
            if hasattr(self, "sum_lbl") and self.sum_lbl.winfo_exists(): self.sum_lbl.configure(text=self._summary_text(s))
            self._update_start_btn(s); self._maybe_native_banner(s)
        self.run_async(lambda: P.scan(self.course_root(self.course_name)), cb)

    def _summary_text(self, s):
        if isinstance(s, Exception) or not s or not s.get("has_data"):
            return "Khóa chưa có dữ liệu chương. Dùng “Thêm khóa mới” hoặc “Kiểm tra cập nhật” để lấy danh sách trước."
        done, tot, left = s["done"], s["total"], s["total"] - s["done"]
        base = f"Đã tải {done}/{tot} bài  ·  {fmt_size(s['size'])}.  "
        if tot and done >= tot: return base + "✓ Đã tải đủ — bấm để kiểm tra/tải bổ sung."
        nat = len(s.get("native_expired") or [])
        tail = f"  ·  {nat} bài native hết hạn token (cần cứu)." if nat else ""
        return base + f"Còn {left} bài chưa tải." + tail

    def _update_start_btn(self, s):
        if not (hasattr(self, "b_start") and self.b_start.winfo_exists()): return
        if isinstance(s, Exception) or not s or not s.get("has_data"):
            self.b_start.configure(text="▶   Bắt đầu tải"); return
        done, tot, left = s["done"], s["total"], s["total"] - s["done"]
        if tot and done >= tot: self.b_start.configure(text="↻   Kiểm tra / tải bổ sung")
        elif done > 0:          self.b_start.configure(text=f"▶   Tải tiếp (còn {left} bài)")
        else:                   self.b_start.configure(text="▶   Bắt đầu tải")

    def _maybe_native_banner(self, s):
        if not (hasattr(self, "native_banner") and self.native_banner.winfo_exists()): return
        for w in self.native_banner.winfo_children(): w.destroy()
        if isinstance(s, Exception) or not s: return
        n = len(s.get("native_expired") or [])
        if not n: return
        ban = ctk.CTkFrame(self.native_banner, fg_color="#FFF7ED", corner_radius=12, border_width=1, border_color="#FDBA74")
        ban.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(ban, text=f"🔑  {n} bài native hết hạn token — cần lấy lại token mới rồi tải.",
                     text_color="#9A3412", font=(FT, 12, "bold")).pack(side="left", padx=14, pady=10)
        btn(ban, "Cứu bài native", self.rescue_native, kind="warn", width=140).pack(side="right", padx=10, pady=8)

    # ====================== BƯỚC 4 ======================
    def show_step4(self):
        self.set_step(4); self.clear()
        self.head("Đang tải khóa…", "Theo dõi tiến trình ngay bên dưới. Có thể bấm Dừng bất cứ lúc nào (chạy lại sẽ tiếp tục), hoặc mở thư mục xem ngay.")
        self.build_progress()
        ov = self.card()
        ctk.CTkLabel(ov, text=f"Khóa: {self.course_name or 'SkoolCourse'}", font=(FT, 13, "bold"), text_color=PRIMARY).pack(anchor="w", padx=18, pady=(12, 2))
        b = ctk.CTkFrame(ov, fg_color="transparent"); b.pack(fill="x", padx=18, pady=(2, 14))
        self.pct_lbl = ctk.CTkLabel(b, text="0%", font=(FT, 38, "bold"), text_color=TEXT); self.pct_lbl.pack(side="left")
        r = ctk.CTkFrame(b, fg_color="transparent"); r.pack(side="left", fill="x", expand=True, padx=18)
        self.pb4 = ctk.CTkProgressBar(r, height=16, corner_radius=8, progress_color=PRIMARY); self.pb4.pack(fill="x", pady=(16, 6)); self.pb4.set(0)
        self.status4 = ctk.CTkLabel(r, text="", font=("Consolas", 12), text_color=TEXT2); self.status4.pack(anchor="w")
        self.chap_hdr = ctk.CTkLabel(self.content, text="Chương", font=(FT, 14, "bold"), text_color=TEXT); self.chap_hdr.pack(anchor="w", pady=(8, 2))
        self.chap_scroll = ctk.CTkFrame(self.content, fg_color=CARD, corner_radius=14); self.chap_scroll.pack(fill="x", pady=(0, 6))   # cuon theo trang ngoai
        self.run_lbl = ctk.CTkLabel(self.content, text="⏳  Đang chạy…", font=(FT, 13, "bold"), text_color=WARNING); self.run_lbl.pack(anchor="w", pady=(8, 4))
        self.done_row = ctk.CTkFrame(self.content, fg_color="transparent"); self.done_row.pack(fill="x", pady=6)
        btn(self.done_row, "📁  Mở thư mục dự án", self.open_folder, kind="secondary", width=210).pack(side="left", padx=(0, 8))
        self.btn_stop = btn(self.done_row, "■  Dừng", self.do_stop, kind="danger", width=120); self.btn_stop.pack(side="left")
        self.build_chapter_rows(); self.refresh4()

    def build_chapter_rows(self):
        self.chap_widgets = {}; self._last4 = {}
        for w in self.chap_scroll.winfo_children(): w.destroy()
        if not self._prog:
            ctk.CTkLabel(self.chap_scroll, text="(Chưa có dữ liệu chương — bắt đầu tải để thấy tiến trình)", font=(FT, 12), text_color=TEXT2).pack(anchor="w", padx=10, pady=12); return
        for ch in self._prog:
            row = ctk.CTkFrame(self.chap_scroll, fg_color="transparent"); row.pack(fill="x", padx=4, pady=3)
            ic = ctk.CTkLabel(row, text="•", text_color=TEXT2, font=(FT, 15, "bold"), width=24); ic.pack(side="left")
            nm = ch["name"]; nm = nm if len(nm) <= 38 else nm[:37] + "…"
            ctk.CTkLabel(row, text=nm, font=(FT, 13), text_color=TEXT, width=270, anchor="w").pack(side="left")
            pb = ctk.CTkProgressBar(row, width=120, height=8, corner_radius=4, progress_color=PRIMARY); pb.pack(side="left", padx=8); pb.set(0)
            cnt = ctk.CTkLabel(row, text="0/0", font=("Consolas", 12), text_color=TEXT2, width=64, anchor="e"); cnt.pack(side="left", padx=6)
            pct = ctk.CTkLabel(row, text="0%", font=("Consolas", 12, "bold"), text_color=PRIMARY, width=48, anchor="e"); pct.pack(side="left")
            self.chap_widgets[ch["name"]] = {"ic": ic, "pb": pb, "cnt": cnt, "pct": pct}

    def refresh4(self):
        """Quet tien do o LUONG PHU (stat hang tram file) -> khong lam dung/giat giao dien."""
        if not hasattr(self, "pct_lbl"): return
        if getattr(self, "_refreshing", False): return
        self._refreshing = True
        def work():
            try: data = self.scan_progress()
            except Exception: data = None
            self.ui_q.put(lambda: self._apply_refresh4(data))
        threading.Thread(target=work, daemon=True).start()

    def _apply_refresh4(self, data):
        self._refreshing = False
        if data is None: return
        if not (hasattr(self, "pct_lbl") and self.pct_lbl.winfo_exists()): return
        rows, dtot, etot, size = data
        pct = round(dtot * 100 / etot) if etot else 0
        last = getattr(self, "_last4", {})
        def setc(key, fn, val):           # chi cap nhat khi GIA TRI doi -> bot ve lai (giat)
            if last.get(key) != val: fn(val); last[key] = val
        setc("pct", lambda v: self.pct_lbl.configure(text=v), f"{pct}%")
        setc("pb4", lambda v: self.pb4.set(v), pct / 100)
        setc("st", lambda v: self.status4.configure(text=v), f"{dtot}/{etot} video   ·   {fmt_size(size)}")
        setc("hdr", lambda v: self.chap_hdr.configure(text=v), f"Chương ({len(rows)})")
        for r in rows:
            w = self.chap_widgets.get(r["name"])
            if not w: continue
            ic, col = ICON.get(r["status"], ("•", TEXT2))
            p = round(r["done"] * 100 / r["exp"]) if r["exp"] else 0
            nm = r["name"]
            setc(("ic", nm), lambda v, w=w: w["ic"].configure(text=v[0], text_color=v[1]), (ic, col))
            setc(("pb", nm), lambda v, w=w: w["pb"].set(v), p / 100)
            setc(("cnt", nm), lambda v, w=w: w["cnt"].configure(text=v), f"{r['done']}/{r['exp']}")
            setc(("pct", nm), lambda v, w=w: w["pct"].configure(text=v), f"{p}%")
        self._last4 = last

    def show_done(self):
        for w in self.done_row.winfo_children(): w.destroy()
        self.refresh4()
        if hasattr(self, "run_lbl"): self.run_lbl.configure(text="✓  Hoàn tất", text_color=SUCCESS)
        if getattr(self, "opt_sub", None) and self.opt_sub.get(): self.write("Bật phụ đề chạy ngầm..."); self.run_sub_on()
        btn(self.done_row, "📁  Mở thư mục dự án", self.open_folder, kind="secondary", width=200).pack(side="left", padx=(0, 8))
        btn(self.done_row, "📄  Xuất & Báo cáo", self.show_report, kind="secondary", width=180).pack(side="left", padx=(0, 8))
        btn(self.done_row, "↻  Làm khóa khác", self.show_step1, width=150).pack(side="left")

    # ====================== TRÌNH TẢI (theo chương / bài) ======================
    def show_manager(self):
        self.set_step(4); self.clear(); self.purpose = "import"
        if not hasattr(self, "mgr_expanded"): self.mgr_expanded = set()
        self.mgr_tree = []; self.mgr_widgets = {}; self.mgr_busy = None
        nm = self.course_name or "SkoolCourse (khóa hiện tại)"
        self.head(f"Tải khóa: {nm}", "Bấm ▸ để mở các bài trong chương. Tải cả chương, tải từng bài, hoặc Tải toàn bộ. Bài đã tải sẽ bỏ qua; có thể Dừng bất cứ lúc nào.")
        bar = self.card()
        row = ctk.CTkFrame(bar, fg_color="transparent"); row.pack(fill="x", padx=14, pady=(12, 4))
        self.b_all = btn(row, "⬇  Tải toàn bộ", self.dl_all, kind="success", width=150); self.b_all.pack(side="left")
        btn(row, "■  Dừng", self.do_stop, kind="danger", width=100).pack(side="left", padx=8)
        self.opt_clean = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(row, text="🔁 Tự thử lại đến khi đủ", variable=self.opt_clean, font=(FT, 12), text_color=TEXT2, fg_color=PRIMARY, hover_color=PRIMARY_H).pack(side="left", padx=8)
        self.mgr_status = ctk.CTkLabel(bar, text="⏳  Đang đọc danh sách chương…", font=(FT, 12), text_color=TEXT2, justify="left", wraplength=520); self.mgr_status.pack(anchor="w", padx=16, pady=(2, 10))
        self.mgr_scroll = ctk.CTkFrame(self.content, fg_color=CARD, corner_radius=14, border_width=1, border_color=BORDER); self.mgr_scroll.pack(fill="x", pady=(2, 6))
        nav = ctk.CTkFrame(self.content, fg_color="transparent"); nav.pack(fill="x", pady=10)
        btn(nav, "←  Quay lại", self.show_step1, kind="ghost", width=110).pack(side="left")
        btn(nav, "Tạo phụ đề  →", self.show_transcribe, kind="secondary", width=160).pack(side="right")
        self._mgr_scan_async()

    def _mgr_scan_async(self):
        def cb(t):
            self.mgr_tree = [] if isinstance(t, Exception) else (t or [])
            self._mgr_render()
        def load():
            self._ensure_folders(self.course_name)   # tao folder chuong/bai truoc -> rel day du, on dinh
            return P.tree(self.course_root(self.course_name))
        self.run_async(load, cb)

    def _ensure_folders(self, course_name):
        """Tao cay folder chuong/bai cho khoa (idempotent) truoc khi liet ke, de duong dan bai (rel)
           luon day du & khop voi videos.py -> tai dung tu lan bam dau. Co lap config.C + chan print
           (pythonw khong co stdout)."""
        import io, sys as _sys
        import config as C2, folders
        with self._cfg_lock:
            saved = (C2.COURSE, C2.ROOT, C2.DUMP_ROOT)
            out = (_sys.stdout, _sys.stderr)
            try:
                if course_name:
                    C2.set_course(course_name)
                else:
                    C2.COURSE = None; C2.ROOT = C2.BASE / "SkoolCourse"; C2.DUMP_ROOT = C2.ROOT
                    C2.ROOT.mkdir(parents=True, exist_ok=True)
                _sys.stdout = _sys.stderr = io.StringIO()
                folders.run()
            except Exception:
                pass
            finally:
                _sys.stdout, _sys.stderr = out
                C2.COURSE, C2.ROOT, C2.DUMP_ROOT = saved

    def _mgr_render(self):
        if not (hasattr(self, "mgr_scroll") and self.mgr_scroll.winfo_exists()): return
        for w in self.mgr_scroll.winfo_children(): w.destroy()
        self.mgr_widgets = {}
        if not self.mgr_tree:
            ctk.CTkLabel(self.mgr_scroll, text="(Chưa có dữ liệu chương — dùng “Thêm khóa mới” hoặc “Kiểm tra cập nhật” để lấy danh sách trước.)",
                         font=(FT, 12), text_color=TEXT2, wraplength=520, justify="left").pack(anchor="w", padx=12, pady=12)
            self._mgr_update_status(); return
        for ch in self.mgr_tree:
            self._mgr_render_chapter(ch)
        self._mgr_update_status()

    def _mgr_render_chapter(self, ch):
        name = ch["name"]; exp = name in self.mgr_expanded
        crow = ctk.CTkFrame(self.mgr_scroll, fg_color=CARD2 if exp else "transparent", corner_radius=8); crow.pack(fill="x", padx=4, pady=(4, 1))
        btn(crow, ("▾" if exp else "▸"), (lambda n=name: self._mgr_toggle(n)), kind="ghost", width=26).pack(side="left", padx=(2, 0))
        full = ch["total"] and ch["done"] >= ch["total"]
        ic = ctk.CTkLabel(crow, text=("✓" if full else ("⏳" if ch["done"] else "•")), text_color=(SUCCESS if full else (WARNING if ch["done"] else TEXT2)), width=20, font=(FT, 14, "bold")); ic.pack(side="left")
        disp = name if len(name) <= 38 else name[:37] + "…"
        ctk.CTkLabel(crow, text=disp, font=(FT, 13, "bold"), text_color=TEXT, width=290, anchor="w").pack(side="left")
        cnt = ctk.CTkLabel(crow, text=f"{ch['done']}/{ch['total']}", font=("Consolas", 12), text_color=TEXT2, width=54, anchor="e"); cnt.pack(side="left", padx=4)
        btn(crow, "⬇ Chương", (lambda t=ch["title"], n=name: self.dl_chapter(t, n)), kind="secondary", width=92, height=30).pack(side="right", padx=4, pady=3)
        self.mgr_widgets[("chap", name)] = {"ic": ic, "cnt": cnt}
        if exp:
            for L in ch["lessons"]:
                self._mgr_render_lesson(L)
            if not ch["lessons"]:
                ctk.CTkLabel(self.mgr_scroll, text="    (chương trống)", font=(FT, 11), text_color=TEXT2).pack(anchor="w", padx=40)

    def _mgr_render_lesson(self, L):
        lrow = ctk.CTkFrame(self.mgr_scroll, fg_color="transparent"); lrow.pack(fill="x", padx=(38, 4), pady=0)
        ic = ctk.CTkLabel(lrow, text=("✓" if L["done"] else "•"), text_color=(SUCCESS if L["done"] else TEXT2), width=18, font=(FT, 13)); ic.pack(side="left")
        t = L["title"] or "(bài)"; t = t if len(t) <= 42 else t[:41] + "…"
        ctk.CTkLabel(lrow, text=t, font=(FT, 12), text_color=TEXT, width=300, anchor="w").pack(side="left")
        host = (L["host"] or "").replace("www.", "")[:16]
        ctk.CTkLabel(lrow, text=host, font=("Consolas", 10), text_color=TEXT2, width=120, anchor="w").pack(side="left")
        btn(lrow, "⬇", (lambda r=L["rel"], tt=(L["title"] or "bài"): self.dl_lesson(r, tt)), kind="ghost", width=32, height=26).pack(side="right", padx=4)
        self.mgr_widgets[("lesson", L["rel"])] = {"ic": ic}

    def _mgr_toggle(self, name):
        self.mgr_expanded.discard(name) if name in self.mgr_expanded else self.mgr_expanded.add(name)
        self._mgr_render()

    def _course_args(self):
        return (["--course", self.course_name] if self.course_name else [])

    def dl_all(self):
        if self.proc: messagebox.showinfo("Đang bận", "Đang tải — bấm Dừng trước đã."); return
        args = self._course_args()
        if getattr(self, "opt_clean", None) and self.opt_clean.get(): args.append("--until-clean")
        self.mgr_busy = "toàn bộ khóa"; self._mgr_busy_status()
        self.start([PY, "main.py"] + args, "TẢI TOÀN BỘ", on_done=self._mgr_after_dl)

    def dl_chapter(self, title, name):
        if self.proc: messagebox.showinfo("Đang bận", "Đang tải — bấm Dừng trước đã."); return
        args = self._course_args() + ["--only", "videos", "--chapter", title]
        if getattr(self, "opt_clean", None) and self.opt_clean.get(): args.append("--until-clean")
        self.mgr_busy = f"chương “{name}”"; self._mgr_busy_status()
        self.start([PY, "main.py"] + args, f"TẢI CHƯƠNG: {name}", on_done=self._mgr_after_dl)

    def dl_lesson(self, rel, title):
        if self.proc: messagebox.showinfo("Đang bận", "Đang tải — bấm Dừng trước đã."); return
        args = self._course_args() + ["--only", "videos", "--lesson", rel]
        self.mgr_busy = f"bài “{title}”"; self._mgr_busy_status()
        self.start([PY, "main.py"] + args, f"TẢI BÀI: {title}", on_done=self._mgr_after_dl)

    def _mgr_busy_status(self):
        if hasattr(self, "mgr_status") and self.mgr_status.winfo_exists():
            self.mgr_status.configure(text=f"⏳  Đang tải {self.mgr_busy}…  (bấm Dừng để ngừng — bài đã tải vẫn giữ)", text_color=WARNING)

    def _mgr_after_dl(self):
        self.mgr_busy = None; self._mgr_scan_async()

    def _mgr_update_status(self):
        if not (hasattr(self, "mgr_status") and self.mgr_status.winfo_exists()): return
        if self.mgr_busy: self._mgr_busy_status(); return
        if not self.mgr_tree:
            self.mgr_status.configure(text="Chưa có dữ liệu chương.", text_color=TEXT2); return
        done = sum(c["done"] for c in self.mgr_tree); tot = sum(c["total"] for c in self.mgr_tree)
        size = sum(L["size"] for c in self.mgr_tree for L in c["lessons"])
        msg = f"Đã tải {done}/{tot} bài  ·  {fmt_size(size)}." + (" ✓ Đủ." if (tot and done >= tot) else f"  Còn {tot - done} bài.")
        self.mgr_status.configure(text=msg, text_color=TEXT2)

    def refresh_manager(self):
        if getattr(self, "_mgr_refreshing", False): return
        self._mgr_refreshing = True
        def work():
            try: t = P.tree(self.course_root(self.course_name))
            except Exception: t = None
            self.ui_q.put(lambda: self._apply_mgr(t))
        threading.Thread(target=work, daemon=True).start()

    def _apply_mgr(self, t):
        self._mgr_refreshing = False
        if t is None or not (hasattr(self, "mgr_scroll") and self.mgr_scroll.winfo_exists()): return
        if len(t) != len(self.mgr_tree):   # cấu trúc đổi -> dựng lại
            self.mgr_tree = t; self._mgr_render(); return
        self.mgr_tree = t
        for ch in t:
            w = self.mgr_widgets.get(("chap", ch["name"]))
            if w and w["cnt"].winfo_exists():
                full = ch["total"] and ch["done"] >= ch["total"]
                w["cnt"].configure(text=f"{ch['done']}/{ch['total']}")
                w["ic"].configure(text=("✓" if full else ("⏳" if ch["done"] else "•")), text_color=(SUCCESS if full else (WARNING if ch["done"] else TEXT2)))
            for L in ch["lessons"]:
                lw = self.mgr_widgets.get(("lesson", L["rel"]))
                if lw and lw["ic"].winfo_exists():
                    lw["ic"].configure(text=("✓" if L["done"] else "•"), text_color=(SUCCESS if L["done"] else TEXT2))
        self._mgr_update_status()

    # ====================== TẠO PHỤ ĐỀ (transcript) ======================
    def _transcript_stats(self, root):
        root = Path(root); vids = txt = 0
        if not root.exists(): return (0, 0)
        for ext in C.VIDEXT:
            for p in root.rglob("video" + ext):
                if p.stem != "video" or any(x.lower() == "resources" for x in p.parts): continue
                vids += 1
                if (p.parent / "video.txt").exists(): txt += 1
        return (txt, vids)

    def show_transcribe(self):
        self.clear(); self.purpose = "import"
        nm = self.course_name or "SkoolCourse"
        self.head(f"Tạo phụ đề: {nm}", "Bóc lời giảng video thành văn bản tiếng Anh (.txt/.srt). Chạy ngầm bằng Windows — sống qua cả khi tắt/mở máy; bài đã có phụ đề sẽ bỏ qua.")
        card = self.card()
        self.trans_lbl = ctk.CTkLabel(card, text="⏳  Đang kiểm tra…", font=(FT, 13), text_color=TEXT2); self.trans_lbl.pack(anchor="w", padx=16, pady=(12, 6))
        self.trans_pb = ctk.CTkProgressBar(card, height=12, corner_radius=6, progress_color=PRIMARY); self.trans_pb.set(0); self.trans_pb.pack(fill="x", padx=16, pady=(0, 12))
        act = self.card()
        r = ctk.CTkFrame(act, fg_color="transparent"); r.pack(fill="x", padx=14, pady=12)
        btn(r, "▶  Bắt đầu tạo phụ đề (chạy ngầm)", self.start_transcribe, width=280).pack(side="left")
        ctk.CTkLabel(r, text="Chạy ngầm độc lập — có thể đóng app.", font=(FT, 11), text_color=TEXT2).pack(side="left", padx=10)
        nav = ctk.CTkFrame(self.content, fg_color="transparent"); nav.pack(fill="x", pady=10)
        btn(nav, "←  Về trình tải", self.show_manager, kind="ghost", width=150).pack(side="left")
        btn(nav, "Dịch tiếng Việt  →", self.show_translate, kind="secondary", width=180).pack(side="right")
        self._trans_scan_async()

    def _trans_scan_async(self):
        def cb(rr):
            txt, vids = (0, 0) if isinstance(rr, Exception) else rr
            if hasattr(self, "trans_lbl") and self.trans_lbl.winfo_exists():
                pct = round(txt * 100 / vids) if vids else 0
                self.trans_lbl.configure(text=f"Đã có phụ đề: {txt}/{vids} video ({pct}%)" + (" — ✓ xong" if (vids and txt >= vids) else ""))
                if self.trans_pb.winfo_exists(): self.trans_pb.set((txt / vids) if vids else 0)
        self.run_async(lambda: self._transcript_stats(self.course_root(self.course_name)), cb)

    def start_transcribe(self):
        self.run_sub_on()
        self.write("Đã bật tạo phụ đề chạy ngầm (Windows Task) cho khóa.")
        if hasattr(self, "trans_lbl") and self.trans_lbl.winfo_exists():
            self.trans_lbl.configure(text="▶  Đã bật chạy ngầm — phụ đề sẽ xuất hiện dần. Quay lại trang này để xem tiến độ.")

    # ====================== DỊCH TIẾNG VIỆT ======================
    def show_translate(self):
        self.clear(); self.purpose = "import"
        nm = self.course_name or "SkoolCourse"
        self.head(f"Dịch sang tiếng Việt: {nm}", "Sau khi đã có phụ đề, tạo bản tiếng Việt + phụ đề song ngữ Anh–Việt cho khóa.")
        try:
            import ai_tools; google = ai_tools.have_google()
        except Exception: google = False
        card = self.card()
        ctk.CTkLabel(card, text=("Dịch vụ: Google (miễn phí) ✓" if google else "✗ Chưa có deep-translator — chạy: pip install deep-translator"),
                     font=(FT, 13), text_color=(TEXT2 if google else DANGER)).pack(anchor="w", padx=16, pady=12)
        self.tl_lbl = ctk.CTkLabel(card, text="", font=(FT, 12), text_color=TEXT2, justify="left", wraplength=520); self.tl_lbl.pack(anchor="w", padx=16, pady=(0, 12))
        act = self.card()
        r = ctk.CTkFrame(act, fg_color="transparent"); r.pack(fill="x", padx=14, pady=12)
        btn(r, "▶  Dịch sang tiếng Việt", self.start_translate, width=220).pack(side="left")
        ctk.CTkLabel(r, text="Tạo Transcript_VI.md + PhuDe_SongNgu.srt trong thư mục khóa.", font=(FT, 11), text_color=TEXT2).pack(side="left", padx=10)
        nav = ctk.CTkFrame(self.content, fg_color="transparent"); nav.pack(fill="x", pady=10)
        btn(nav, "←  Về Phụ đề", self.show_transcribe, kind="ghost", width=140).pack(side="left")
        btn(nav, "📁  Mở thư mục", self.open_folder, kind="secondary", width=150).pack(side="right")

    def start_translate(self):
        if self.proc: messagebox.showinfo("Đang bận", "Một tác vụ đang chạy."); return
        try:
            import ai_tools
            if not ai_tools.have_google():
                messagebox.showinfo("Thiếu công cụ dịch", "Cần deep-translator để dịch.\nChạy: pip install deep-translator"); return
        except Exception: pass
        root = self.course_root(self.course_name)
        if hasattr(self, "tl_lbl"): self.tl_lbl.configure(text="⏳  Đang dịch… (theo dõi ở Nhật ký bên dưới)")
        self.start([PY, "report_bundle.py", "--root", str(root), "--out", str(root)], "DỊCH TIẾNG VIỆT", on_done=self._after_translate)

    def _after_translate(self):
        if hasattr(self, "tl_lbl") and self.tl_lbl.winfo_exists():
            self.tl_lbl.configure(text="✓  Xong — xem Transcript_VI.md + PhuDe_SongNgu.srt trong thư mục khóa.")

    # ---------- tien trinh ----------
    def start_download(self):
        args = ([] if not self.course_name else ["--course", self.course_name])
        test = bool(getattr(self, "opt_test", None) and self.opt_test.get())
        if test: args.append("--dry-run")
        if not test and getattr(self, "opt_clean", None) and self.opt_clean.get(): args.append("--until-clean")
        self.show_step4()
        if test and hasattr(self, "run_lbl"): self.run_lbl.configure(text="🔧  CHẾ ĐỘ TEST — chỉ kiểm tra, không tải thật", text_color="#9A6700")
        self.start([PY, "main.py"] + args, "TẢI KHÓA" + (" (TEST)" if test else ""), on_done=self.show_done)

    # ---------- B4: cuu bai native het han token ----------
    def rescue_native(self):
        s = self.last_scan
        if not s or not s.get("native_expired"):
            messagebox.showinfo("Không cần", "Không có bài native nào hết hạn token."); return
        self.target_titles = set(P.expired_native_chapter_titles(s))
        self.purpose = "rescue"; self.show_step2()

    def _rescue_dump(self, group, chapters):
        sel = [c for c in chapters if K.san(c["title"]) in self.target_titles]
        if not sel:
            messagebox.showinfo("Không khớp", "Không tìm thấy chương cần cứu trên Skool (có thể đã đổi tên).")
            self.show_manager(); return
        self.chap_box.pack(fill="x", pady=8); self.dump_row.pack(fill="x", pady=4)
        for w in self.dump_row.winfo_children(): w.destroy()
        self.dump_status = ctk.CTkLabel(self.dump_row, text=f"Đang lấy lại token {len(sel)} chương…", font=(FT, 12, "bold"), text_color=PRIMARY); self.dump_status.pack(anchor="w")
        self.dump_pb = ctk.CTkProgressBar(self.dump_row, height=12, corner_radius=6, progress_color=PRIMARY); self.dump_pb.set(0); self.dump_pb.pack(fill="x", pady=(2, 6))
        out = self.course_root(self.course_name); self._dumping = True
        self.write(f"Cứu native: lấy lại token {len(sel)} chương → {out}")
        self.sb.dump([{"id": c["id"], "title": c["title"]} for c in sel], out, all_titles=self.live_titles or None)

    def start_native_download(self):
        self.purpose = "import"
        args = (["--course", self.course_name] if self.course_name else []) + ["--only", "videos", "--native-only"]
        self.show_step4()
        if hasattr(self, "run_lbl"): self.run_lbl.configure(text="🔑  Đang tải lại video native (token mới)…", text_color=WARNING)
        self.start([PY, "main.py"] + args, "CỨU NATIVE", on_done=self.show_done)

    def run_sub_on(self):
        c = self.course_name; ps = HERE / "install_transcribe_task.ps1"; extra = ["-Course", c] if c else ["-All"]
        subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps)] + extra, creationflags=NO_WIN)

    def start(self, cmd, title, cwd=None, on_done=None):
        if self.proc: messagebox.showinfo("Đang bận", "Một tác vụ đang chạy."); return
        self._on_done = on_done; self.write(f"\n===== {title} =====")
        env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
        try:
            self.proc = subprocess.Popen(cmd, cwd=cwd or HERE, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1, creationflags=NO_WIN)
        except Exception as e:
            self.write(f"[LỖI] {e}"); self.proc = None; return
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        for line in self.proc.stdout: self.q.put(("out", line))
        self.proc.wait(); self.q.put(("out", SENTINEL))

    def do_stop(self):
        if self.proc:
            try: self.proc.terminate()
            except Exception: pass
            self.write("[Đã dừng]")
            if hasattr(self, "run_lbl") and self.run_lbl.winfo_exists(): self.run_lbl.configure(text="■  Đã dừng", text_color=DANGER)
            if hasattr(self, "mgr_status") and self.mgr_status.winfo_exists():
                self.mgr_busy = None; self.mgr_status.configure(text="■  Đã dừng. Bài đã tải vẫn được giữ.", text_color=DANGER)

    def open_folder(self):
        r = self.course_root(); r.mkdir(parents=True, exist_ok=True)
        try: os.startfile(str(r))
        except Exception as e: messagebox.showerror("Lỗi", f"Không mở được thư mục: {e}")

    def poll(self):
        # TU CHUA LANH: bao boc toan bo + reschedule trong finally -> 1 loi le KHONG bao gio dung vong lap.
        try:
            try:
                while True: self.ui_q.get_nowait()()
            except queue.Empty: pass
            if self.sb:
                try:
                    while True:
                        ev = self.sb.evt_q.get_nowait()
                        try: self.on_browser_event(ev)
                        except Exception as e: self.write(f"[lỗi sự kiện trình duyệt] {e}")
                except queue.Empty: pass
            lines = []; done_cb = None
            try:
                while True:
                    tag, s = self.q.get_nowait()
                    if s == SENTINEL:
                        rc = self.proc.returncode if self.proc else 0
                        lines.append(f"--- Kết thúc (mã {rc}) ---"); self.proc = None
                        if getattr(self, "_on_done", None): done_cb = self._on_done; self._on_done = None
                    else: lines.append(s.rstrip("\n"))
            except queue.Empty: pass
            if lines: self._flush_log(lines)      # ghi 1 lan/chu ky (gom dong) -> bot giat
            if done_cb:
                try: done_cb()
                except Exception as e: self.write(f"[lỗi sau khi xong tác vụ] {e}")
            if time.time() - self._lastref > 1.5:
                if hasattr(self, "chap_scroll") and self.chap_scroll.winfo_exists():
                    self._lastref = time.time(); self.refresh4()
                elif hasattr(self, "mgr_scroll") and self.mgr_scroll.winfo_exists():
                    self._lastref = time.time(); self.refresh_manager()
                elif self.proc and hasattr(self, "trans_lbl") and self.trans_lbl.winfo_exists():
                    self._lastref = time.time(); self._trans_scan_async()
        except Exception as e:
            try: self.write(f"[lỗi vòng lặp] {e}")
            except Exception: pass
        finally:
            try: self.root.after(200, self.poll)   # luon lap lai; bo qua neu app dang dong
            except Exception: pass

    def on_browser_event(self, e):
        t = e.get("type")
        if t == "ready": self.write("Trình duyệt sẵn sàng."); self.sb.open()
        elif t == "opened":
            self.write("Đã mở Skool. Đăng nhập & mở trang Classroom, rồi bấm nút 2.")
            if hasattr(self, "b_list") and self.b_list.winfo_exists(): self.b_list.configure(state="normal")
        elif t == "log": self.write(e["msg"])
        elif t == "need_classroom": messagebox.showinfo("Mở trang Classroom", e["msg"])
        elif t == "chapters":
            self.live_titles = [c["title"] for c in e["chapters"]]
            self.write(f"Tìm thấy {len(e['chapters'])} chương.")
            if self.purpose == "rescue": self._rescue_dump(e["group"], e["chapters"])
            else: self.render_chapters(e["group"], e["chapters"])
        elif t == "dump_progress":
            self.write(f"[{e['i']}/{e['n']}] {e['title']}")
            if (hasattr(self, "dump_status") and self.dump_status.winfo_exists()
                    and hasattr(self, "dump_pb") and self.dump_pb.winfo_exists()):
                pct = round(e["i"] * 100 / max(1, e["n"]))
                self.dump_status.configure(text=f"Đang lấy: {e['i']}/{e['n']} chương ({pct}%) — {e['title']}"); self.dump_pb.set(pct / 100)
        elif t == "dumped":
            self._dumping = False; self.write(f"Đã lấy xong {e['ok']}/{e['total']} chương → {e['out_dir']}")
            if hasattr(self, "dump_status") and self.dump_status.winfo_exists():
                self.dump_status.configure(text=f"✓ Đã lấy {e['ok']}/{e['total']} chương")
            if hasattr(self, "dump_pb") and self.dump_pb.winfo_exists(): self.dump_pb.set(1)
            if self.purpose == "rescue":
                self.write("Token mới đã sẵn sàng — bắt đầu tải lại native…"); self.start_native_download(); return
            if self.purpose == "update":
                messagebox.showinfo("Xong", f"Đã cập nhật {e['ok']}/{e['total']} chương.\nChọn chương/bài để tải phần mới."); self.show_manager(); return
            messagebox.showinfo("Xong", f"Đã lấy dữ liệu khóa ({e['ok']}/{e['total']} chương).\nChọn chương/bài để tải."); self.show_manager()
        elif t == "error":
            self._dumping = False     # gỡ kẹt: nếu đang dump mà lỗi, mở lại nút
            if hasattr(self, "b_dump") and self.b_dump.winfo_exists():
                self.b_dump.configure(state="normal", text="3.   Tải dữ liệu các chương đã chọn  →")
            self.write(f"[LỖI trình duyệt] {e.get('msg', '')}"); messagebox.showerror("Lỗi", e.get("msg", "Lỗi trình duyệt"))


def main():
    root = ctk.CTk()
    App(root)
    if os.environ.get("GUI_SMOKE_TEST"): root.after(900, root.destroy)
    root.mainloop()


if __name__ == "__main__":
    main()
