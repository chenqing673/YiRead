// Curated OpenAI-compatible text models. Verified against official documentation on 2026-10-05.
// Availability depends on the provider account; custom model IDs remain supported.
const TRANSLATION_PROVIDERS = [
  {id:'openai', name:'OpenAI', baseUrl:'https://api.openai.com/v1',
   models:[{id:'gpt-4.1-mini',name:'GPT-4.1 mini'},{id:'gpt-4.1',name:'GPT-4.1'}],
   keyUrl:'https://platform.openai.com/api-keys', signupUrl:'https://platform.openai.com/',
   docsUrl:'https://developers.openai.com/api/docs/quickstart',
   note:'API 调用使用独立的 API Key。当前 YiRead 不读取本机 ChatGPT 登录状态。'},
  {id:'deepseek', name:'DeepSeek', baseUrl:'https://api.deepseek.com',
   models:[{id:'deepseek-flash',name:'DeepSeek Flash'},{id:'deepseek-v4-pro',name:'DeepSeek V4 Pro'}],
   keyUrl:'https://platform.deepseek.com/api_keys', signupUrl:'https://platform.deepseek.com/',
   docsUrl:'https://api-docs.deepseek.com/', note:'注册开放平台账号后，在 API Keys 页面创建密钥。'},
  {id:'qwen', name:'通义千问 · 阿里云百炼（北京）', baseUrl:'https://dashscope.aliyuncs.com/compatible-mode/v1',
   quotaLabel:'新用户免费额度', quotaUrl:'https://help.aliyun.com/zh/model-studio/new-free-quota',
   quotaNote:'北京地域指定模型提供新用户试用额度，通常有效期 90 天。各模型额度独立；建议在百炼开启「免费额度用完即停」，到期或耗尽后可能转为付费。',
   models:[{id:'qwen-plus',name:'Qwen Plus'},{id:'qwen3.8-max',name:'Qwen 3.8 Max'}],
   keyUrl:'https://bailian.console.aliyun.com/', signupUrl:'https://account.aliyun.com/register/register.htm',
   docsUrl:'https://help.aliyun.com/zh/model-studio/get-api-key',
   note:'进入百炼控制台开通服务并创建北京地域 API Key。预填北京兼容地址；使用其他地域或业务空间专属域名时请修改地址，并使用对应地域密钥。'},
  {id:'kimi', name:'Kimi · 月之暗面', baseUrl:'https://api.moonshot.cn/v1',
   models:[{id:'kimi-k2.6',name:'Kimi K2.6'},{id:'kimi-k3',name:'Kimi K3'}],
   keyUrl:'https://platform.kimi.com/console/api-keys', signupUrl:'https://platform.kimi.com/',
   docsUrl:'https://platform.kimi.com/docs/get-api-key', note:'在 Kimi 开放平台注册或登录后，创建 API Key。'},
  {id:'zhipu', name:'智谱 · GLM', baseUrl:'https://open.bigmodel.cn/api/paas/v4',
   models:[{id:'glm-4.7-flash',name:'GLM-4.7 Flash',quotaLabel:'免费模型'}],
   keyUrl:'https://bigmodel.cn/usercenter/proj-mgmt/apikeys', signupUrl:'https://bigmodel.cn/',
   docsUrl:'https://docs.bigmodel.cn/cn/guide/models/free/glm-4.7-flash',
   quotaLabel:'有免费模型', quotaUrl:'https://www.zhipuai.cn/zh/news/148',
   quotaNote:'GLM-4.7-Flash 提供免费 API 调用，仍受账号并发及速率限制。其他 GLM 模型不一定免费。',
   note:'在智谱开放平台创建 API Key；这里使用普通模型 API 地址。'},
  {id:'siliconflow', name:'硅基流动 · SiliconFlow', baseUrl:'https://api.siliconflow.cn/v1',
   models:[{id:'deepseek-ai/DeepSeek-V4-Pro',name:'DeepSeek V4 Pro'},{id:'Qwen/Qwen3.6-27B',name:'Qwen 3.6 27B'}],
   keyUrl:'https://cloud.siliconflow.cn/account/ak', signupUrl:'https://cloud.siliconflow.cn/',
   docsUrl:'https://docs.siliconflow.cn/docs/userguide/quickstart', quotaUrl:'https://siliconflow.cn/pricing',
   note:'预置的两个模型按量计费。合作应用内的免费模型不等同于个人 API Key 免费；可在官方价格页核对当前免费模型或赠送额度，再填写自定义模型 ID。'},
  {id:'gemini', name:'Google · Gemini', baseUrl:'https://generativelanguage.googleapis.com/v1beta/openai',
   models:[{id:'gemini-2.5-flash',name:'Gemini 2.5 Flash',quotaLabel:'有免费层'},{id:'gemini-2.5-flash-lite',name:'Gemini 2.5 Flash-Lite',quotaLabel:'有免费层'}],
   keyUrl:'https://aistudio.google.com/api-keys', signupUrl:'https://aistudio.google.com/',
   docsUrl:'https://ai.google.dev/gemini-api/docs/openai',
   quotaLabel:'有免费层', quotaUrl:'https://ai.google.dev/gemini-api/docs/pricing',
   quotaNote:'指定模型提供受限免费层，账号资格、地区及速率限制以控制台为准。免费层提交的内容可能用于改进产品；未公开研究资料请先确认适用的数据政策。',
   note:'在 Google AI Studio 获取 Gemini API Key。需能访问 Google API，付费层按对应价格计费。'},
  {id:'groq', name:'Groq', baseUrl:'https://api.groq.com/openai/v1',
   models:[{id:'openai/gpt-oss-120b',name:'GPT OSS 120B',quotaLabel:'有免费层'},{id:'qwen/qwen3.8-27b',name:'Qwen 3.8 27B',quotaLabel:'有免费层'}],
   keyUrl:'https://console.groq.com/keys', signupUrl:'https://console.groq.com/',
   docsUrl:'https://console.groq.com/docs/openai',
   quotaLabel:'有免费层', quotaUrl:'https://console.groq.com/docs/rate-limits',
   quotaNote:'Free Plan 有每分钟及每日请求 / Token 限额。长文献逐段翻译可能触发限流，具体剩余额度请查看账号控制台；升级后按付费方案计费。',
   note:'在 Groq Console 创建 API Key，模型 ID 必须包含完整的命名空间。'},
  {id:'openrouter', name:'OpenRouter', baseUrl:'https://openrouter.ai/api/v1',
   models:[{id:'openrouter/free',name:'免费模型自动路由',quotaLabel:'免费模型'}],
   keyUrl:'https://openrouter.ai/settings/keys', signupUrl:'https://openrouter.ai/',
   docsUrl:'https://openrouter.ai/docs/quickstart',
   quotaLabel:'有免费模型', quotaUrl:'https://openrouter.ai/docs/guides/routing/model-variants/free',
   quotaNote:'免费路由及 :free 模型有请求限额和可用性限制。自动路由可能在不同段落使用不同模型，术语一致性可能变化；需要固定模型可填写官方提供的 :free 模型 ID。',
   note:'在 OpenRouter 创建 API Key。免费路由只选择可用的免费模型；手动选择其他模型时请核对价格。'},
  {id:'mistral', name:'Mistral AI', baseUrl:'https://api.mistral.ai/v1',
   models:[{id:'mistral-small-latest',name:'Mistral Small · 最新版'}],
   keyUrl:'https://console.mistral.ai/', signupUrl:'https://console.mistral.ai/',
   docsUrl:'https://docs.mistral.ai/getting-started/quickstarts/studio/activate-and-generate-api-key',
   quotaLabel:'免费试用层', quotaUrl:'https://help.mistral.ai/en/articles/698531-why-am-i-hitting-api-rate-limits-and-how-do-i-increase-them',
   quotaNote:'Studio 默认提供 Free mode，无需信用卡，适合评估和试用，有用量与速率限制。请确认账号仍处于免费模式；付费模式采用对应计费规则。',
   note:'在 Studio 控制台左侧「API Keys」创建密钥。latest 模型别名会随服务商更新。'},
  {id:'custom', name:'自定义 OpenAI 兼容服务 / 本地模型', baseUrl:'', models:[],
   note:'填写服务提供的 API 基础地址和模型 ID。本地无鉴权服务可留空密钥；API Key 请向你选择的服务商获取。'}
];
function normalizedEndpoint(value) { return String(value || '').trim().replace(/\/+$/, ''); }
function providerForEndpoint(value) {
  return TRANSLATION_PROVIDERS.find(provider => provider.baseUrl && normalizedEndpoint(provider.baseUrl) === normalizedEndpoint(value)) || TRANSLATION_PROVIDERS.at(-1);
}
function setupProviderPicker(form, root) {
  const providerSelect = root.querySelector('#provider-select');
  const modelSelect = root.querySelector('#model-select');
  const customModel = root.querySelector('#custom-model-label');
  const help = root.querySelector('#provider-help');
  let savedEndpoint = '';
  for (const provider of TRANSLATION_PROVIDERS) {
    const option = el('option','',provider.name + (provider.quotaLabel ? '【' + provider.quotaLabel + '】' : '')); option.value = provider.id; providerSelect.append(option);
  }
  function updateHelp(provider) {
    help.replaceChildren();
    const links = el('div','provider-links');
    for (const [name,url] of [['注册 / 登录',provider.signupUrl],['申请 API Key ↗',provider.keyUrl],['配置指南 ↗',provider.docsUrl],['额度 / 价格说明 ↗',provider.quotaUrl]]) {
      if (!url) continue;
      const link = el('a','button quiet',name); link.href = url; link.target = '_blank'; link.rel = 'noopener noreferrer'; links.append(link);
    }
    if (links.children.length) help.append(links);
    if (provider.quotaLabel) {
      const quota = el('div','provider-quota');
      quota.append(el('span','provider-quota-label',provider.quotaLabel), el('p','settings-note',provider.quotaNote));
      help.append(quota);
    }
    help.append(el('p','settings-note',provider.note));
    if (provider.quotaLabel) help.append(el('p','settings-note','额度说明核对于 2026-10-05；当前账号资格、模型价格与限制以官方控制台为准。自定义模型不继承免费标记。'));
  }
  function models(provider, model, useDefault) {
    modelSelect.replaceChildren();
    for (const entry of provider.models) {const option=el('option','',entry.name + ' · ' + entry.id + (entry.quotaLabel ? '【' + entry.quotaLabel + '】' : ''));option.value=entry.id;modelSelect.append(option);}
    const custom=el('option','','自定义模型 ID…');custom.value='custom';modelSelect.append(custom);
    const known=provider.models.some(entry=>entry.id===model);
    modelSelect.value=known ? model : useDefault && provider.models.length ? provider.models[0].id : 'custom';
    form.elements.model.value=modelSelect.value==='custom' ? model || '' : modelSelect.value;
    customModel.hidden=modelSelect.value!=='custom';
    updateHelp(provider);
  }
  function endpointChanged() {
    const changed=normalizedEndpoint(form.elements.base_url.value)!==normalizedEndpoint(savedEndpoint);
    form.elements.api_key.placeholder=changed ? '接口已变更 · 请填写此服务的密钥' : form.dataset.hasKey==='true' ? '密钥已保存 · 留空保留' : '填写 API Key（本地无鉴权服务可留空）';
    root.querySelector('#key-change-note').hidden=!changed || form.dataset.hasKey!=='true';
  }
  providerSelect.onchange=()=>{
    const provider=TRANSLATION_PROVIDERS.find(entry=>entry.id===providerSelect.value);
    form.elements.api_key.value='';
    if(provider.id!=='custom') form.elements.base_url.value=provider.baseUrl;
    models(provider,provider.id==='custom' ? form.elements.model.value : '',true);endpointChanged();
  };
  modelSelect.onchange=()=>{
    customModel.hidden=modelSelect.value!=='custom';
    form.elements.model.value=modelSelect.value==='custom' ? '' : modelSelect.value;
    if(modelSelect.value==='custom')form.elements.model.focus();
  };
  form.elements.base_url.onchange=()=>{
    const provider=providerForEndpoint(form.elements.base_url.value);providerSelect.value=provider.id;
    models(provider,form.elements.model.value,false);endpointChanged();
  };
  return {
    load(data) {
      savedEndpoint=data.base_url || '';form.dataset.hasKey=String(Boolean(data.has_key));
      form.elements.base_url.value=savedEndpoint;
      const provider=providerForEndpoint(savedEndpoint);providerSelect.value=provider.id;
      models(provider,data.model || '',!data.model);endpointChanged();
    },
    saved(data) {savedEndpoint=data.base_url;form.dataset.hasKey=String(Boolean(data.has_key));endpointChanged();}
  };
}
