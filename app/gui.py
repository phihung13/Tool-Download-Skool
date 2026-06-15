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
        self.proc = None; self.sb = None; self.q = queue.Queue()
        self.chapters = []; self.course_name = None; self.mode = None
        self.admin = False; self._dumping = False; self._prog = []; self._lastref = 0.0
        self.step = 1; self.chap_widgets = {}

        root.title("Skool Archiver"); root.geometry("960x760"); root.minsize(880, 680)
        root.configure(fg_color=BG)
        root.grid_columnconfigure(1, weight=1); root.grid_rowconfigure(0, weight=1)

        # ---------- sidebar ----------
        side = ctk.CTkFrame(root, width=232, corner_radius=0, fg_color=SIDE)
        side.grid(row=0, column=0, sticky="nsw"); side.grid_propagate(False)
        ctk.CTkLabel(side, text="📦  Skool Archiver", font=(FT, 18, "bold"), text_color="white").pack(anchor="w", padx=22, pady=(26, 4))
        ctk.CTkLabel(side, text="Lưu trữ khóa học Skool", font=(FT, 11), text_color=ON_SIDE).pack(anchor="w", padx=22, pady=(0, 22))
        self.step_box = ctk.CTkFrame(side, fg_color="transparent"); self.step_box.pack(fill="x", padx=14)
        self.badge = ctk.CTkLabel(side, text="", font=(FT, 12, "bold"), text_color="white"); self.badge.pack(side="bottom", anchor="w", padx=22, pady=(0, 8))
        btn(side, "⚙  Kiểm tra môi trường", self.show_check, kind="ghost", text_color="white", hover_color=SIDE_HI, anchor="w").pack(side="bottom", fill="x", padx=14, pady=(0, 6))

        # ---------- main ----------
        main = ctk.CTkFrame(root, corner_radius=0, fg_color=BG); main.grid(row=0, column=1, sticky="nsew")
        main.grid_rowconfigure(0, weight=1); main.grid_columnconfigure(0, weight=1)
        self.content = ctk.CTkScrollableFrame(main, fg_color="transparent"); self.content.grid(row=0, column=0, sticky="nsew", padx=24, pady=(20, 6))
        self.content.grid_columnconfigure(0, weight=1)
        logwrap = ctk.CTkFrame(main, fg_color="transparent"); logwrap.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 16))
        ctk.CTkLabel(logwrap, text="Nhật ký", font=(FT, 11, "bold"), text_color=TEXT2).pack(anchor="w")
        self.log = ctk.CTkTextbox(logwrap, height=120, font=("Consolas", 11), fg_color=CARD, text_color=TEXT, corner_radius=10)
        self.log.pack(fill="x"); self.log.configure(state="disabled")

        root.bind_all("<Control-Alt-t>", self.toggle_admin); root.bind_all("<Control-Alt-T>", self.toggle_admin)
        self.render_sidebar(); self.show_step1()
        self.root.after(120, self.poll)

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

    def toggle_admin(self, *_):
        self.admin = not self.admin
        self.badge.configure(text="🔧 TEST MODE" if self.admin else "")
        self.write("== Chế độ TEST: BẬT (tải sẽ KHÔNG tải thật) ==" if self.admin else "== Chế độ TEST: TẮT ==")

    def head(self, text, sub=""):
        ctk.CTkLabel(self.content, text=text, font=(FT, 22, "bold"), text_color=TEXT).pack(anchor="w", pady=(0, 2))
        if sub:
            ctk.CTkLabel(self.content, text=sub, font=(FT, 13), text_color=TEXT2, justify="left", wraplength=640).pack(anchor="w", pady=(0, 14))

    def card(self):
        c = ctk.CTkFrame(self.content, fg_color=CARD, corner_radius=14, border_width=1, border_color=BORDER)
        c.pack(fill="x", pady=8); return c

    def write(self, s):
        if not s.endswith("\n"): s += "\n"
        self.log.configure(state="normal"); self.log.insert("end", s); self.log.see("end"); self.log.configure(state="disabled")

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

    # ====================== BƯỚC 1 ======================
    def show_step1(self):
        self.set_step(1); self.clear()
        self.head("Bạn muốn tải khóa nào?", "Chọn một khóa đã có, hoặc thêm khóa mới trực tiếp từ tài khoản Skool của bạn.")
        try: miss = self.env_missing()
        except Exception: miss = []
        if miss:
            ban = ctk.CTkFrame(self.content, fg_color="#F4F4F5", corner_radius=12, border_width=1, border_color="#D4D4D8"); ban.pack(fill="x", pady=(0, 8))
            ctk.CTkLabel(ban, text="⚠  Thiếu: " + ", ".join(m[0].split(" (")[0] for m in miss), text_color=TEXT, font=(FT, 12, "bold")).pack(side="left", padx=14, pady=10)
            btn(ban, "Kiểm tra & cài", self.show_check, kind="warn", width=140).pack(side="right", padx=10, pady=8)
        items = self.existing_courses(); card = self.card()
        if items:
            ctk.CTkLabel(card, text="Khóa đã có", font=(FT, 12, "bold"), text_color=TEXT2).pack(anchor="w", padx=16, pady=(12, 4))
            self.pick_var = ctk.StringVar(value=items[0])
            for it in items:
                ctk.CTkRadioButton(card, text=it, variable=self.pick_var, value=it, font=(FT, 13), text_color=TEXT,
                                   fg_color=PRIMARY, hover_color=PRIMARY_H).pack(anchor="w", padx=18, pady=5)
            ctk.CTkFrame(card, fg_color="transparent", height=8).pack()
        else:
            ctk.CTkLabel(card, text="(Chưa có khóa nào — hãy thêm khóa mới)", font=(FT, 12), text_color=TEXT2).pack(padx=16, pady=16)
            self.pick_var = ctk.StringVar(value="")
        row = ctk.CTkFrame(self.content, fg_color="transparent"); row.pack(fill="x", pady=14)
        btn(row, "➕  Thêm khóa mới từ Skool", self.go_import, width=230).pack(side="left")
        if items: btn(row, "Tiếp tục  →", self.use_existing, kind="success", width=150).pack(side="right")

    def use_existing(self):
        v = self.pick_var.get().strip()
        if not v: return
        self.mode = "existing"; self.course_name = None if v.startswith("SkoolCourse") else v; self.show_step3()

    def go_import(self): self.mode = "new"; self.show_step2()

    # ====================== BƯỚC 2 ======================
    def show_step2(self):
        self.set_step(2); self.clear()
        self.head("Lấy khóa mới từ Skool", "Làm theo 3 nút. App mở một cửa sổ trình duyệt riêng — bạn đăng nhập và mở đúng khóa, app tự lấy danh sách.")
        f = ctk.CTkFrame(self.content, fg_color="transparent"); f.pack(fill="x")
        self.b_open = btn(f, "1.   Mở Skool & đăng nhập", self.do_open, height=44); self.b_open.pack(fill="x", pady=5)
        self.b_list = btn(f, "2.   Lấy danh sách chương", self.do_list, kind="secondary", height=44, state="disabled"); self.b_list.pack(fill="x", pady=5)
        self.chap_box = ctk.CTkScrollableFrame(self.content, fg_color=CARD, corner_radius=14, height=210, label_text="")
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
        ctk.CTkLabel(self.chap_box, text=f"Khóa: {group} — chọn chương cần tải", font=(FT, 12, "bold"), text_color=PRIMARY).pack(anchor="w", padx=6, pady=(4, 6))
        self.chapters = []
        for c in chapters:
            var = ctk.BooleanVar(value=True)
            ctk.CTkCheckBox(self.chap_box, text=c["title"], variable=var, font=(FT, 13), text_color=TEXT, fg_color=PRIMARY, hover_color=PRIMARY_H).pack(anchor="w", padx=8, pady=3)
            self.chapters.append({"id": c["id"], "title": c["title"], "var": var})
        nm = ctk.CTkFrame(self.dump_row, fg_color="transparent"); nm.pack(fill="x", pady=(2, 0))
        ctk.CTkLabel(nm, text="Đặt tên khóa:", font=(FT, 13), text_color=TEXT).pack(side="left")
        self.name_var = ctk.StringVar(value=group)
        ctk.CTkEntry(nm, textvariable=self.name_var, font=(FT, 13), width=260).pack(side="left", padx=10)
        self.b_dump = btn(self.dump_row, "3.   Tải dữ liệu các chương đã chọn  →", self.do_dump, height=44); self.b_dump.pack(fill="x", pady=8)
        self.dump_status = ctk.CTkLabel(self.dump_row, text="", font=(FT, 12, "bold"), text_color=PRIMARY); self.dump_status.pack(anchor="w")
        self.dump_pb = ctk.CTkProgressBar(self.dump_row, height=12, corner_radius=6, progress_color=PRIMARY); self.dump_pb.set(0)

    def do_dump(self):
        if self._dumping: return
        sel = [c for c in self.chapters if c["var"].get()]
        if not sel: messagebox.showinfo("Chưa chọn", "Hãy tick ít nhất 1 chương."); return
        name = self.name_var.get().strip()
        if not name: messagebox.showinfo("Thiếu tên", "Hãy đặt tên khóa."); return
        self.course_name = name; self._dumping = True
        self.b_dump.configure(state="disabled", text="⏳   Đang lấy dữ liệu...")
        self.dump_status.configure(text=f"Đang lấy dữ liệu: 0/{len(sel)} chương"); self.dump_pb.pack(fill="x", pady=(2, 6)); self.dump_pb.set(0)
        out = C.BASE / "courses" / name; self.write(f"Đang lấy dữ liệu {len(sel)} chương vào: {out}")
        self.sb.dump([{"id": c["id"], "title": c["title"]} for c in sel], out)

    # ====================== BƯỚC 3 ======================
    def show_step3(self):
        self.set_step(3); self.clear()
        nm = self.course_name or "SkoolCourse (khóa hiện tại)"
        self.head(f"Sẵn sàng tải: {nm}", "Bấm Bắt đầu để tải toàn bộ video + tài liệu. Có thể bật tạo phụ đề tiếng Anh chạy ngầm sau khi tải.")
        card = self.card()
        self.opt_sub = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(card, text="Tạo phụ đề tiếng Anh (chạy ngầm sau khi tải xong)", variable=self.opt_sub, font=(FT, 13), text_color=TEXT, fg_color=PRIMARY, hover_color=PRIMARY_H).pack(anchor="w", padx=16, pady=12)
        self.opt_test = ctk.BooleanVar(value=self.admin)
        if self.admin:
            ctk.CTkCheckBox(card, text="🔧 Chế độ TEST — chỉ kiểm tra, KHÔNG tải thật (dry-run)", variable=self.opt_test, font=(FT, 13, "bold"), text_color="#9A6700", fg_color=WARNING, hover_color="#B98700").pack(anchor="w", padx=16, pady=(0, 12))
        row = ctk.CTkFrame(self.content, fg_color="transparent"); row.pack(fill="x", pady=16)
        btn(row, "←  Quay lại", self.show_step1, kind="ghost", width=110).pack(side="left")
        btn(row, "▶   Bắt đầu tải", self.start_download, kind="success", width=190, height=46).pack(side="right")

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
        self.chap_scroll = ctk.CTkScrollableFrame(self.content, fg_color=CARD, corner_radius=14, height=230); self.chap_scroll.pack(fill="x", pady=(0, 6))
        self.run_lbl = ctk.CTkLabel(self.content, text="⏳  Đang chạy…", font=(FT, 13, "bold"), text_color=WARNING); self.run_lbl.pack(anchor="w", pady=(8, 4))
        self.done_row = ctk.CTkFrame(self.content, fg_color="transparent"); self.done_row.pack(fill="x", pady=6)
        btn(self.done_row, "📁  Mở thư mục dự án", self.open_folder, kind="secondary", width=210).pack(side="left", padx=(0, 8))
        self.btn_stop = btn(self.done_row, "■  Dừng", self.do_stop, kind="danger", width=120); self.btn_stop.pack(side="left")
        self.build_chapter_rows(); self.refresh4()

    def build_chapter_rows(self):
        self.chap_widgets = {}
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
        if not hasattr(self, "pct_lbl"): return
        rows, dtot, etot, size = self.scan_progress()
        pct = round(dtot * 100 / etot) if etot else 0
        self.pct_lbl.configure(text=f"{pct}%"); self.pb4.set(pct / 100)
        self.status4.configure(text=f"{dtot}/{etot} video   ·   {fmt_size(size)}")
        self.chap_hdr.configure(text=f"Chương ({len(rows)})")
        for r in rows:
            w = self.chap_widgets.get(r["name"])
            if not w: continue
            ic, col = ICON.get(r["status"], ("•", TEXT2))
            p = round(r["done"] * 100 / r["exp"]) if r["exp"] else 0
            w["ic"].configure(text=ic, text_color=col); w["pb"].set(p / 100)
            w["cnt"].configure(text=f"{r['done']}/{r['exp']}"); w["pct"].configure(text=f"{p}%")

    def show_done(self):
        for w in self.done_row.winfo_children(): w.destroy()
        self.refresh4()
        if hasattr(self, "run_lbl"): self.run_lbl.configure(text="✓  Hoàn tất", text_color=SUCCESS)
        if getattr(self, "opt_sub", None) and self.opt_sub.get(): self.write("Bật phụ đề chạy ngầm..."); self.run_sub_on()
        btn(self.done_row, "📁  Mở thư mục dự án", self.open_folder, kind="secondary", width=210).pack(side="left", padx=(0, 8))
        btn(self.done_row, "↻  Làm khóa khác", self.show_step1, width=170).pack(side="left")

    # ---------- tien trinh ----------
    def start_download(self):
        args = ([] if not self.course_name else ["--course", self.course_name])
        test = bool(getattr(self, "opt_test", None) and self.opt_test.get())
        if test: args.append("--dry-run")
        self.show_step4()
        if test and hasattr(self, "run_lbl"): self.run_lbl.configure(text="🔧  CHẾ ĐỘ TEST — chỉ kiểm tra, không tải thật", text_color="#9A6700")
        self.start([PY, "main.py"] + args, "TẢI KHÓA" + (" (TEST)" if test else ""), on_done=self.show_done)

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
            if hasattr(self, "run_lbl"): self.run_lbl.configure(text="■  Đã dừng", text_color=DANGER)

    def open_folder(self):
        r = self.course_root(); r.mkdir(parents=True, exist_ok=True)
        try: os.startfile(str(r))
        except Exception as e: messagebox.showerror("Lỗi", f"Không mở được thư mục: {e}")

    def poll(self):
        if self.sb:
            try:
                while True: self.on_browser_event(self.sb.evt_q.get_nowait())
            except queue.Empty: pass
        try:
            while True:
                tag, s = self.q.get_nowait()
                if s == SENTINEL:
                    rc = self.proc.returncode if self.proc else 0
                    self.write(f"--- Kết thúc (mã {rc}) ---"); self.proc = None
                    if getattr(self, "_on_done", None): self._on_done(); self._on_done = None
                else: self.write(s.rstrip("\n"))
        except queue.Empty: pass
        if hasattr(self, "chap_scroll") and self.chap_scroll.winfo_exists() and (time.time() - self._lastref > 1.5):
            self._lastref = time.time(); self.refresh4()
        self.root.after(150, self.poll)

    def on_browser_event(self, e):
        t = e.get("type")
        if t == "ready": self.write("Trình duyệt sẵn sàng."); self.sb.open()
        elif t == "opened":
            self.write("Đã mở Skool. Đăng nhập & mở trang Classroom, rồi bấm nút 2.")
            if hasattr(self, "b_list"): self.b_list.configure(state="normal")
        elif t == "log": self.write(e["msg"])
        elif t == "need_classroom": messagebox.showinfo("Mở trang Classroom", e["msg"])
        elif t == "chapters":
            self.write(f"Tìm thấy {len(e['chapters'])} chương."); self.render_chapters(e["group"], e["chapters"])
        elif t == "dump_progress":
            self.write(f"[{e['i']}/{e['n']}] {e['title']}")
            if hasattr(self, "dump_status"):
                pct = round(e["i"] * 100 / max(1, e["n"]))
                self.dump_status.configure(text=f"Đang lấy: {e['i']}/{e['n']} chương ({pct}%) — {e['title']}"); self.dump_pb.set(pct / 100)
        elif t == "dumped":
            self._dumping = False; self.write(f"Đã lấy xong {e['ok']}/{e['total']} chương → {e['out_dir']}")
            if hasattr(self, "dump_status"): self.dump_status.configure(text=f"✓ Đã lấy {e['ok']}/{e['total']} chương"); self.dump_pb.set(1)
            messagebox.showinfo("Xong", f"Đã lấy dữ liệu khóa ({e['ok']}/{e['total']} chương).\nTiếp tục để tải video."); self.show_step3()
        elif t == "error":
            self.write(f"[LỖI trình duyệt] {e['msg']}"); messagebox.showerror("Lỗi", e["msg"])


def main():
    root = ctk.CTk()
    App(root)
    if os.environ.get("GUI_SMOKE_TEST"): root.after(900, root.destroy)
    root.mainloop()


if __name__ == "__main__":
    main()
