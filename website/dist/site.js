(() => {
  'use strict';
  const localized=[...document.querySelectorAll('[data-en]')];
  const originals=new Map(localized.map(node=>[node,node.innerHTML]));
  const locales=['zh','en','ja'];
  const ja=window.RICCA_JA||{};
  let language='zh';
  try {
    const requested=new URLSearchParams(location.search).get('lang');
    const saved=localStorage.getItem('ricca-site-language');
    language=locales.includes(requested)?requested:locales.includes(saved)?saved:'zh';
  } catch {}
  const choose=(zh,en,jp)=>({zh,en,ja:jp})[language];
  function applyRelease() {
    const release=window.RICCA_RELEASE||{urls:{}};
    document.querySelectorAll('[data-release-sha]').forEach(node=>{
      node.textContent=release.sha256||choose('校验值待生成','Checksum pending','チェックサム準備中');
    });
    document.querySelectorAll('[data-release-version]').forEach(node=>{node.textContent=release.version||'—';});
    document.querySelectorAll('[data-baidu-code]').forEach(node=>{node.textContent=release.baiduCode||'—';});
    document.querySelectorAll('.baidu-code').forEach(node=>{node.hidden=!release.baiduCode;});
    const names={baidu:{zh:'百度网盘',en:'Baidu Netdisk',ja:'百度網盤'},direct:{zh:'高速直链',en:'Direct download',ja:'直接ダウンロード'},github:{zh:'GitHub',en:'GitHub',ja:'GitHub'}};
    document.querySelectorAll('[data-download]').forEach(link=>{
      const url=release.urls?.[link.dataset.download];
      const valid=typeof url==='string'&&/^https:\/\//.test(url);
      const label=link.dataset.channelLabel?names[link.dataset.download][language]+' · ':'';
      if(valid) {link.href=url;link.removeAttribute('aria-disabled');link.textContent=label+(link.dataset.download==='baidu'?choose('前往网盘 ↗','Open Netdisk ↗','網盤を開く ↗'):choose('下载 ZIP ↗','Download ZIP ↗','ZIP をダウンロード ↗'));link.target='_blank';link.rel='noopener noreferrer';}
      else {link.removeAttribute('href');link.setAttribute('aria-disabled','true');link.textContent=label+choose('稍后开放','Coming later','後日公開');}
    });
  }
  const isGuide=!!document.querySelector('.guide-layout');
  const description=document.querySelector('meta[name="description"]');
  const originalDescription=description?.content;
  const imageDescriptions=new Map([...document.querySelectorAll('img[alt]')].map(node=>[node,node.alt]));
  const altCopies={
    "Guoguo's X avatar":['果果的 X 头像',"Guoguo's X avatar",'果果の X アバター'],
    'QQ community QR code':['QQ群二维码','QQ community QR code','QQ 交流グループの QR コード'],
    "Guoguo's reward code":['果果的赞赏码',"Guoguo's reward code",'果果の応援用 QR コード'],
    'DG-LAB 图标':['DG-LAB 图标','DG-LAB icon','DG-LAB アイコン'],
    'Ricca 插件图标':['Ricca 插件图标','Ricca app icon','Ricca アプリアイコン'],
    'Ricca overview, HP and capture progress':['Ricca 总览、HP 与捕获进度','Ricca overview, HP and capture progress','Ricca 概要・HP・拘束進捗'],
    'Ricca independent channel strategies':['Ricca 独立通道策略','Ricca independent channel strategies','Ricca 独立チャンネル設定'],
    'Ricca 16-point waveform editor':['Ricca 16 点波形编辑器','Ricca 16-point waveform editor','Ricca 16点波形エディター'],
    'Optional Ricca audio empathy':['Ricca 可选音频共感','Optional Ricca audio empathy','Ricca 任意の音声同期'],
    'Story waveform playlist':['剧情波形队列','Story waveform playlist','シナリオ波形キュー'],
    'Custom global emergency hotkey':['自定义全局急停键','Custom global emergency hotkey','グローバル緊急停止キー設定'],
    'Expanded Ricca application screenshot':['Ricca 软件截图放大图','Expanded Ricca application screenshot','Ricca ソフトウェア画面の拡大表示'],
    'DG-LAB mobile device page':['DG-LAB 手机设备页','DG-LAB mobile device page','DG-LAB スマートフォンのデバイス画面'],
    'DG-LAB Socket initialization':['DG-LAB Socket 初始化','DG-LAB Socket initialization','DG-LAB Socket 初期化'],
    'DG-LAB server connection':['DG-LAB 服务连接','DG-LAB server connection','DG-LAB サーバー接続'],
    'DG-LAB QR scanner':['DG-LAB 二维码扫描','DG-LAB QR scanner','DG-LAB QR スキャナー']
  };
  function setLanguage(next) {
    language=locales.includes(next)?next:'zh';
    document.documentElement.lang={zh:'zh-CN',en:'en',ja:'ja'}[language];
    localized.forEach(node=>{node.innerHTML=language==='zh'?originals.get(node):language==='ja'?(ja[node.dataset.en]||node.dataset.en):node.dataset.en;});
    imageDescriptions.forEach((original,node)=>{if(altCopies[original])node.alt=choose(...altCopies[original]);});
    document.querySelectorAll('.language').forEach(select=>{select.value=language;});
    document.querySelectorAll('.copy-status').forEach(node=>{node.textContent='';});
    document.querySelector('nav')?.setAttribute('aria-label',choose('主导航','Main navigation','メインナビゲーション'));
    document.querySelector('.guide-nav')?.setAttribute('aria-label',choose('指南目录','Guide contents','ガイド目次'));
    document.title=isGuide?choose('连接与使用指南 · Ricca × DG-LAB','Guide · Ricca × DG-LAB','使い方 · Ricca × DG-LAB'):choose('Ricca × DG-LAB 控制中心','Ricca × DG-LAB Control Center','Ricca × DG-LAB コントロールセンター');
    if(description) description.content=language==='zh'?originalDescription:choose('', 'Ricca x DG-LAB 1.1.0: V3/V4 Coyote and Opossum support, independent workbenches, manual control and adjustable HUD.', 'Ricca x DG-LAB 1.1.0：V3/V4・郊狼とオポッサム、独立設定、手動操作、カスタム HUD。');
    applyRelease();
    try {localStorage.setItem('ricca-site-language',language);} catch {}
  }
  document.querySelectorAll('.language').forEach(select=>select.addEventListener('change',()=>{
    setLanguage(select.value);
    const url=new URL(location.href);
    if(url.searchParams.has('lang')){url.searchParams.set('lang',language);history.replaceState(null,'',url);}
  }));
  const quickStart=document.querySelector('#quick-start');
  document.querySelector('.quick-start-trigger')?.addEventListener('click',()=>{
    if(quickStart&&!quickStart.open)quickStart.showModal();
  });
  quickStart?.querySelector('.quick-start-close')?.addEventListener('click',()=>quickStart.close());
  quickStart?.addEventListener('click',event=>{
    if(event.target!==quickStart)return;
    const b=quickStart.getBoundingClientRect();
    if(event.clientX<b.left||event.clientX>b.right||event.clientY<b.top||event.clientY>b.bottom)quickStart.close();
  });
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
    try {await navigator.clipboard.writeText(document.querySelector(button.dataset.copy).textContent.trim());status.textContent=choose('已复制。','Copied.','コピーしました。');}
    catch {status.textContent=choose('剪贴板不可用，请选中上方数值手动复制。','Clipboard unavailable. Select and copy the value above.','コピーできません。上の値を選択して手動でコピーしてください。');}
  }));
  setLanguage(language);
})();
