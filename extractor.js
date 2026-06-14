/* ============================================================================
   SKOOL COURSE EXTRACTOR  v1.0
   Dán vào Console (F12).
     • Ở trang /classroom  -> liệt kê tất cả chương + URL
     • Ở 1 trang chương     -> dump chương đó: vid__<Chương>.json + meta__<Chương>.json
   Sang chương khác (sidebar) rồi gõ:  skoolDumpChapter()
   Token native 24h, link file 8h -> chạy archive.py NGAY trong ngày.
   ============================================================================ */
   (function () {
    const GROUP = location.pathname.split('/')[1] || 'aiautomationsbyjack';
    const sleep = ms => new Promise(r => setTimeout(r, ms));
    const ND = () => JSON.parse(document.getElementById('__NEXT_DATA__').textContent);
  
    /* ---------- ProseMirror -> Markdown ---------- */
    function inline(nodes) {
      return (nodes || []).map(n => {
        if (n.type === 'text') {
          let t = n.text || '';
          const mk = (n.marks || []).map(m => m.type);
          if (mk.includes('code')) t = '`' + t + '`';
          if (mk.includes('bold')) t = '**' + t + '**';
          if (mk.includes('italic')) t = '*' + t + '*';
          const lk = (n.marks || []).find(m => m.type === 'link');
          if (lk && lk.attrs && lk.attrs.href) t = '[' + t + '](' + lk.attrs.href + ')';
          return t;
        }
        if (n.type === 'hardBreak') return '  \n';
        return '';
      }).join('');
    }
    function blocks(arr, depth) {
      depth = depth || 0; const out = [];
      for (const b of (arr || [])) {
        const t = b.type;
        if (t === 'paragraph') out.push(inline(b.content));
        else if (t === 'heading') out.push('#'.repeat((b.attrs && b.attrs.level) || 2) + ' ' + inline(b.content));
        else if (t === 'blockquote') out.push('> ' + blocks(b.content, depth).join('\n> '));
        else if (t === 'codeBlock') out.push('```\n' + inline(b.content) + '\n```');
        else if (t === 'bulletList') for (const li of (b.content || [])) out.push('  '.repeat(depth) + '- ' + blocks(li.content, depth + 1).join('\n').trim());
        else if (t === 'orderedList') { let i = (b.attrs && b.attrs.start) || 1; for (const li of (b.content || [])) out.push('  '.repeat(depth) + (i++) + '. ' + blocks(li.content, depth + 1).join('\n').trim()); }
        else if (t === 'listItem') out.push(blocks(b.content, depth).join('\n'));
        else if (t === 'image') out.push('![](' + ((b.attrs && (b.attrs.src || b.attrs.url)) || '') + ')');
        else if (b.content) out.push(blocks(b.content, depth).join('\n'));
      }
      return out;
    }
    function descToMd(desc) {
      if (!desc) return '';
      let s = String(desc);
      if (s.startsWith('[v2]')) { try { return blocks(JSON.parse(s.slice(4)), 0).join('\n\n').replace(/\n{3,}/g, '\n\n').trim(); } catch (e) { return ''; } }
      return s.trim();
    }
  
    /* ---------- resources: parse + resolve file url (api2) ---------- */
    async function resolveResources(raw) {
      let arr = [];
      try { arr = typeof raw === 'string' ? JSON.parse(raw) : (raw || []); } catch (e) { arr = []; }
      const out = [];
      for (const r of (arr || [])) {
        if (r.link) { out.push({ type: 'link', file_name: r.title || r.link, url: r.link }); continue; }
        if (r.file_id) {
          let url = '';
          for (let a = 0; a < 3 && !url; a++) {
            try { const resp = await fetch(`https://api2.skool.com/files/${r.file_id}/download-url?expire=28800`, { method: 'POST', credentials: 'include' }); if (resp.ok) url = (await resp.text()).trim(); } catch (e) {}
            if (!url) await sleep(500 * (a + 1));
          }
          out.push({ type: 'file', file_name: r.file_name || r.title || 'file', url });
        }
      }
      return out;
    }
  
    /* ---------- tree helpers ---------- */
    function collectLeaves(wrappers, trail, acc) {
      acc = acc || [];
      for (const w of (wrappers || [])) {
        const obj = w.course; if (!obj) continue;
        const title = (obj.metadata && obj.metadata.title) || '';
        const kids = w.children || [];
        if (kids.length) collectLeaves(kids, trail.concat([title]), acc);
        else acc.push({ trail: trail.concat([title]), obj });
      }
      return acc;
    }
    function nest(items, setLeaf) {
      const roots = [];
      for (const it of items) {
        let level = roots;
        for (let i = 0; i < it.trail.length; i++) {
          const title = it.trail[i], last = i === it.trail.length - 1;
          let node = level.find(n => n.title === title && (!!n.__c !== last));
          if (!node) { node = { title, children: [] }; if (last) setLeaf(node, it); else node.__c = true; level.push(node); }
          level = node.children;
        }
      }
      return roots;
    }
    function clean(nodes, vid) { for (const n of nodes) { if (n.__c) { delete n.__c; if (vid) n.url = ''; } clean(n.children || [], vid); } return nodes; }
    function sanFile(s) {
      return (s || 'chuong').replace(/[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u2190-\u21FF\u2B00-\u2BFF\u2300-\u23FF\uFE0F\u200D]/gu, '')
        .replace(/[<>:"/\\|?*]/g, '').trim().replace(/\s+/g, '_').replace(/^_+|_+$/g, '') || 'chuong';
    }
    function download(name, obj) {
      const blob = new Blob([JSON.stringify(obj, null, 2)], { type: 'application/json' });
      const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 8000);
    }
  
    /* ---------- liệt kê chương (chạy ở /classroom) ---------- */
    function skoolListChapters() {
      const d = ND(), ac = d.props.pageProps.allCourses || [], grp = d.query.group || GROUP;
      if (!ac.length) { console.warn('[Skool] Khong thay allCourses. Mo trang /classroom roi chay lai.'); return; }
      console.log(`[Skool] ${ac.length} chuong trong "${grp}":`);
      ac.forEach((c, i) => console.log(`  ${String(i + 1).padStart(2, '0')}. ${(c.metadata && c.metadata.title) || c.id}  ->  https://www.skool.com/${grp}/classroom/${c.id}`));
      // Xuat thu tu chuong -> folders.py danh so chuong tu dong cho khoa moi
      download('_chapters.json', ac.map(c => (c.metadata && c.metadata.title) || c.id));
      console.log('   -> _chapters.json da tai ve (dat cung thu muc khoa). Mo tung URL -> dan extractor (hoac skoolDumpChapter()).');
      return ac.map(c => ({ title: c.metadata && c.metadata.title, url: `https://www.skool.com/${grp}/classroom/${c.id}` }));
    }
  
    /* ---------- dump 1 chương ---------- */
    async function dumpChapter() {
      const d = ND(), pp = d.props.pageProps, buildId = d.buildId, cid = d.query.course;
      if (!pp.course || !pp.course.children) { console.error('[Skool] Khong phai trang chuong. Mo 1 chuong trong Classroom roi chay lai.'); return; }
      const chapterTitle = (pp.course.course && pp.course.course.metadata && pp.course.course.metadata.title) || cid;
      const lvs = collectLeaves(pp.course.children, [], []), total = lvs.length;
      const st = window.__skool = { done: false, chapter: chapterTitle, total, i: 0, native: 0, ext: 0, none: 0, file: 0, link: 0, desc: 0, err: 0 };
      console.log(`[Skool] "${chapterTitle}" — ${total} bai. Bat dau...`);
      const vidItems = [], metaItems = [];
      for (const lf of lvs) {
        st.i++;
        const m = lf.obj.metadata || {};
        let url = (m.videoLink || '').trim(), desc = m.desc, resRaw = m.resources, pv = null;
        for (let a = 0; a < 4; a++) {
          try {
            const r = await fetch(`/_next/data/${buildId}/${GROUP}/classroom/${cid}.json?md=${lf.obj.id}&group=${GROUP}&course=${cid}`, { credentials: 'include', headers: { 'x-nextjs-data': '1' } });
            if (r.ok) {
              const j = await r.json(), rpp = j.pageProps || {};
              let lm = null; JSON.stringify(rpp.course, (k, v) => { if (v && typeof v === 'object' && v.id === lf.obj.id && v.metadata) lm = v.metadata; return v; });
              if (lm) { if (lm.desc) desc = lm.desc; if (lm.resources) resRaw = lm.resources; if (!url && (lm.videoLink || '').trim()) url = lm.videoLink.trim(); }
              pv = rpp.video || null; break;
            }
          } catch (e) {}
          if (a === 3) st.err++;
          await sleep(400 * (a + 1));
        }
        if (!url && pv && pv.playbackId && pv.playbackToken) { url = `https://stream.video.skool.com/${pv.playbackId}.m3u8?token=${pv.playbackToken}`; st.native++; }
        else if (url) st.ext++; else st.none++;
        const desc_md = descToMd(desc); if (desc_md) st.desc++;
        const resources = await resolveResources(resRaw);
        st.file += resources.filter(r => r.type === 'file').length;
        st.link += resources.filter(r => r.type === 'link').length;
        vidItems.push({ trail: lf.trail, url });
        metaItems.push({ trail: lf.trail, desc_md, resources });
        if (st.i % 10 === 0) console.log(`  [${st.i}/${total}] native=${st.native} ext=${st.ext} desc=${st.desc} file=${st.file} link=${st.link} err=${st.err}`);
        await sleep(120);
      }
      const vidTree = [{ title: chapterTitle, url: '', children: clean(nest(vidItems, (n, it) => { n.url = it.url; }), true) }];
      const metaTree = [{ title: chapterTitle, children: clean(nest(metaItems, (n, it) => { n.desc_md = it.desc_md; n.resources = it.resources; }), false) }];
      const safe = sanFile(chapterTitle);
      download(`vid__${safe}.json`, vidTree); await sleep(600); download(`meta__${safe}.json`, metaTree);
      st.done = true;
      console.log(`[Skool] XONG "${chapterTitle}": ${total} bai | native=${st.native} ext=${st.ext} text=${st.none} | desc=${st.desc} | file=${st.file} link=${st.link} | err=${st.err}`);
      console.log('   -> vid__ + meta__ da tai ve Downloads. Chuong khac: skoolDumpChapter()');
    }
  
    /* ---------- CLAUDE MODE: dump 1 chương va TRA JSON ve (khong tai file) ----------
       Dung khi Claude lai trinh duyet: Claude goi window.skoolDumpReturn(), nhan {vid,meta}
       roi tu ghi ra courses/<khoa>/. Token native (base64) co the bi lop an toan che -> chuong
       native can dump thu cong; chuong YouTube/Loom/text thi Claude lam tron. */
    async function dumpReturn() {
      const d = ND(), pp = d.props.pageProps, buildId = d.buildId, cid = d.query.course;
      if (!pp.course || !pp.course.children) return { ok: false, err: 'not_chapter' };
      const chapterTitle = (pp.course.course && pp.course.course.metadata && pp.course.course.metadata.title) || cid;
      const lvs = collectLeaves(pp.course.children, [], []), total = lvs.length;
      const vidItems = [], metaItems = []; let native = 0, ext = 0, none = 0;
      for (const lf of lvs) {
        const m = lf.obj.metadata || {};
        let url = (m.videoLink || '').trim(), desc = m.desc, resRaw = m.resources, pv = null;
        for (let a = 0; a < 4; a++) {
          try {
            const r = await fetch(`/_next/data/${buildId}/${GROUP}/classroom/${cid}.json?md=${lf.obj.id}&group=${GROUP}&course=${cid}`, { credentials: 'include', headers: { 'x-nextjs-data': '1' } });
            if (r.ok) { const j = await r.json(), rpp = j.pageProps || {}; let lm = null; JSON.stringify(rpp.course, (k, v) => { if (v && typeof v === 'object' && v.id === lf.obj.id && v.metadata) lm = v.metadata; return v; }); if (lm) { if (lm.desc) desc = lm.desc; if (lm.resources) resRaw = lm.resources; if (!url && (lm.videoLink || '').trim()) url = lm.videoLink.trim(); } pv = rpp.video || null; break; }
          } catch (e) {}
          await sleep(400 * (a + 1));
        }
        if (!url && pv && pv.playbackId && pv.playbackToken) { url = `https://stream.video.skool.com/${pv.playbackId}.m3u8?token=${pv.playbackToken}`; native++; } else if (url) ext++; else none++;
        const desc_md = descToMd(desc); const resources = await resolveResources(resRaw);
        vidItems.push({ trail: lf.trail, url }); metaItems.push({ trail: lf.trail, desc_md, resources });
        await sleep(120);
      }
      const vidTree = [{ title: chapterTitle, url: '', children: clean(nest(vidItems, (n, it) => { n.url = it.url; }), true) }];
      const metaTree = [{ title: chapterTitle, children: clean(nest(metaItems, (n, it) => { n.desc_md = it.desc_md; n.resources = it.resources; }), false) }];
      return { ok: true, chapter: chapterTitle, safe: sanFile(chapterTitle), total, native, ext, none, vid: JSON.stringify(vidTree), meta: JSON.stringify(metaTree) };
    }

    window.skoolDumpChapter = dumpChapter;
    window.skoolDumpReturn = dumpReturn;
    window.skoolListChapters = skoolListChapters;
  
    /* ---------- tự nhận trang ---------- */
    try {
      const d = ND();
      if (d.query && d.query.course && d.props.pageProps.course && d.props.pageProps.course.children) dumpChapter();
      else if (d.props.pageProps.allCourses) skoolListChapters();
      else console.warn('[Skool] Mo 1 trang Classroom hoac trang chuong roi dan lai.');
    } catch (e) { console.error('[Skool] Loi doc trang:', e.message); }
  })();