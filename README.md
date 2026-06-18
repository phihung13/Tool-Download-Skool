# Skool Archiver

Công cụ lưu trữ **toàn bộ một khóa học Skool** về máy: cây thư mục theo chương/bài, video (native Skool + Loom + YouTube), mô tả bài, tài liệu (resources) và **phụ đề tiếng Anh (Whisper)** — chạy bằng **một lệnh**, có **kiểm tra môi trường trước khi chạy** và **báo lỗi kèm cách xử lý**.

> Đã kiểm chứng trên khóa *AI Automations by Jack* (584 bài, ~170 GB).

---

## 0. Cấu trúc thư mục

Chỉ những thứ bạn cần dùng nằm ở ngoài; toàn bộ mã nguồn kỹ thuật gom trong `app/`.

```
Archiver/
├─ SkoolArchiver.cmd             ← ⭐ BẤM PHÁT LÀ CHẠY (lần đầu tự cài → mở giao diện)
├─ Nâng cao/                     ← công cụ dòng lệnh (KHÔNG bắt buộc)
│  ├─ Tai bang dong lenh.cmd     ← chạy pipeline bằng dòng lệnh
│  ├─ Cai transcribe nen.cmd     ← bật phụ đề chạy ngầm (Scheduled Task)
│  └─ Go transcribe nen.cmd      ← tắt phụ đề ngầm
├─ extractor.js                  ← dán vào Console trình duyệt để dump
├─ README.md
├─ docs/                         ← tài liệu (.docx): hướng dẫn, SOP, báo cáo
├─ logs/                         ← log mỗi lần chạy (tự sinh)
└─ app/                          ← mã nguồn (Python + PowerShell), không cần đụng
```

→ **Bình thường chỉ cần duy nhất `SkoolArchiver.cmd`.** Lần đầu trên máy mới nó **tự cài** (tạo venv + thư viện + ffmpeg), các lần sau **mở giao diện ngay** — không cần chạy setup hay run gì cả. Folder `Nâng cao/` chỉ dùng khi muốn thao tác bằng dòng lệnh.

---

## 1. Pipeline làm gì

Giao diện gọi pipeline này; muốn chạy tay thì dùng `Nâng cao\Tai bang dong lenh.cmd` → `app/run.ps1` → `app/main.py`, chạy lần lượt (có **preflight** kiểm tra môi trường ở đầu):

| Bước | Module | Việc |
|------|--------|------|
| *preflight* | [preflight.py](app/preflight.py) | Kiểm tra Python/Node/ffmpeg/yt-dlp/đĩa/JSON → PASS/WARN/FAIL. FAIL thì dừng |
| `folders`    | [folders.py](app/folders.py)    | Dựng cây `NN - Tên` cho từng chương/bài (tự tạo cả folder **chương** cho khóa mới) |
| `extras`     | [extras.py](app/extras.py)      | Ghi `description.md` + tải `resources/` *(link resource hết hạn sau **8h**)* |
| `videos`     | [videos.py](app/videos.py)      | Tải video → `video.<ext>` (yt-dlp). 2 lượt: **native trước** *(token **24h**)*, rồi Loom/YouTube. **Phân loại lỗi tự động** |
| `transcribe` | [transcribe.py](app/transcribe.py) | *(tùy chọn `--transcribe`)* faster-whisper → `video.txt` + `video.srt` |
| `audit`      | [audit.py](app/audit.py)        | Đối chiếu JSON ↔ file thực, xuất `video_audit.txt` |

Toàn bộ **resume an toàn**: bài xong tự skip, mất mạng tự chờ, tải dở tự nối tiếp, chạy lại bao nhiêu lần cũng được.

---

## 1b. Giao diện (SkoolArchiver.cmd) — cách dùng chính

Double-click **`SkoolArchiver.cmd`** → mở app cửa sổ (wizard 4 bước). Lần đầu trên máy mới nó tự cài môi trường rồi mới mở. Ngoài tải khóa, app có:

**Trình tải theo chương/bài (mới):** Sau khi chọn khóa, app mở **trình quản lý tải**: liệt kê tất cả chương, bấm **▸** để mở các bài bên trong. Có thể **⬇ Tải cả chương**, **⬇ tải từng bài**, hoặc **⬇ Tải toàn bộ**; **■ Dừng** bất cứ lúc nào (bài đã tải vẫn giữ). Trạng thái ✓/⏳ cập nhật trực tiếp. Xong → trang **Tạo phụ đề** → trang **Dịch tiếng Việt**. CLI tương ứng: `--chapter "<tên chương>"`, `--lesson "<đường dẫn bài>"`.

**Hoàn thiện việc tải (Nhóm B):**

