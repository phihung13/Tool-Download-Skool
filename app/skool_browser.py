"""
Dieu khien trinh duyet (Playwright) cho GUI: nguoi dung dang nhap Skool 1 lan,
app doc danh sach chuong, va dump (tra JSON ve Python -> ghi ra courses/<khoa>/).
Chay trong 1 LUONG rieng (Playwright sync API phai o cung 1 thread).
Giao tiep voi GUI qua 2 hang doi: cmd_q (GUI->worker), evt_q (worker->GUI).
"""
import json, re, threading, queue
from pathlib import Path

HERE = Path(__file__).resolve().parent
USER_DATA = HERE / ".browser"          # luu dang nhap (persistent) - .gitignore

def san_file(s):
    s = re.sub(r"[\U0001F000-\U0001FAFF\U00002600-\U000027BF←-⇿⬀-⯿⌀-⏿️‍]", "", s or "")
    s = re.sub(r'[<>:"/\\|?*]', "", s).strip()
    s = re.sub(r"\s+", "_", s).strip("_")
    return s or "chuong"

# JS: doc danh sach chuong tu trang classroom
JS_LIST = r"""() => {
  const el = document.getElementById('__NEXT_DATA__'); if (!el) return null;
  const d = JSON.parse(el.textContent); const pp = d.props.pageProps || {};
  const ac = pp.allCourses; if (!ac) return null;
  const grp = (d.query && d.query.group) || location.pathname.split('/')[1];
  return { group: grp, loggedIn: true,
    chapters: ac.map((c, i) => ({ i: i+1, id: c.id, title: (c.metadata && c.metadata.title) || c.id })) };
}"""

