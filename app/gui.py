#!/usr/bin/env python3
"""
Giao dien (GUI) wizard cho Skool Archiver - tung buoc, danh cho NGUOI DUNG.
Mo bang: double-click GiaoDien.cmd
"""
import os, sys, queue, threading, subprocess
from pathlib import Path
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as C

HERE = Path(__file__).resolve().parent
ARCHIVER = HERE.parent
PY = sys.executable.replace("pythonw.exe", "python.exe")
NO_WIN = 0x08000000 if os.name == "nt" else 0
SENTINEL = "\x00DONE\x00"

# mau
BLUE = "#1F4E79"; BLUE2 = "#2E75B6"; GREY = "#6b6b6b"; BG = "#f4f6f9"
FT = "Segoe UI"

def big_btn(parent, text, cmd, color=BLUE2, **kw):
    b = tk.Button(parent, text=text, command=cmd, bg=color, fg="white",
                  activebackground=BLUE, activeforeground="white",
                  font=(FT, 11, "bold"), relief="flat", bd=0, padx=16, pady=9,
                  cursor="hand2", **kw)
    return b

class App:
    def __init__(self, root):
        self.root = root
        self.proc = None
        self.sb = None
        self.q = queue.Queue()
        self.chapters = []      # [{id,title,var}]
        self.course_name = None
        self.mode = None

        root.title("Skool Archiver")
        root.geometry("760x650"); root.minsize(700, 600)
        root.configure(bg=BG)
        try: ttk.Style().theme_use("vista")
        except Exception: pass

        # header
        head = tk.Frame(root, bg=BLUE, height=64); head.pack(fill="x"); head.pack_propagate(False)
        tk.Label(head, text="  📦  Skool Archiver", bg=BLUE, fg="white",
                 font=(FT, 16, "bold")).pack(side="left", pady=12)
        self.step_lbl = tk.Label(head, text="", bg=BLUE, fg="#cfe0f3", font=(FT, 10))
        self.step_lbl.pack(side="right", padx=16)

        # body (swap)
        self.body = tk.Frame(root, bg=BG); self.body.pack(fill="both", expand=True, padx=18, pady=12)

        # log
        logf = tk.Frame(root, bg=BG); logf.pack(fill="x", padx=18, pady=(0, 10))
        tk.Label(logf, text="Nhật ký", bg=BG, fg=GREY, font=(FT, 9, "bold")).pack(anchor="w")
        self.log = scrolledtext.ScrolledText(logf, height=8, font=("Consolas", 9),
                                             relief="solid", bd=1)
        self.log.pack(fill="x"); self.log.configure(state="disabled")

        self.show_step1()
        self.root.after(120, self.poll)

    # ---------- tien ich ----------
    def clear_body(self):
        for w in self.body.winfo_children(): w.destroy()

    def set_step(self, n, name):
        self.step_lbl.config(text=f"Bước {n}/4  ·  {name}")

    def title(self, text, sub=""):
        tk.Label(self.body, text=text, bg=BG, fg=BLUE, font=(FT, 15, "bold")).pack(anchor="w")
        if sub:
            tk.Label(self.body, text=sub, bg=BG, fg=GREY, font=(FT, 10),
                     justify="left", wraplength=680).pack(anchor="w", pady=(2, 10))

    def write(self, s):
        if not s.endswith("\n"): s += "\n"
        self.log.configure(state="normal"); self.log.insert("end", s)
        self.log.see("end"); self.log.configure(state="disabled")

    def course_root(self, name=None):
        name = name or self.course_name
        if not name or str(name).startswith("SkoolCourse"):
            return C.BASE / "SkoolCourse"
        return C.BASE / "courses" / name

    def existing_courses(self):
        items = []
        sk = C.BASE / "SkoolCourse"
        if sk.exists(): items.append("SkoolCourse (đã có sẵn)")
        cdir = C.BASE / "courses"
        if cdir.exists():
            items += sorted(p.name for p in cdir.iterdir() if p.is_dir())
        return items

    # ====================== BƯỚC 1: chọn khóa ======================
    def show_step1(self):
        self.set_step(1, "Chọn khóa")
        self.clear_body()
        self.title("Bạn muốn tải khóa nào?",
                   "Chọn một khóa đã có sẵn bên dưới, hoặc thêm khóa mới trực tiếp từ tài khoản Skool của bạn.")
        items = self.existing_courses()
        card = tk.Frame(self.body, bg="white", relief="solid", bd=1); card.pack(fill="x", pady=6)
        if items:
            tk.Label(card, text="Khóa đã có:", bg="white", fg=GREY, font=(FT, 10)).pack(anchor="w", padx=12, pady=(10, 2))
            self.pick_var = tk.StringVar(value=items[0])
            for it in items:
                tk.Radiobutton(card, text="   " + it, variable=self.pick_var, value=it, bg="white",
                               font=(FT, 11), anchor="w", selectcolor="white").pack(fill="x", padx=12)
            tk.Frame(card, bg="white", height=8).pack()
        else:
            tk.Label(card, text="(Chưa có khóa nào — hãy thêm khóa mới)", bg="white", fg=GREY,
                     font=(FT, 10, "italic")).pack(padx=12, pady=12)
            self.pick_var = tk.StringVar(value="")

        row = tk.Frame(self.body, bg=BG); row.pack(fill="x", pady=14)
        big_btn(row, "➕  Thêm khóa mới từ Skool", self.go_import, color=BLUE).pack(side="left")
        if items:
            big_btn(row, "Tiếp tục khóa đã chọn  →", self.use_existing).pack(side="right")

    def use_existing(self):
        v = self.pick_var.get().strip()
        if not v: return
        self.mode = "existing"
        self.course_name = None if v.startswith("SkoolCourse") else v
        self.show_step3()

    def go_import(self):
        self.mode = "new"
        self.show_step2()

    # ====================== BƯỚC 2: lấy khóa từ Skool ======================
    def show_step2(self):
        self.set_step(2, "Lấy khóa từ Skool")
        self.clear_body()
        self.title("Lấy khóa mới từ Skool",
                   "Làm theo 3 nút dưới đây. App sẽ mở một cửa sổ trình duyệt riêng — bạn đăng nhập và mở đúng khóa, app tự lấy danh sách.")
        f = tk.Frame(self.body, bg=BG); f.pack(fill="x", pady=4)
        self.b_open = big_btn(f, "1.  Mở Skool & đăng nhập", self.do_open, color=BLUE)
        self.b_open.pack(fill="x", pady=4)
        self.b_list = big_btn(f, "2.  Lấy danh sách chương", self.do_list)
        self.b_list.pack(fill="x", pady=4); self.b_list.config(state="disabled")

        self.chap_box = tk.Frame(self.body, bg="white", relief="solid", bd=1)
        self.dump_row = tk.Frame(self.body, bg=BG)

        back = tk.Frame(self.body, bg=BG); back.pack(side="bottom", fill="x", pady=8)
        ttk.Button(back, text="←  Quay lại", command=self.show_step1).pack(side="left")

    def do_open(self):
        if self.sb is None:
            self.write("Đang mở trình duyệt (lần đầu hơi lâu)...")
            try:
                from skool_browser import SkoolBrowser
                self.sb = SkoolBrowser()
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không mở được trình duyệt: {e}"); return
        else:
            self.sb.open()

    def do_list(self):
        if self.sb: self.write("Đang đọc danh sách chương từ trang hiện tại..."); self.sb.list_chapters()

    def render_chapters(self, group, chapters):
        for w in self.chap_box.winfo_children(): w.destroy()
        for w in self.dump_row.winfo_children(): w.destroy()
        self.chap_box.pack(fill="both", expand=True, pady=8)
        self.dump_row.pack(fill="x", pady=4)
        tk.Label(self.chap_box, text=f"Khóa: {group} — chọn chương cần tải:", bg="white",
                 fg=BLUE, font=(FT, 10, "bold")).pack(anchor="w", padx=10, pady=(8, 2))
        canvas = tk.Canvas(self.chap_box, bg="white", height=180, highlightthickness=0)
        sb = ttk.Scrollbar(self.chap_box, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg="white")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True, padx=6); sb.pack(side="right", fill="y")
        self.chapters = []
        for c in chapters:
            var = tk.BooleanVar(value=True)
            tk.Checkbutton(inner, text="  " + c["title"], variable=var, bg="white",
                           font=(FT, 10), anchor="w", selectcolor="white").pack(fill="x", anchor="w")
            self.chapters.append({"id": c["id"], "title": c["title"], "var": var})
        nm = tk.Frame(self.dump_row, bg=BG); nm.pack(fill="x")
        tk.Label(nm, text="Đặt tên khóa:", bg=BG, font=(FT, 10)).pack(side="left")
        self.name_var = tk.StringVar(value=group)
        tk.Entry(nm, textvariable=self.name_var, font=(FT, 11), width=30).pack(side="left", padx=8)
        big_btn(self.dump_row, "3.  Tải dữ liệu các chương đã chọn  →", self.do_dump, color=BLUE).pack(pady=8)

    def do_dump(self):
        sel = [c for c in self.chapters if c["var"].get()]
        if not sel:
            messagebox.showinfo("Chưa chọn", "Hãy tick ít nhất 1 chương."); return
        name = self.name_var.get().strip()
        if not name:
            messagebox.showinfo("Thiếu tên", "Hãy đặt tên khóa."); return
        self.course_name = name
        out = C.BASE / "courses" / name
        self.write(f"Đang lấy dữ liệu {len(sel)} chương vào: {out}")
        self.sb.dump([{"id": c["id"], "title": c["title"]} for c in sel], out)

    # ====================== BƯỚC 3: tùy chọn ======================
    def show_step3(self):
        self.set_step(3, "Tùy chọn")
        self.clear_body()
        nm = self.course_name or "SkoolCourse (khóa hiện tại)"
        self.title(f"Sẵn sàng tải: {nm}",
                   "Bấm Bắt đầu để tải toàn bộ video + tài liệu. Có thể bật tạo phụ đề tiếng Anh chạy ngầm sau khi tải.")
        self.opt_sub = tk.BooleanVar(value=True)
        tk.Checkbutton(self.body, text="  Tạo phụ đề tiếng Anh (chạy ngầm sau khi tải xong)",
                       variable=self.opt_sub, bg=BG, font=(FT, 11)).pack(anchor="w", pady=8)
        row = tk.Frame(self.body, bg=BG); row.pack(fill="x", pady=16)
        ttk.Button(row, text="←  Quay lại", command=self.show_step1).pack(side="left")
        big_btn(row, "▶  Bắt đầu tải", self.start_download, color="#1e7e34").pack(side="right")

    # ====================== BƯỚC 4: tải / xong ======================
    def show_step4(self):
        self.set_step(4, "Đang tải")
        self.clear_body()
        self.title("Đang tải khóa…", "Theo dõi tiến trình ở khung Nhật ký bên dưới. Bạn có thể bấm Dừng bất cứ lúc nào (chạy lại sẽ tiếp tục).")
        self.status4 = tk.Label(self.body, text="", bg=BG, fg=BLUE, font=(FT, 11, "bold"))
        self.status4.pack(anchor="w", pady=6)
        self.done_row = tk.Frame(self.body, bg=BG); self.done_row.pack(fill="x", pady=10)
        self.btn_stop = big_btn(self.done_row, "■  Dừng", self.do_stop, color="#b02a37")
        self.btn_stop.pack(side="left")
        self.refresh4()

    def refresh4(self):
        root = self.course_root()
        v = sum(1 for p in root.rglob("video.*")
                if p.suffix.lower() in C.VIDEXT and p.stem == "video") if root.exists() else 0
        t = sum(1 for _ in root.rglob("video.txt")) if root.exists() else 0
        self.status4.config(text=f"Video đã tải: {v}    |    Phụ đề: {t}")

    def show_done(self):
        self.set_step(4, "Hoàn tất")
        for w in self.done_row.winfo_children(): w.destroy()
        self.refresh4()
        self.status4.config(text=self.status4.cget("text") + "    ✓ XONG")
        if getattr(self, "opt_sub", None) and self.opt_sub.get():
            self.write("Bật phụ đề chạy ngầm...")
            self.run_sub_on()
        big_btn(self.done_row, "📁  Mở thư mục", self.open_folder, color=GREY).pack(side="left", padx=2)
        big_btn(self.done_row, "↻  Làm khóa khác", self.show_step1, color=BLUE2).pack(side="left", padx=2)

    # ---------- chay tien trinh ----------
    def start_download(self):
        args = ([] if not self.course_name else ["--course", self.course_name])
        self.show_step4()
        self.start([PY, "main.py"] + args, "TẢI KHÓA", on_done=self.show_done)

    def run_sub_on(self):
        c = self.course_name
        ps = HERE / "install_transcribe_task.ps1"
        extra = ["-Course", c] if c else ["-All"]
        subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps)] + extra,
                         creationflags=NO_WIN)

    def start(self, cmd, title, cwd=None, on_done=None):
        if self.proc:
            messagebox.showinfo("Đang bận", "Một tác vụ đang chạy."); return
        self._on_done = on_done
        self.write(f"\n===== {title} =====")
        env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
        try:
            self.proc = subprocess.Popen(cmd, cwd=cwd or HERE, env=env, stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                         errors="replace", bufsize=1, creationflags=NO_WIN)
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

    def open_folder(self):
        r = self.course_root(); r.mkdir(parents=True, exist_ok=True)
        try: os.startfile(str(r))
        except Exception as e: messagebox.showerror("Lỗi", str(e))

    # ---------- vong lap su kien ----------
    def poll(self):
        # subprocess output
        try:
            while True:
                tag, s = self.q.get_nowait()
                if s == SENTINEL:
                    rc = self.proc.returncode if self.proc else 0
                    self.write(f"--- Kết thúc (mã {rc}) ---")
                    self.proc = None
                    if getattr(self, "_on_done", None): self._on_done(); self._on_done = None
                else:
                    self.write(s.rstrip("\n"))
        except queue.Empty:
            pass
        # playwright events
        if self.sb:
            try:
                while True:
                    e = self.sb.evt_q.get_nowait()
                    self.on_browser_event(e)
            except queue.Empty:
                pass
        if hasattr(self, "status4") and self.proc:
            self.refresh4()
        self.root.after(150, self.poll)

    def on_browser_event(self, e):
        t = e.get("type")
        if t == "ready": self.write("Trình duyệt sẵn sàng."); self.sb.open()
        elif t == "opened":
            self.write("Đã mở Skool. Đăng nhập & mở trang Classroom của khóa, rồi bấm nút 2.")
            if hasattr(self, "b_list"): self.b_list.config(state="normal")
        elif t == "log": self.write(e["msg"])
        elif t == "need_classroom": messagebox.showinfo("Mở trang Classroom", e["msg"])
        elif t == "chapters":
            self.write(f"Tìm thấy {len(e['chapters'])} chương.")
            self.render_chapters(e["group"], e["chapters"])
        elif t == "dump_progress":
            self.write(f"[{e['i']}/{e['n']}] {e['title']}")
        elif t == "dumped":
            self.write(f"Đã lấy xong {e['ok']}/{e['total']} chương → {e['out_dir']}")
            messagebox.showinfo("Xong", f"Đã lấy dữ liệu khóa.\nTiếp tục để tải video.")
            self.show_step3()
        elif t == "error":
            self.write(f"[LỖI trình duyệt] {e['msg']}"); messagebox.showerror("Lỗi", e["msg"])

def main():
    root = tk.Tk()
    App(root)
    if os.environ.get("GUI_SMOKE_TEST"):
        root.after(800, root.destroy)
    root.mainloop()

if __name__ == "__main__":
    main()