| Tính năng | Mô tả |
|-----------|-------|
| **Tải tiếp khóa dở** | Bước 1 hiện ngay `đã tải / tổng · dung lượng · còn N bài` cho từng khóa; nút đổi thành **“Tải tiếp (còn N bài)”**. Chỉ tải phần thiếu (bài có rồi tự bỏ qua) |
| **Tự thử lại đến khi tải đủ** | Tick ô ở Bước 3 → app tự lặp lại `tải → kiểm tra`, **chờ rồi tải lại** khi bị YouTube/Skool giới hạn, cho đến khi không còn bài nào cứu được (CLI: `--until-clean`) |
| **Kiểm tra cập nhật khóa** | Nút **🔄 Kiểm tra cập nhật** ở Bước 1: so danh sách chương trên Skool với bản đã lưu, **chương MỚI được tick sẵn**, chỉ tải phần mới |
| **Cứu bài native hết hạn** | App tự đọc hạn token (JWT `exp`) → nếu có bài native **403/hết hạn**, hiện nút **🔑 Cứu bài native**: mở trình duyệt lấy lại token mới rồi tải lại đúng các chương đó |
| **Xóa khóa** | Nút **🗑 Xóa khóa** ở Bước 1: xóa khóa đã chọn (hiện rõ dung lượng trước khi xóa). Mặc định đưa vào **Thùng rác** (khôi phục được) nếu có `send2trash` |

**Xuất & Báo cáo (Nhóm A)** — nút **📄 Xuất & Báo cáo** ở thanh bên:

| Tính năng | Mô tả | Yêu cầu |
|-----------|-------|---------|
| **Gộp & xuất Word** | Gộp `description.md` + lời giảng (`video.txt`) toàn khóa → `_TongHop.md` **và** `_TongHop.docx` | `python-docx` cho bản `.docx` (thiếu vẫn có `.md`) |
| **Dịch tiếng Việt** | Dịch file tổng hợp sang tiếng Việt → `_TongHop.vi.md` | **API key Claude** (dán ngay trong app) **hoặc** `deep-translator` (Google, miễn phí) |
| **Tóm tắt + To-do (AI)** | Tóm tắt từng chương + **việc áp dụng cho Trường Việt Anh** → `_TomTat.md` | **API key Claude** |

> **API key Claude điền sống trong app:** ở màn “📄 Xuất & Báo cáo” có ô dán API key (lấy ở console.anthropic.com → API Keys). Key lưu tại `app\.settings.json` **trên máy này** (đã `.gitignore`), chỉ gửi tới API Claude. Vẫn dùng được biến môi trường `ANTHROPIC_API_KEY` nếu thích (biến môi trường được ưu tiên).

→ Chuỗi trọn vẹn: **tải → bóc lời giảng → dịch → tóm tắt/to-do → xuất file gửi sếp.**

---

## 2. Yêu cầu

| Thành phần | Vì sao | Cài |
|------------|--------|-----|
| **Python 3.9+** | chạy pipeline | python.org |
| **Node.js (LTS)** | yt-dlp cần JS runtime để **vượt chặn bot YouTube** | https://nodejs.org *(setup tự thử cài qua winget)* |
| **ffmpeg** | ghép video | tự cài qua `setup.ps1` |
| yt-dlp, faster-whisper | tải + phụ đề | qua `setup.ps1` |

> ⚠️ **Thiếu Node.js là nguyên nhân #1 khiến YouTube fail hàng loạt.** `preflight` sẽ cảnh báo nếu thiếu.

---

## 3. Cài đặt (máy mới)

**Không cần làm gì riêng** — cứ double-click **`SkoolArchiver.cmd`**, lần đầu nó tự tạo venv + cài thư viện + ffmpeg rồi mở giao diện. (Nếu máy chưa có Python, nó hiện thông báo bảo tải Python 3.11+ ở python.org, nhớ tick *Add to PATH*.)

> 💡 Máy hiện tại **đã có sẵn** `..\whisper\venv` đầy đủ (yt-dlp + faster-whisper + model) → `SkoolArchiver.cmd` tự dùng venv đó, mở giao diện tức thì.
>
> 🔒 Nếu Windows chặn chạy `.ps1` (ExecutionPolicy): cứ dùng file **`.cmd`** (đã tự bypass), khỏi chỉnh gì.

---

## 4. Quy trình lưu trữ một khóa mới

### Bước A — Dump dữ liệu khóa (trình duyệt, ĐÃ đăng nhập Skool)

> ❗ Thủ công vì cần phiên đăng nhập. Token native **24h**, link file **8h** → **dump xong xử lý ngay trong ngày**.

1. Mở khóa ở trang `…/classroom`, bật **F12 → Console**.
2. Dán toàn bộ [extractor.js](extractor.js) → Enter.
   - Ở **/classroom**: in danh sách chương + tự tải **`_chapters.json`** (thứ tự chương).
   - Ở một **trang chương**: tự dump `vid__<Chương>.json` + `meta__<Chương>.json`.
