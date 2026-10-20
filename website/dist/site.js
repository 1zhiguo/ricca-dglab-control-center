(() => {
  'use strict';
  const localized=[...document.querySelectorAll('[data-en]')];
  const originals=new Map(localized.map(node=>[node,node.innerHTML]));
  let language='zh';
  try { language=localStorage.getItem('ricca-site-language')==='en'?'en':'zh'; } catch {}
  function applyRelease() {
    const release=window.RICCA_RELEASE||{urls:{}};
    const names={baidu:['百度网盘','Baidu Netdisk'],direct:['高速直链','Direct download'],github:['GitHub','GitHub']};
    document.querySelectorAll('[data-download]').forEach(link=>{
      const url=release.urls?.[link.dataset.download];
      const valid=typeof url==='string'&&/^https:\/\//.test(url);
      const label=link.dataset.channelLabel?names[link.dataset.download][language==='en'?1:0]+' · ':'';
      if(valid) {link.href=url;link.removeAttribute('aria-disabled');link.textContent=label+(language==='en'?'Open download ↗':'前往下载 ↗');link.target='_blank';link.rel='noopener noreferrer';}
      else {link.removeAttribute('href');link.setAttribute('aria-disabled','true');link.textContent=label+(language==='en'?'Not published yet':'尚未发布');}
    });
  }
  function setLanguage(next) {
    language=next;document.documentElement.lang=next==='en'?'en':'zh-CN';
    localized.forEach(node=>{node.innerHTML=next==='en'?node.dataset.en:originals.get(node);});
    document.querySelectorAll('.language').forEach(button=>{button.textContent=next==='en'?'中文':'English';button.setAttribute('aria-label',next==='en'?'切换中文':'Switch to English');});
    applyRelease();
    try {localStorage.setItem('ricca-site-language',next);} catch {}
  }
  document.querySelectorAll('.language').forEach(button=>button.addEventListener('click',()=>setLanguage(language==='en'?'zh':'en')));
  const menu=document.querySelector('.download-menu');
  if(menu) {
    const trigger=menu.querySelector('.download-trigger'),panel=menu.querySelector('.download-source-menu');
    const toggle=open=>{panel.hidden=!open;menu.classList.toggle('is-open',open);trigger.setAttribute('aria-expanded',String(open));};
    trigger.addEventListener('click',()=>toggle(panel.hidden));
    document.addEventListener('click',event=>{if(!menu.contains(event.target))toggle(false);});
    menu.addEventListener('keydown',event=>{
      if(event.key==='Escape'){toggle(false);trigger.focus();}
      if(event.key==='ArrowDown'){event.preventDefault();toggle(true);panel.querySelector('a[href]')?.focus();}
    });
    panel.querySelectorAll('a').forEach(link=>link.addEventListener('click',()=>toggle(false)));
  }
  const lightbox=document.querySelector('#lightbox');
  document.querySelectorAll('[data-screenshot]').forEach(link=>link.addEventListener('click',event=>{
    if(!lightbox)return;
    event.preventDefault();
    const image=lightbox.querySelector('img');image.src=link.href;image.alt=link.querySelector('img').alt;lightbox.showModal();
  }));
  lightbox?.addEventListener('click',event=>{if(event.target===lightbox){const b=lightbox.getBoundingClientRect();if(event.clientX<b.left||event.clientX>b.right||event.clientY<b.top||event.clientY>b.bottom)lightbox.close();}});
  document.querySelectorAll('[data-copy]').forEach(button=>button.addEventListener('click',async()=>{
    const status=button.parentElement.querySelector('.copy-status');
    try {await navigator.clipboard.writeText(document.querySelector(button.dataset.copy).textContent.trim());status.textContent=language==='en'?'Copied.':'已复制。';}
    catch {status.textContent=language==='en'?'Clipboard unavailable. Select and copy the value above.':'剪贴板不可用，请选中上方数值手动复制。';}
  }));
  setLanguage(language);
})();
