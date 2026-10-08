let toastTimer;
function showError(message) {
  let box = document.getElementById('error-box');
  if (!box) { box = document.createElement('div'); box.id = 'error-box'; box.setAttribute('role', 'status'); document.body.append(box); }
  box.textContent = message; box.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => box.hidden = true, 6000);
}
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function formatSize(bytes) { return bytes >= 1048576 ? (bytes / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round((bytes || 0) / 1024)) + ' KB'; }
function statusText(ts) {
  if (!ts) return '待翻译';
  return ({completed:'已翻译', pending:'排队中', running:'翻译中 ' + (ts.progress || 0) + '%', failed:'翻译未完成 · 可重试',partial:'部分已翻译',paused:'已暂停 · 可继续'})[ts.status] || '待翻译';
}
function downloadText(name, text) {
  const url = URL.createObjectURL(new Blob([text], {type:'text/markdown;charset=utf-8'}));
  const a = el('a'); a.href = url; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
document.querySelectorAll('button[data-theme]').forEach(button => button.onclick = () => {
  const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = theme; localStorage.setItem('yiread-theme', theme);
});
let settingsDialog;
let providerPicker;
async function openSettings() {
  if (!settingsDialog) {
    settingsDialog = el('dialog');
    settingsDialog.innerHTML = `<div class="dialog-heading"><div><h2 id="settings-title">翻译设置</h2><p class="settings-note">连接你自己的 OpenAI 兼容服务</p></div><button type="button" id="close-settings" class="quiet" aria-label="关闭设置">✕</button></div>
    <form class="settings-form"><label>翻译服务商<select id="provider-select" aria-label="翻译服务商"></select></label><div id="provider-help" class="provider-help"></div><label>翻译模型<select id="model-select" aria-label="翻译模型"></select></label><label>API 基础地址<input name="base_url" type="url" placeholder="https://api.openai.com/v1" required></label><label id="custom-model-label">自定义模型 ID<input name="model" placeholder="填写服务商提供的模型 ID" required></label><label>API 密钥<input name="api_key" type="password" autocomplete="new-password" placeholder="留空保留已保存的密钥"></label><p id="key-change-note" class="settings-note key-change-note" hidden>接口地址已更换，保存时会清除原服务的密钥。请填写新服务对应的 API Key。</p><label>目标语言<select name="target_lang"><option value="zh">简体中文</option><option value="en">English</option><option value="ja">日本語</option></select></label><label><span><input name="batch" type="checkbox" style="width:auto"> 合并小段翻译，减少请求次数</span></label><label>同时翻译批数<select name="concurrency"><option value="1">1（稳妥）</option><option value="2">2（较快，可能限流）</option></select></label><label>合成一室术语表<textarea name="glossary" rows="7" placeholder="每行一条，例如 workup = 后处理"></textarea></label><label><span><input name="aligned" type="checkbox" style="width:auto"> 按原文逐句翻译并保存对应位置</span></label><p class="settings-note">术语表用于之后的翻译与重译，不会自动改变已有译文。逐句翻译直接保存原句位置；请求数会增加，可能触发限流，并减少跨句上下文。</p><label><span><input name="clear_key" type="checkbox" style="width:auto"> 清除已保存密钥</span></label><p class="settings-note">配置保存在本机。密钥不会回显到页面。点击翻译将向此服务发送文献文本，调用费用由服务商收取。</p><div class="settings-result" role="status"></div><div class="dialog-actions"><button type="button" id="test-settings">测试连接</button><button class="primary" type="submit">保存设置</button></div></form>`;
    settingsDialog.setAttribute('aria-labelledby','settings-title'); document.body.append(settingsDialog);
    settingsDialog.querySelector('#close-settings').onclick = () => settingsDialog.close();
    const form = settingsDialog.querySelector('form');
    const result = settingsDialog.querySelector('.settings-result');
    providerPicker = setupProviderPicker(form, settingsDialog);
    async function save() {
      if (!form.reportValidity()) return false;
      const data = Object.fromEntries(new FormData(form)); data.clear_key = form.elements.clear_key.checked; data.aligned=form.elements.aligned.checked; data.batch=form.elements.batch.checked;
      const saved = await apiPost('/api/settings', data); providerPicker.saved(saved.data); form.elements.api_key.value = ''; form.elements.clear_key.checked = false;
      return true;
    }
    form.onsubmit = async event => {
      event.preventDefault(); const button = form.querySelector('[type=submit]'); button.disabled = true;
      try { if (await save()) result.textContent = '设置已保存，可以开始翻译。'; } catch(error) { result.textContent = error.message; } finally { button.disabled = false; }
    };
    settingsDialog.querySelector('#test-settings').onclick = async event => {
      const button = event.currentTarget; button.disabled = true; result.textContent = '正在保存并测试连接…';
      try { if (await save()) { const data = await apiPost('/api/settings/test', {}); result.textContent = '连接成功：' + data.data.translation; } else result.textContent = '请先填写完整配置。'; }
      catch(error) { result.textContent = error.message; } finally { button.disabled = false; }
    };
  }
  settingsDialog.querySelector('.settings-result').textContent = '';
  settingsDialog.showModal();
  try {
    const result = await apiAuthedGet('/api/settings');
    const form = settingsDialog.querySelector('form');
    form.elements.target_lang.value = result.data.target_lang || 'zh';form.elements.glossary.value=result.data.glossary || '';form.elements.aligned.checked=result.data.aligned===true;form.elements.batch.checked=result.data.batch!==false;form.elements.concurrency.value=String(result.data.concurrency || 1);
    providerPicker.load(result.data);
    form.elements.api_key.value = ''; form.elements.clear_key.checked = false;

  } catch(error) { settingsDialog.querySelector('.settings-result').textContent = error.message; }
}
document.querySelectorAll('[data-settings]').forEach(button => button.onclick = openSettings);
