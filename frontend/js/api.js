async function apiFetch(url, options = {}, silent = false) {
  try {
    const response = await fetch(url, options);
    const data = await response.json().catch(() => { throw new Error('服务器返回异常，请检查服务是否运行'); });
    if (!response.ok || data.status !== 'ok') {
      const error = new Error(data.message || '请求失败'); error.code = response.status;
      if (response.status === 403) localStorage.removeItem('token');
      throw error;
    }
    return data;
  } catch(error) { if (!silent) showError(error.message); throw error; }
}
async function apiPost(url, body) {
  for (let attempt = 0; attempt < 2; attempt++) {
    const token = await ensureToken();
    try { return await apiFetch(url, {method:'POST',headers:{'Content-Type':'application/json','X-Token':token},body:JSON.stringify(body)}, true); }
    catch(error) { if (error.code !== 403 || attempt) { showError(error.message); throw error; } }
  }
}

async function apiAuthedGet(url) {
  for (let attempt = 0; attempt < 2; attempt++) {
    const token = await ensureToken();
    try { return await apiFetch(url, {headers:{'X-Token':token}}, true); }
    catch(error) { if (error.code !== 403 || attempt) { showError(error.message); throw error; } }
  }
}
