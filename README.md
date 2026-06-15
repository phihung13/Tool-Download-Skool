# Skool Archiver

Công cụ lưu trữ **toàn bộ một khóa học Skool** về máy: cây thư mục theo chương/bài, video (native Skool + Loom + YouTube), mô tả bài, tài liệu (resources) và **phụ đề tiếng Anh (Whisper)** — chạy bằng **một lệnh**, có **kiểm tra môi trường trước khi chạy** và **báo lỗi kèm cách xử lý**.

> Đã kiểm chứng trên khóa *AI Automations by Jack* (584 bài, ~170 GB).

---

## 0. Cấu trúc thư mục

Chỉ những thứ bạn cần dùng nằm ở ngoài; toàn bộ mã nguồn kỹ thuật gom trong `app/`.

```
Archiver/
├─ run.cmd                       ← chạy pipeline (double-click / dòng lệnh)
├─ setup.cmd                     ← cài đặt máy mới
├─ install_transcribe_task.cmd   ← bật phụ đề chạy ngầm
├─ uninstall_transcribe_task.cmd ← tắt phụ đề ngầm
├─ extractor.js                  ← dán vào Console trình duyệt để dump
├─ README.md
├─ docs/                         ← tài liệu (.docx): hướng dẫn, SOP, báo cáo
├─ logs/                         ← log mỗi lần chạy (tự sinh)
└─ app/                          ← mã nguồn (Python + PowerShell), thường không cần đụng
```

→ Người dùng chỉ thao tác với 4 file `.cmd` + `extractor.js`. Mọi thứ trong `app/` do các `.cmd` tự gọi.

---

## 1. Pipeline làm gì

`run.cmd` → `app/run.ps1` → `app/main.py` chạy lần lượt (có **preflight** kiểm tra môi trường ở đầu):

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

Double-click **`setup.cmd`** (hoặc trong PowerShell: `.\setup.ps1`). Nó tạo venv + cài thư viện + ffmpeg + thử cài Node + chạy preflight.

> 💡 Máy hiện tại **đã có sẵn** `..\whisper\venv` đầy đủ (yt-dlp + faster-whisper + model). **Không cần** chạy setup — `run.ps1` tự dùng venv đó.
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
.\run.cmd --course "X" --only videos            # 1 bước: folders|extras|videos|transcribe|audit
.\run.cmd --course "X" --only videos --dry-run  # liệt kê, không tải
.\run.cmd --course "X" --cookies-file cookies.txt   # nếu video cần đăng nhập
python app\preflight.py --course "X"           # chỉ kiểm tra môi trường
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

> Whisper chỉ ra **text đúng ngôn ngữ gốc** (tiếng Anh). Muốn **phụ đề tiếng Việt** cần thêm bước dịch máy riêng cho file `.srt`.

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
| Native Skool **403 Forbidden** | token **24h hết hạn** | Dump lại `vid__*.json` → `--only videos` |
| Resource tải lỗi | link file **8h hết hạn** | Dump lại `meta__*.json` → `--only extras` |
| `Failed to decrypt with DPAPI` | Chrome/Edge mã hóa cookie (ABE) | Đừng dùng `--cookies-browser`; xuất `cookies.txt` → `--cookies-file` |
| ORPHAN trong audit | tên chương/bài đổi giữa 2 lần dump | Chuyển `video.*` về đúng folder, xóa folder thừa, `--only audit` |
| `[!] khong khop folder` (NOFOLDER) | chưa chạy `folders` | Chạy `--only folders` trước |
| Chặn chạy `.ps1` | ExecutionPolicy | Dùng file `.cmd` (đã tự bypass) |
| Transcribe lỗi tải model | mạng/HuggingFace | Watcher tự thử lại; kiểm tra mạng |

---

## 10. Ghi chú bàn giao

- **Bàn giao = zip mỗi thư mục `Archiver\`** (bỏ `__pycache__\`, `logs\`). Mọi thứ khác trong `E:\SkoolProject\` là dữ liệu/môi trường, dựng lại được từ `Archiver\` + `setup`.
- **Nguồn chuẩn duy nhất là `Archiver\`.** Script lẻ ở thư mục gốc (`download_videos.py`, `check_video.py`, `make_folder.py`, `save_extras.py`) là **bản cũ standalone đã được gộp** — giữ tham khảo, không cần dùng.
- Quy tắc token: **native 24h · file/resource 8h** → luôn dump & chạy trong ngày.
- Whisper trên CPU rất chậm với khóa lớn (có thể nhiều giờ/ngày). Có GPU NVIDIA → cài `torch`/CUDA để nhanh hơn nhiều.