# JS: dump 1 chuong (dang o trang chuong) -> tra ve {vid, meta} (stringified)
JS_DUMP = r"""async () => {
  const GROUP = location.pathname.split('/')[1];
  const d = JSON.parse(document.getElementById('__NEXT_DATA__').textContent);
  const pp = d.props.pageProps, buildId = d.buildId, cid = d.query.course;
  if (!pp.course || !pp.course.children) return { ok:false, err:'not_chapter' };
  const sleep = ms => new Promise(r=>setTimeout(r,ms));
  function inline(ns){return (ns||[]).map(n=>{if(n.type==='text'){let t=n.text||'';const mk=(n.marks||[]).map(m=>m.type);if(mk.includes('code'))t='`'+t+'`';if(mk.includes('bold'))t='**'+t+'**';if(mk.includes('italic'))t='*'+t+'*';const lk=(n.marks||[]).find(m=>m.type==='link');if(lk&&lk.attrs&&lk.attrs.href)t='['+t+']('+lk.attrs.href+')';return t;}if(n.type==='hardBreak')return '  \n';return '';}).join('');}
  function blocks(a,dep){dep=dep||0;const o=[];for(const b of (a||[])){const t=b.type;if(t==='paragraph')o.push(inline(b.content));else if(t==='heading')o.push('#'.repeat((b.attrs&&b.attrs.level)||2)+' '+inline(b.content));else if(t==='blockquote')o.push('> '+blocks(b.content,dep).join('\n> '));else if(t==='codeBlock')o.push('```\n'+inline(b.content)+'\n```');else if(t==='bulletList')for(const li of (b.content||[]))o.push('  '.repeat(dep)+'- '+blocks(li.content,dep+1).join('\n').trim());else if(t==='orderedList'){let i=(b.attrs&&b.attrs.start)||1;for(const li of (b.content||[]))o.push('  '.repeat(dep)+(i++)+'. '+blocks(li.content,dep+1).join('\n').trim());}else if(t==='listItem')o.push(blocks(b.content,dep).join('\n'));else if(t==='image')o.push('![]('+((b.attrs&&(b.attrs.src||b.attrs.url))||'')+')');else if(b.content)o.push(blocks(b.content,dep).join('\n'));}return o;}
  function descToMd(x){if(!x)return '';let s=String(x);if(s.startsWith('[v2]')){try{return blocks(JSON.parse(s.slice(4)),0).join('\n\n').replace(/\n{3,}/g,'\n\n').trim();}catch(e){return '';}}return s.trim();}
  async function resolveRes(raw){let arr=[];try{arr=typeof raw==='string'?JSON.parse(raw):(raw||[]);}catch(e){arr=[];}const out=[];for(const r of (arr||[])){if(r.link){out.push({type:'link',file_name:r.title||r.link,url:r.link});continue;}if(r.file_id){let u='';for(let a=0;a<3&&!u;a++){try{const rs=await fetch('https://api2.skool.com/files/'+r.file_id+'/download-url?expire=28800',{method:'POST',credentials:'include'});if(rs.ok)u=(await rs.text()).trim();}catch(e){}if(!u)await sleep(500*(a+1));}out.push({type:'file',file_name:r.file_name||r.title||'file',url:u});}}return out;}
  function leaves(ws,tr,acc){acc=acc||[];for(const w of (ws||[])){const o=w.course;if(!o)continue;const t=(o.metadata&&o.metadata.title)||'';const k=w.children||[];if(k.length)leaves(k,tr.concat([t]),acc);else acc.push({trail:tr.concat([t]),obj:o});}return acc;}
  function nest(items,setLeaf){const roots=[];for(const it of items){let lv=roots;for(let i=0;i<it.trail.length;i++){const ti=it.trail[i],last=i===it.trail.length-1;let nd=lv.find(n=>n.title===ti&&(!!n.__c!==last));if(!nd){nd={title:ti,children:[]};if(last)setLeaf(nd,it);else nd.__c=true;lv.push(nd);}lv=nd.children;}}return roots;}
  function clean(ns,vid){for(const n of ns){if(n.__c){delete n.__c;if(vid)n.url='';}clean(n.children||[],vid);}return ns;}
  const title=(pp.course.course&&pp.course.course.metadata&&pp.course.course.metadata.title)||cid;
  const lvs=leaves(pp.course.children,[],[]); let native=0,ext=0,none=0;
  const vi=[],mi=[];
  for(const lf of lvs){const m=lf.obj.metadata||{};let url=(m.videoLink||'').trim(),desc=m.desc,resRaw=m.resources,pv=null;
    for(let a=0;a<4;a++){try{const r=await fetch('/_next/data/'+buildId+'/'+GROUP+'/classroom/'+cid+'.json?md='+lf.obj.id+'&group='+GROUP+'&course='+cid,{credentials:'include',headers:{'x-nextjs-data':'1'}});if(r.ok){const j=await r.json(),rpp=j.pageProps||{};let lm=null;JSON.stringify(rpp.course,(k,v)=>{if(v&&typeof v==='object'&&v.id===lf.obj.id&&v.metadata)lm=v.metadata;return v;});if(lm){if(lm.desc)desc=lm.desc;if(lm.resources)resRaw=lm.resources;if(!url&&(lm.videoLink||'').trim())url=lm.videoLink.trim();}pv=rpp.video||null;break;}}catch(e){}await sleep(350*(a+1));}
    if(!url&&pv&&pv.playbackId&&pv.playbackToken){url='https://stream.video.skool.com/'+pv.playbackId+'.m3u8?token='+pv.playbackToken;native++;}else if(url)ext++;else none++;
    const dm=descToMd(desc);const res=await resolveRes(resRaw);
    vi.push({trail:lf.trail,url});mi.push({trail:lf.trail,desc_md:dm,resources:res});await sleep(80);}
  const vidTree=[{title,url:'',children:clean(nest(vi,(n,it)=>{n.url=it.url;}),true)}];
  const metaTree=[{title,children:clean(nest(mi,(n,it)=>{n.desc_md=it.desc_md;n.resources=it.resources;}),false)}];
  return {ok:true,chapter:title,total:lvs.length,native,ext,none,vid:JSON.stringify(vidTree),meta:JSON.stringify(metaTree)};
}"""


