/* Website-only GA4. No game, device, audio, form or vote data is read. */
(() => {
  'use strict';
  const tag = document.currentScript;
  const id = tag?.dataset.measurementId;
  const host = tag?.dataset.analyticsHost;
  if (!/^G-[A-Z0-9]+$/.test(id || '') || !host) return;
  const key = 'dglab-analytics-consent-v1';
  const production = location.protocol === 'https:' && location.hostname === host;
  const blocked = navigator.globalPrivacyControl === true || navigator.doNotTrack === '1';
  const maxAge = 180 * 86400000;
  const copy = {
    zh: ['网站访问统计', '允许 Google Analytics 统计访问、下载和站点跳转。不会读取投票建议、配对信息、游戏数据或音频。可随时在页脚撤回。', '允许统计', '拒绝统计', '统计与隐私', '关闭', '已允许网站统计', '网站统计已关闭', '浏览器隐私信号已关闭统计'],
    en: ['Website analytics', 'Allow Google Analytics to measure visits, downloads and site navigation. No suggestions, pairing details, game data or audio are read. Withdraw anytime in the footer.', 'Allow analytics', 'Reject analytics', 'Analytics & privacy', 'Close', 'Website analytics allowed', 'Website analytics off', 'Analytics disabled by your browser privacy signal'],
    ja: ['サイト利用統計', 'Google Analytics でアクセス、ダウンロード、サイト移動を計測します。提案内容、ペアリング情報、ゲームデータ、音声は読み取りません。フッターからいつでも撤回できます。', '統計を許可', '統計を拒否', '統計とプライバシー', '閉じる', 'サイト統計を許可済み', 'サイト統計はオフ', 'ブラウザーのプライバシー設定により統計はオフ']
  };
  let choice = null, started = false;
  try {
    const saved = JSON.parse(localStorage.getItem(key));
    if (saved && ['granted', 'denied'].includes(saved.value) && Date.now() - saved.time < maxAge && saved.time <= Date.now()) choice = saved.value;
  } catch {}
  const locale = () => copy[document.documentElement.lang.split('-')[0]] || copy.en;
  const panel = document.createElement('section');
  panel.className = 'analytics-consent';
  panel.setAttribute('role', 'region');
  const heading = document.createElement('h2');
  const description = document.createElement('p');
  const status = document.createElement('p');
  status.className = 'analytics-status';
  status.setAttribute('role', 'status');
  const actions = document.createElement('div');
  actions.className = 'analytics-actions';
  const allow = document.createElement('button');
  const reject = document.createElement('button');
  const close = document.createElement('button');
  for (const button of [allow, reject, close]) { button.type = 'button'; actions.append(button); }
  panel.append(heading, description, status, actions);
  const preferences = document.createElement('button');
  preferences.type = 'button';
  preferences.className = 'analytics-preferences';
  function render() {
    const c = locale();
    panel.setAttribute('aria-label', c[0]);
    heading.textContent = c[0]; description.textContent = c[1];
    allow.textContent = c[2]; reject.textContent = c[3];
    preferences.textContent = c[4]; close.textContent = c[5];
    allow.disabled = blocked;
    status.textContent = blocked ? c[8] : choice === 'granted' ? c[6] : c[7];
    close.hidden = choice === null && !blocked;
  }
  function track(name, params = {}) {
    if (!started || blocked || choice !== 'granted') return;
    window.gtag('event', name, {send_to: id, ...params});
  }
  function start() {
    if (started || !production || blocked || choice !== 'granted') return;
    started = true;
    window.dataLayer = window.dataLayer || [];
    window.gtag = function () { window.dataLayer.push(arguments); };
    window['ga-disable-' + id] = false;
    window.gtag('consent', 'default', {analytics_storage: 'granted', ad_storage: 'denied', ad_user_data: 'denied', ad_personalization: 'denied'});
    window.gtag('js', new Date());
    // Strip query strings, fragments and referrer paths before any Google tag runs.
    const page = host === 'ricca-dglab.web.app' && /^\/guide(?:\.html)?\/?$/.test(location.pathname) ? 'guide' : 'home';
    let referrer = '';
    try { referrer = new URL(document.referrer).origin + '/'; } catch {}
    window.gtag('config', id, {
      send_page_view: false, allow_google_signals: false, allow_ad_personalization_signals: false,
      page_location: 'https://' + host + (page === 'guide' ? '/guide' : '/'),
      page_referrer: referrer, page_title: host + ' · ' + page,
      cookie_domain: host, cookie_flags: 'SameSite=Lax;Secure', cookie_expires: 15552000,
      linker: {accept_incoming: false}
    });
    const script = document.createElement('script');
    script.async = true;
    script.src = 'https://www.googletagmanager.com/gtag/js?id=' + id;
    document.head.append(script);
    track('page_view', {page_name: page});
  }
  function clearCookies() {
    for (const item of document.cookie.split(';')) {
      const name = item.split('=')[0].trim();
      if (!/^_ga(?:_|$)/.test(name)) continue;
      for (const domain of ['', '; Domain=' + host, '; Domain=.' + host]) {
        document.cookie = name + '=; Max-Age=0; Path=/' + domain + '; SameSite=Lax; Secure';
      }
    }
  }
  function save(value) {
    if (value === 'granted' && blocked) return;
    choice = value;
    try {localStorage.setItem(key, JSON.stringify({value, time: Date.now()}));} catch {}
    if (value === 'denied') {
      window['ga-disable-' + id] = true;
      clearCookies();
      // Unload the tag, including any engagement timers already installed by Google.
      if (started) {location.reload(); return;}
    } else start();
    panel.hidden = true; render(); preferences.focus();
  }
  allow.addEventListener('click', () => save('granted'));
  reject.addEventListener('click', () => save('denied'));
  close.addEventListener('click', () => {panel.hidden = true; preferences.focus();});
  preferences.addEventListener('click', () => {render(); panel.hidden = false; (blocked ? reject : allow).focus();});
  panel.addEventListener('keydown', event => {if (event.key === 'Escape' && choice !== null) {panel.hidden = true; preferences.focus();}});
  window.addEventListener('storage', event => {if (event.key === key) location.reload();});
  document.addEventListener('click', event => {
    const target = event.target.closest?.('a,button');
    if (!target) return;
    const channel = target.dataset.download;
    if (['baidu', 'direct', 'github'].includes(channel) && target.hasAttribute('href') && target.getAttribute('aria-disabled') !== 'true') {
      track('download_' + (channel === 'direct' ? 'cos' : channel), {download_channel: channel === 'direct' ? 'cos' : channel}); return;
    }
    if (target.classList.contains('quick-start-trigger')) {track('quick_start'); return;}
    if (target.tagName !== 'A' || !target.hasAttribute('href')) return;
    const url = new URL(target.href, location.href);
    const games = {'manaka-dglab.web.app':'manaka', 'ricca-dglab.web.app':'ricca', 'dglab-x-game.web.app':'dashboard'};
    if (games[url.hostname] && url.hostname !== host) track('game_navigation', {destination: games[url.hostname]});
    else if (url.hostname === host && /^\/guide(?:\.html)?$/.test(url.pathname)) track('guide_open');
    else if (url.hostname === 'github.com') track('github_open');
    else if (url.hostname === 'x.com' && url.pathname === '/1zhiguo') track('developer_profile');
  }, true);
  new MutationObserver(render).observe(document.documentElement, {attributes:true, attributeFilter:['lang']});
  (document.querySelector('footer') || document.body).append(preferences);
  document.body.append(panel);
  panel.hidden = choice !== null || blocked;
  render(); start();
})();
