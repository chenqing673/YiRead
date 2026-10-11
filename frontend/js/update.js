// Updates run only after an explicit user action.
document.querySelectorAll('[data-update]').forEach(button => button.onclick = async () => {
  const dialog = el('dialog', 'yiread-help');
  const heading = el('h2', '', '检查更新');
  const message = el('p', '', '正在检查 GitHub 最新正式版本…');
  const notes = el('pre'); notes.style.whiteSpace = 'pre-wrap';
  const actions = el('div');
  const close = el('button', 'quiet', '关闭'); close.onclick = () => dialog.close();
  dialog.append(heading, message, notes, actions, close);
  dialog.addEventListener('close', () => dialog.remove());
  document.body.append(dialog); dialog.showModal();
  try {
    const {data} = await apiPost('/api/update/check', {});
    message.textContent = '当前版本 ' + data.current_version + ' · 最新版本 ' + data.latest_version +
      (data.available ? '，发现新版。' : '，当前已是最新版本。');
    notes.textContent = data.notes;
    const page = el('a', 'quiet', '查看 GitHub 发布页面');
    page.href = data.release_url; page.target = '_blank'; page.rel = 'noopener noreferrer'; actions.append(page);
    if (data.available && data.download_url) {
      const download = el('a', 'quiet', '手动下载安装包'); download.href = data.download_url;
      download.style.marginLeft = '12px'; actions.append(download);
    }
    if (data.available && !data.can_install) {
      dialog.append(el('p', 'settings-note', '自动安装仅适用于免安装版，且发布包须提供 SHA256 校验值。可使用手动下载入口升级。'));
    }
    if (data.can_install) {
      dialog.append(el('p', 'settings-note', '更新会关闭并重新启动 YiRead，保留 data 及其他用户文件。请先保存所有页面中的笔记与修订，暂停翻译并等待请求结束。'));
      const confirm = el('input'); confirm.type = 'checkbox';
      const label = el('label'); label.append(confirm, ' 我已保存编辑内容，允许下载后退出并更新');
      const install = el('button', 'primary', '下载并更新（' + formatSize(data.size) + '）');
      install.disabled = true; confirm.onchange = () => install.disabled = !confirm.checked;
      dialog.append(label, install);
      install.onclick = async () => {
        install.disabled = true; confirm.disabled = true;
        try {
          await apiPost('/api/update/install', {});
          const poll = async () => {
            try {
              const {data: state} = await apiAuthedGet('/api/update/status');
              message.textContent = (state.message || '') + (state.status === 'downloading' ? ' ' + state.progress + '%' : '');
              if (state.status === 'failed') {install.disabled = false; confirm.disabled = false; return;}
              setTimeout(poll, 1500);
            } catch (error) {
              message.textContent = '服务已断开，可能正在替换并重新启动。稍后刷新页面；启动失败时查看程序目录 update-result.txt。';
              const refresh = el('button', 'primary', '刷新页面'); refresh.onclick = () => location.reload(); actions.append(refresh);
            }
          };
          poll();
        } catch (error) { message.textContent = error.message; install.disabled = false; confirm.disabled = false; }
      };
    }
  } catch (error) { message.textContent = '检查失败：' + error.message + '。请检查网络或稍后重试。'; }
});