class SkoolBrowser:
    def __init__(self):
        self.cmd_q = queue.Queue()
        self.evt_q = queue.Queue()
        self.group = None
        self._p = None
        self._ctx = None
        self._t = threading.Thread(target=self._run, daemon=True)
        self._t.start()

    def emit(self, **kw): self.evt_q.put(kw)
    def send(self, **kw): self.cmd_q.put(kw)
    def open(self):  self.send(type="open")
    def list_chapters(self): self.send(type="list")
    def dump(self, chapters, out_dir): self.send(type="dump", chapters=chapters, out_dir=str(out_dir))
    def quit(self): self.send(type="quit")

    def _run(self):
        try:
            from playwright.sync_api import sync_playwright
        except Exception as e:
            self.emit(type="error", msg=f"Chua cai Playwright: {e}"); return
        try:
            with sync_playwright() as p:
                self._p = p
                self.emit(type="ready")
                while True:
                    cmd = self.cmd_q.get()
                    if cmd.get("type") == "quit":
                        break
                    try:
                        self._handle(cmd)
                    except Exception as e:
                        self.emit(type="error", msg=str(e))
                if self._ctx is not None:
                    try: self._ctx.close()
                    except Exception: pass
        except Exception as e:
            self.emit(type="error", msg=f"Loi trinh duyet: {e}")

    def _ensure_ctx(self):
        """Tao (hoac tao lai neu da bi dong) persistent context."""
        if self._ctx is None:
            self._ctx = self._p.chromium.launch_persistent_context(
                str(USER_DATA), headless=False,
                viewport={"width": 1200, "height": 800},
                args=["--disable-blink-features=AutomationControlled"])
        return self._ctx

    def _live_page(self):
        """Luon tra ve 1 trang dang song (uu tien skool.com). Tu mo lai neu browser bi dong."""
        for _ in range(2):
            ctx = self._ensure_ctx()
            try:
                pages = [pg for pg in ctx.pages if not pg.is_closed()]
                if not pages:
                    return ctx.new_page()
                for pg in pages:
                    try:
                        if "skool.com" in (pg.url or ""):
                            return pg
                    except Exception:
                        pass
                return pages[-1]
            except Exception:
                self._ctx = None   # browser da dong -> tao lai vong sau
        raise RuntimeError("Khong mo duoc trang (trinh duyet co the da dong).")

    def _handle(self, cmd):
        page = self._live_page()
        t = cmd["type"]
        if t == "open":
            self.emit(type="log", msg="Mo Skool... Hay dang nhap va mo trang Classroom cua khoa ban muon.")
            if "skool.com" not in (page.url or ""):
                page.goto("https://www.skool.com/", wait_until="domcontentloaded")
            try: page.bring_to_front()
            except Exception: pass
            self.emit(type="opened")
        elif t == "list":
            data = page.evaluate(JS_LIST)
            if not data:
                self.emit(type="need_classroom",
                          msg="Chua thay danh sach chuong. Hay mo trang Classroom cua khoa (URL .../classroom) roi thu lai.")
                return
            self.group = data["group"]
            self.emit(type="chapters", group=data["group"], chapters=data["chapters"])
        elif t == "dump":
            chapters = cmd["chapters"]; out = Path(cmd["out_dir"])
            out.mkdir(parents=True, exist_ok=True)
            (out / "_chapters.json").write_text(
                json.dumps([c["title"] for c in chapters], ensure_ascii=False, indent=2), encoding="utf-8")
            grp = self.group or page.url.split("/")[3]
            ok = 0
            for idx, c in enumerate(chapters, 1):
                self.emit(type="dump_progress", i=idx, n=len(chapters), title=c["title"])
                try:
                    page = self._live_page()
                    page.goto(f"https://www.skool.com/{grp}/classroom/{c['id']}",
                              wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_function(
                        "() => { try { const d=JSON.parse(document.getElementById('__NEXT_DATA__').textContent);"
                        " return !!(d.props.pageProps.course && d.props.pageProps.course.children);} catch(e){return false;} }",
                        timeout=25000)
                    page.set_default_timeout(150000)   # chuong nhieu bai can lau
                    res = page.evaluate(JS_DUMP)
                    if not res or not res.get("ok"):
                        self.emit(type="log", msg=f"  [bo qua] {c['title']}: {res.get('err') if res else 'loi'}"); continue
                    safe = san_file(res["chapter"])
                    (out / f"vid__{safe}.json").write_text(res["vid"], encoding="utf-8")
                    (out / f"meta__{safe}.json").write_text(res["meta"], encoding="utf-8")
                    ok += 1
                    self.emit(type="log",
                              msg=f"  [OK] {res['chapter']}: {res['total']} bai (native={res['native']} ext={res['ext']} text={res['none']})")
                except Exception as e:
                    self.emit(type="log", msg=f"  [LOI] {c['title']}: {e}")
            self.emit(type="dumped", ok=ok, total=len(chapters), out_dir=str(out))
