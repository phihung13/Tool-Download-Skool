#!/usr/bin/env python3
"""
Skool Archiver - pipeline luu tru khoa hoc Skool bang 1 lenh.

  python main.py --course "AI Automations by Jack"            # folders->extras->video->audit
  python main.py --course "AI Automations by Jack" --transcribe   # + Whisper o cuoi
  python main.py --course "X" --only videos                   # chay 1 buoc: folders|extras|videos|transcribe|audit
  python main.py --course "X" --dry-run                       # video chi liet ke, khong tai
  python main.py --list-courses                               # liet ke cac khoa duoi BASE/courses

Khong truyen --course  ->  dung layout cu BASE/SkoolCourse (khoa da tai).
Truoc khi chay: dump JSON bang extractor.js (xem README) va dat vao thu muc khoa.
Cau hinh mac dinh o config.py; cac co duoi day de override nhanh.
"""
import argparse, time
import config as C
import common as K
import folders, extras, videos, transcribe, audit, preflight

STEPS = {"folders": folders.run, "extras": extras.run, "videos": videos.run,
         "transcribe": transcribe.run, "audit": audit.run}

NATIVE_HOST = "stream.video.skool.com"
# Loi CO THE thu lai tu dong (mang chap chon / YouTube chan bot / loi la). Cac loi
# khac (token het han, video rieng tu...) can nguoi can thiep -> khong loop vo ich.
RECOVERABLE = {"network", "unknown", "bot"}

def run_videos_two_pass():
    """Native (token 24h, de het han) tai truoc, roi Loom/YouTube. Tra ve list fails."""
    orig = C.ONLY_HOSTS
    if orig:
        return videos.run() or []
    print(">> Luot 1: video NATIVE (token 24h) truoc")
    C.ONLY_HOSTS = [NATIVE_HOST]; f1 = videos.run() or []
    print(">> Luot 2: Loom + YouTube")
    C.ONLY_HOSTS = []; f2 = videos.run() or []
    C.ONLY_HOSTS = orig
    return f1 + f2

def run_videos(until_clean=False, rounds=5, wait=300):
    """Tai video. Neu until_clean: lap lai cho den khi khong con bai NAO co the thu lai
       (vd YouTube bi gioi han toc do -> cho roi tai tiep), toi da `rounds` vong."""
    fails = run_videos_two_pass()
    if not until_clean:
        return fails
    rnd = 1
    while rnd < rounds:
        recover = [f for f in fails if f[1] in RECOVERABLE]
        if not recover:
            print(f">> SACH: khong con bai nao can thu lai (sau {rnd} vong).")
            return fails
        print(f">> Con {len(recover)} bai co the thu lai. Nghi {wait}s roi thu vong {rnd+1}/{rounds}...")
        try:
            time.sleep(wait)
        except KeyboardInterrupt:
            print(">> Da dung vong thu lai."); return fails
        fails = run_videos_two_pass()
        rnd += 1
    left = [f for f in fails if f[1] in RECOVERABLE]
    if left:
        print(f">> Het {rounds} vong, van con {len(left)} bai chua tai duoc (thu lai sau).")
    return fails

def list_courses():
    base = C.BASE / "courses"
    if not base.exists():
        print(f"Chua co thu muc {base}"); return
    items = sorted(p.name for p in base.iterdir() if p.is_dir())
    print(f"Cac khoa duoi {base}:")
    for n in items: print("   -", n)
    if not items: print("   (trong)")

def main():
    K.setup_console()
    ap = argparse.ArgumentParser(description="Skool course archiver")
    ap.add_argument("--course", help="Ten khoa duoi BASE/courses/. Bo trong = dung BASE/SkoolCourse (cu).")
    ap.add_argument("--root", help="Override truc tiep thu muc lam viec (thay cho --course).")
    ap.add_argument("--only", choices=list(STEPS), help="Chi chay 1 buoc.")
    ap.add_argument("--transcribe", action="store_true", help="Chay Whisper transcribe o cuoi.")
    ap.add_argument("--dry-run", action="store_true", help="Video chi liet ke, khong tai.")
    ap.add_argument("--list-courses", action="store_true", help="Liet ke cac khoa roi thoat.")
    ap.add_argument("--skip-preflight", action="store_true", help="Bo qua kiem tra moi truong dau.")
    ap.add_argument("--until-clean", action="store_true", help="Tu thu lai cho den khi tai du (cho neu bi gioi han).")
    ap.add_argument("--rounds", type=int, default=5, help="So vong toi da khi --until-clean (mac dinh 5).")
    ap.add_argument("--round-wait", type=int, default=300, help="Giay nghi giua cac vong --until-clean (mac dinh 300).")
    ap.add_argument("--native-only", action="store_true", help="Chi tai video native Skool (de cuu bai het token).")
    ap.add_argument("--chapter", help="Chi tai 1 chuong (ten chuong da san). Dung cho GUI tai theo chuong.")
    ap.add_argument("--lesson", help="Chi tai 1 bai (duong dan tuong doi vs course root).")
    # override config nhanh
    ap.add_argument("--js-runtime", help="JS runtime cho yt-dlp (node/deno). '' de tat.")
    ap.add_argument("--cookies-file", help="Duong dan cookies.txt cho yt-dlp.")
    ap.add_argument("--cookies-browser", help="Lay cookies tu trinh duyet (firefox).")
    a = ap.parse_args()

    if a.list_courses:
        list_courses(); return

    if a.root:        C.set_root(a.root)
    elif a.course:    C.set_course(a.course)
    if a.dry_run:               C.DRY_RUN = True
    if a.js_runtime is not None: C.JS_RUNTIME = a.js_runtime
    if a.cookies_file:          C.YT_COOKIES_FILE = a.cookies_file
    if a.cookies_browser:       C.YT_COOKIES_BROWSER = a.cookies_browser
    if a.native_only:           C.ONLY_HOSTS = [NATIVE_HOST]
    if a.chapter:               C.ONLY_CHAPTER = a.chapter
    if a.lesson:                C.ONLY_LESSON = a.lesson

    print(f"=== KHOA: {C.COURSE or C.ROOT.name}  ({C.ROOT}) ===\n")

    if a.only:
        if a.only == "videos":
            if a.chapter or a.lesson: folders.run()   # bao dam co folder truoc khi tai chon loc
            run_videos(until_clean=a.until_clean, rounds=a.rounds, wait=a.round_wait)
        else:
            STEPS[a.only]()
        return

    if not a.skip_preflight:
        if preflight.run_checks(check_json=True) > 0:
            print("Dung lai do preflight co loi FAIL. Sua roi chay lai (hoac --skip-preflight de bo qua).")
            return

    folders.run()
    extras.run()                 # resource het han 8h -> lam som
    run_videos(until_clean=a.until_clean, rounds=a.rounds, wait=a.round_wait)  # native 24h truoc, roi loom/youtube
    if a.transcribe: transcribe.run()
    audit.run()
    print("=== HOAN TAT PIPELINE ===")

if __name__ == "__main__":
    main()