3. Lần lượt mở từng chương ở sidebar, gõ `skoolDumpChapter()`.
4. Gom mọi file vừa tải vào: `E:\SkoolProject\courses\<Tên khóa>\`

### Bước B — Một lệnh

> Cách nhanh nhất là dùng giao diện (`SkoolArchiver.cmd`). Các ví dụ `run.cmd` dưới đây nay nằm ở **`Nâng cao\Tai bang dong lenh.cmd`** (cùng tham số):

```powershell
.\run.cmd --course "<Tên khóa>"
.\run.cmd --course "<Tên khóa>" --transcribe  # kèm phụ đề luôn
```

Xong. Video + tài liệu + mô tả nằm trong `courses\<Tên khóa>\`, báo cáo ở `video_audit.txt`.

---

## 5. Bảng lệnh

```powershell
.\run.cmd --list-courses                       # liệt kê các khóa
.\run.cmd --course "X"                          # full pipeline (có preflight)
.\run.cmd --course "X" --transcribe             # + phụ đề
.\run.cmd --course "X" --until-clean            # tự thử lại đến khi tải đủ (chờ nếu bị giới hạn)
.\run.cmd --course "X" --only videos            # 1 bước: folders|extras|videos|transcribe|audit
.\run.cmd --course "X" --only videos --native-only  # chỉ tải native (cứu bài hết token)
.\run.cmd --course "X" --only videos --dry-run  # liệt kê, không tải
.\run.cmd --course "X" --cookies-file cookies.txt   # nếu video cần đăng nhập
python app\preflight.py --course "X"           # chỉ kiểm tra môi trường
python app\export.py   --course "X" --docx     # gộp & xuất Word (Nhóm A)
python app\ai_tools.py --course "X" --translate --summary   # dịch + tóm tắt/to-do (cần API key / deep-translator)
```

Mỗi lần chạy ghi log vào `Archiver\logs\run_<thời gian>.log`. Không truyền `--course` ⇒ dùng `SkoolCourse` (khóa cũ).

---

## 6. Phụ đề chạy ngầm (Whisper) — sống qua reboot / tắt Claude

Engine mặc định **faster-whisper + `distil-large-v3`** (English-only, nhanh & nhẹ; tự dùng GPU NVIDIA nếu có, không thì CPU int8). Xuất `video.txt` + `video.srt` **cùng folder với video**.

**Chạy ngầm bằng Windows Task Scheduler** (độc lập Claude, tự tiếp tục sau khi bật lại máy, xong thì báo Windows):

```powershell
.\install_transcribe_task.cmd -All                       # quét SkoolCourse + mọi courses/*
.\install_transcribe_task.cmd -Course "AI Automations by Jack"
.\uninstall_transcribe_task.cmd                          # gỡ khi xong
```

Cơ chế:
- Chạy ngay + **tự chạy lại mỗi lần đăng nhập** → tắt/mở máy vẫn tiếp tục (bài nào có `.txt` rồi thì bỏ qua).
- Chạy **song song** lúc đang tải: bỏ qua file đang tải dở; **không tự kết thúc khi còn đang tải**.
- Khi transcribe hết & không còn tải → **hiện thông báo Windows** rồi dừng. (Claude tắt vẫn báo, vì đây là task của Windows.)

Chạy tay (không cần task): `.\app\run_transcribe_watch.ps1 --all` (hoặc thêm `--once` để làm 1 lượt rồi thoát).

> Whisper chỉ ra **text đúng ngôn ngữ gốc** (tiếng Anh). Muốn **bản tiếng Việt** dùng nút **📄 Xuất & Báo cáo → 🌐 Dịch tiếng Việt** (xem mục 1b) để dịch file tổng hợp.

---

## 7. Cấu hình ([config.py](app/config.py))

| Khóa | Mặc định | Ý nghĩa |
|------|----------|---------|
| `JS_RUNTIME` | `"node"` | JS runtime cho yt-dlp (vượt chặn bot YouTube). `""` = tắt |
| `ONLY_HOSTS` | `[]` | `["stream.video.skool.com"]` = chỉ tải native |
| `YT_COOKIES_FILE` | `""` | đường dẫn `cookies.txt` (Netscape) nếu cần đăng nhập |
| `YT_COOKIES_BROWSER` | `""` | `"firefox"` (Chrome/Edge bản mới bị App-Bound Encryption — **không dùng được**) |
| `MAX_TRIES` / `RETRY_WAIT` | `6` / `8` | số lần thử lại / giây nghỉ mỗi video |
| `WHISPER_ENGINE` | `"faster-whisper"` | hoặc `"openai-whisper"` |
| `WHISPER_MODEL` | `"distil-large-v3"` | hoặc `"large-v3-turbo"`, `"large-v3"`… |
| `WHISPER_TASK` | `"transcribe"` | `"translate"` = dịch SANG tiếng Anh |
| `WHISPER_DEVICE` / `WHISPER_COMPUTE` | `auto` / `int8` | tự dò GPU; CPU dùng int8 |
| `WATCH_INTERVAL` / `WATCH_MIN_AGE` | `90` / `60` | chu kỳ quét / tuổi tối thiểu của file trước khi transcribe |
| `SKOOL_BASE` *(env)* | *(thư mục cha của Archiver)* | đổi thư mục gốc (không còn hardcode ổ E:) |

---

## 8. Cấu trúc output

```
courses\<Tên khóa>\
├─ _chapters.json, vid__*.json, meta__*.json   ← dump đầu vào
├─ video_audit.txt                              ← báo cáo
├─ _TongHop.md / _TongHop.docx                  ← Gộp & xuất (Nhóm A)
├─ _TongHop.vi.md                               ← bản dịch tiếng Việt
├─ _TomTat.md                                   ← tóm tắt + to-do (AI)
├─ 01 - <Chương>\ 01 - <Bài>\
│  ├─ video.mp4
│  ├─ video.txt / video.srt   (nếu transcribe)
│  ├─ description.md
│  └─ resources\  (_links.txt + file đính kèm)
```

---

## 9. Xử lý sự cố

Khi tải lỗi, pipeline **tự phân loại nguyên nhân và in cách xử lý**, đồng thời gom nhóm ở cuối. Tham chiếu nhanh:

| Triệu chứng | Nguyên nhân | Cách xử lý |
|-------------|-------------|------------|
| *"Sign in to confirm you're not a bot"* (YouTube) | thiếu JS runtime | Cài **Node.js**; tự dùng `--js-runtimes node` |
| `UnicodeEncodeError` / `'charmap'` (ký tự `▶`…) | console Windows cp1252 | Đã xử lý: ép UTF-8 (`run.ps1` + `setup_console`) |
| Native Skool **403 Forbidden** | token **24h hết hạn** | GUI: nút **🔑 Cứu bài native** (tự dump lại token + tải). CLI: dump lại `vid__*.json` → `--only videos --native-only` |
| Resource tải lỗi | link file **8h hết hạn** | Dump lại `meta__*.json` → `--only extras` |
| `Failed to decrypt with DPAPI` | Chrome/Edge mã hóa cookie (ABE) | Đừng dùng `--cookies-browser`; xuất `cookies.txt` → `--cookies-file` |
| ORPHAN trong audit | tên chương/bài đổi giữa 2 lần dump | Chuyển `video.*` về đúng folder, xóa folder thừa, `--only audit` |
| `[!] khong khop folder` (NOFOLDER) | chưa chạy `folders` | Chạy `--only folders` trước |
| Chặn chạy `.ps1` | ExecutionPolicy | Dùng file `.cmd` (đã tự bypass) |
| Transcribe lỗi tải model | mạng/HuggingFace | Watcher tự thử lại; kiểm tra mạng |

---

## 10. Ghi chú bàn giao

- **Bàn giao = zip mỗi thư mục `Archiver\`** (bỏ `__pycache__\`, `logs\`, **`app\.browser\`**, **`app\.settings.json`** — chứa API key). Mọi thứ khác trong `E:\SkoolProject\` là dữ liệu/môi trường, dựng lại được từ `Archiver\` + `setup`.
- **Sang máy khác là KHÔNG có khóa nào.** Khóa đã tải nằm ở `courses\` và `SkoolCourse\` — **ngoài** `Archiver\`. Vì thế zip `Archiver\` không kèm khóa; máy mới mở app thấy danh sách **trống**, tự tải khóa mới. (`app\.browser\` là phiên đăng nhập Skool của bạn — đừng đưa kèm.)
- Muốn dọn khóa ngay trên máy này: dùng nút **🗑 Xóa khóa** ở Bước 1 (mặc định đưa vào **Thùng rác**, khôi phục được).
- **Nguồn chuẩn duy nhất là `Archiver\`.** Script lẻ ở thư mục gốc (`download_videos.py`, `check_video.py`, `make_folder.py`, `save_extras.py`) là **bản cũ standalone đã được gộp** — giữ tham khảo, không cần dùng.
- Quy tắc token: **native 24h · file/resource 8h** → luôn dump & chạy trong ngày.
- Whisper trên CPU rất chậm với khóa lớn (có thể nhiều giờ/ngày). Có GPU NVIDIA → cài `torch`/CUDA để nhanh hơn nhiều.
