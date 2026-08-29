// AI Agent 控制台 —— 原生 JS，零依赖，对接 FastAPI 后端
"use strict";

const state = {
  base: window.location.origin,
  lastBatchId: null,
};

// ---------- 工具函数 ----------
const $ = (id) => document.getElementById(id);

function api(path, opts = {}) {
  const url = state.base.replace(/\/$/, "") + path;
  const init = {
    method: opts.method || "GET",
    headers: { "Content-Type": "application/json" },
  };
  if (opts.body) init.body = JSON.stringify(opts.body);
  return fetch(url, init).then(async (res) => {
    let data = null;
    try { data = await res.json(); } catch (e) { /* 非 JSON */ }
    if (!res.ok) {
      const msg = (data && (data.detail || data.message)) || `HTTP ${res.status}`;
      throw new Error(msg);
    }
    return data;
  });
}

let toastTimer = null;
function toast(msg, type = "") {
  const t = $("toast");
  t.textContent = msg;
  t.className = "toast " + type;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.add("hidden"), 3200);
}

function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// ---------- 每个用户自带 API 模型配置（存 localStorage）----------
const LLM_STORE_KEY = "ai_llm_config";

// 各服务商默认模型，便于用户少填
const PROVIDER_DEFAULT_MODEL = {
  deepseek: "deepseek-chat",
  doubao: "ep-xxxxxxxx",
  qwen: "qwen-plus",
};

function getLLMConfig() {
  try {
    const raw = localStorage.getItem(LLM_STORE_KEY);
    if (!raw) return null;
    const c = JSON.parse(raw);
    if (!c.api_key) return null;
    const out = { provider: c.provider, api_key: c.api_key };
    if (c.model) out.model = c.model;
    if (c.base_url) out.base_url = c.base_url;
    if (c.emb_provider && c.emb_key) {
      out.embedding_provider = c.emb_provider;
      out.embedding_api_key = c.emb_key;
      if (c.emb_model) out.embedding_model = c.emb_model;
    }
    return out;
  } catch (e) {
    return null;
  }
}

// 把当前用户的 API 配置并入请求体（仅对支持 llm 字段的接口生效）
function withLLM(body) {
  const cfg = getLLMConfig();
  if (!cfg) return body;
  return Object.assign({}, body, { llm: cfg });
}

function renderLLMStatus() {
  const c = getLLMConfig();
  const el = $("llmStatus");
  if (c) {
    el.textContent = "模型：" + (c.provider || "custom") + (c.model ? " / " + c.model : "");
    el.classList.add("configured");
  } else {
    el.textContent = "未配置模型";
    el.classList.remove("configured");
  }
}

function openApiModal() {
  let c = {};
  try { c = JSON.parse(localStorage.getItem(LLM_STORE_KEY) || "{}"); } catch (e) {}
  $("cfg-provider").value = c.provider || "deepseek";
  $("cfg-model").value = c.model || (c.provider && PROVIDER_DEFAULT_MODEL[c.provider]) || "";
  $("cfg-key").value = c.api_key || "";
  $("cfg-baseurl").value = c.base_url || "";
  $("cfg-emb-provider").value = c.emb_provider || "";
  $("cfg-emb-model").value = c.emb_model || "";
  $("cfg-emb-key").value = c.emb_key || "";
  toggleCustomBaseUrl();
  $("cfg-msg").textContent = "";
  $("apiModal").classList.remove("hidden");
}

function toggleCustomBaseUrl() {
  const isCustom = $("cfg-provider").value === "custom";
  $("cfg-baseurl").closest(".cfg-custom").classList.toggle("hidden", !isCustom);
}

function saveApiConfig() {
  const provider = $("cfg-provider").value;
  const api_key = $("cfg-key").value.trim();
  if (!api_key) { $("cfg-msg").className = "cfg-msg err"; $("cfg-msg").textContent = "请填写 API Key"; return; }
  if (provider === "custom" && !$("cfg-baseurl").value.trim()) {
    $("cfg-msg").className = "cfg-msg err"; $("cfg-msg").textContent = "自定义服务商需填写 Base URL"; return;
  }
  const cfg = {
    provider,
    api_key,
    model: $("cfg-model").value.trim() || PROVIDER_DEFAULT_MODEL[provider] || "",
    base_url: $("cfg-baseurl").value.trim(),
    emb_provider: $("cfg-emb-provider").value,
    emb_model: $("cfg-emb-model").value.trim(),
    emb_key: $("cfg-emb-key").value.trim(),
  };
  localStorage.setItem(LLM_STORE_KEY, JSON.stringify(cfg));
  renderLLMStatus();
  $("cfg-msg").className = "cfg-msg ok"; $("cfg-msg").textContent = "已保存";
  setTimeout(() => $("apiModal").classList.add("hidden"), 700);
  toast("API 配置已保存", "success");
}

function clearApiConfig() {
  localStorage.removeItem(LLM_STORE_KEY);
  renderLLMStatus();
  $("cfg-msg").className = "cfg-msg ok"; $("cfg-msg").textContent = "已清除，将使用服务端默认配置";
  toast("已清除 API 配置", "success");
}

async function testApiConfig() {
  const cfg = getLLMConfig();
  if (!cfg) { $("cfg-msg").className = "cfg-msg err"; $("cfg-msg").textContent = "请先填写并保存配置"; return; }
  try {
    await api("/health");
    $("cfg-msg").className = "cfg-msg ok";
    $("cfg-msg").textContent = "服务可达，配置已就绪（真实可用性以首次调用为准）";
  } catch (e) {
    $("cfg-msg").className = "cfg-msg err"; $("cfg-msg").textContent = "无法连接后端：" + e.message;
  }
}

// ---------- 健康探测 ----------
async function checkHealth() {
  try {
    const r = await api("/health");
    $("healthDot").className = "health-dot online";
    $("healthText").textContent = "在线 · " + (r.service || "ok");
  } catch (e) {
    $("healthDot").className = "health-dot offline";
    $("healthText").textContent = "离线";
  }
}

// ---------- Tabs ----------
function switchTab(name) {
  document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".panel").forEach((p) => p.classList.toggle("active", p.id === "tab-" + name));
}
document.querySelectorAll(".tab").forEach((b) => b.addEventListener("click", () => switchTab(b.dataset.tab)));

// ---------- 选题中心 ----------
async function genTopics() {
  const btn = $("btnGen");
  btn.disabled = true;
  try {
    const payload = {
      industry: $("t-industry").value.trim(),
      style: $("t-style").value.trim(),
      count: parseInt($("t-count").value, 10) || 5,
      use_knowledge: $("t-useKb").checked,
      write_to_bitable: $("t-bitable").checked,
      hotspots: $("t-hotspots").value.trim(),
    };
    if (!payload.industry) { toast("请填写行业", "error"); return; }
    const data = await api("/api/topic/generate", { method: "POST", body: withLLM(payload) });
    state.lastBatchId = data.batch_id;
    renderSummary(data);
    renderTopics(data);
    $("btnApprove").disabled = false;
    toast("已生成 " + (data.count || 0) + " 条选题", "success");
  } catch (e) {
    toast("生成失败：" + e.message, "error");
  } finally {
    btn.disabled = false;
  }
}

function renderSummary(data) {
  const s = data.quality_summary || data.summary;
  const box = $("t-summary");
  if (!s) { box.classList.add("hidden"); return; }
  const tc = s.tier_counts || {};
  box.classList.remove("hidden");
  box.innerHTML =
    `本批共 <b>${s.total ?? "-"}</b> 条，去重后保留 <b>${s.kept ?? "-"}</b> 条，` +
    `移除重复 <b>${s.duplicates_removed ?? 0}</b> 条，平均分 <b>${s.avg_score ?? "-"}</b>。` +
    (s.top_topic ? ` 最佳：<b>${esc(s.top_topic.title)}</b>（${s.top_topic.score} 分）` : "") +
    ` 等级分布：优质 ${tc["优质"] || 0} / 良好 ${tc["良好"] || 0} / 待优化 ${tc["待优化"] || 0}` +
    (data.batch_id ? ` ｜ 批次ID：<b>${esc(data.batch_id)}</b>` : "");
}

function renderTopics(data) {
  const list = $("t-list");
  list.innerHTML = "";
  const topics = (data.topics || []).filter((t) => !t.is_duplicate);
  topics.forEach((t) => {
    const q = t.quality || {};
    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `
      <div class="rank">${t.rank ?? "-"}</div>
      <input type="checkbox" data-id="${esc(t.id)}" />
      <h3>${esc(t.title || t.topic || "未命名选题")}</h3>
      <div class="meta">核心角度：<span class="topic">${esc(t.topic || "")}</span></div>
      ${t.hook ? `<div class="field"><span class="k">钩子</span>${esc(t.hook)}</div>` : ""}
      ${t.script_outline ? `<div class="field"><span class="k">脚本</span>${esc(t.script_outline)}</div>` : ""}
      ${t.target_audience ? `<div class="field"><span class="k">人群</span>${esc(t.target_audience)}</div>` : ""}
      ${(t.tags || []).length ? `<div class="tags">${t.tags.map((x) => `<span class="tag">${esc(x)}</span>`).join("")}</div>` : ""}
      <div class="field">
        <span class="score">${q.score ?? "-"}</span>
        <span class="badge ${esc(q.tier || "")}">${esc(q.tier || "未知")}</span>
      </div>
      ${(q.suggestions || []).length ? `<div class="suggestions">建议：${q.suggestions.map(esc).join("；")}</div>` : ""}
    `;
    const cb = card.querySelector("input[type=checkbox]");
    cb.addEventListener("change", () => card.classList.toggle("selected", cb.checked));
    list.appendChild(card);
  });
}

async function approveTopics() {
  if (!state.lastBatchId) { toast("请先生成选题", "error"); return; }
  const checked = [...document.querySelectorAll("#t-list input[type=checkbox]:checked")].map((c) => c.dataset.id);
  const body = { batch_id: state.lastBatchId };
  if (checked.length) body.topic_ids = checked;
  else body.top_n = 3; // 未勾选时默认优选前 3
  try {
    const data = await api("/api/topic/approve", { method: "POST", body });
    const titles = (data.approved_topics || []).map((t) => esc(t.title || t.topic || t.id)).join("、");
    toast("已审核通过 " + (data.approved || []).length + " 条", "success");
    if (titles) $("t-summary").insertAdjacentHTML("beforeend", `<br>已优选：${titles}`);
  } catch (e) {
    toast("审核失败：" + e.message, "error");
  }
}

// ---------- 知识库 ----------
async function kbSearch() {
  const q = $("k-query").value.trim();
  if (!q) { toast("请填写检索内容", "error"); return; }
  try {
    const data = await api("/api/knowledge/search", { method: "POST", body: { query: q, top_k: 5 } });
    $("k-result").textContent = JSON.stringify(data.results || data, null, 2);
  } catch (e) { toast("检索失败：" + e.message, "error"); }
}

async function kbIngest() {
  const text = $("k-text").value.trim();
  if (!text) { toast("请填写导入文本", "error"); return; }
  try {
    const data = await api("/api/knowledge/ingest", { method: "POST", body: withLLM({ text, source: "console" }) });
    $("k-result").textContent = JSON.stringify(data, null, 2);
    toast("导入成功", "success");
  } catch (e) { toast("导入失败：" + e.message, "error"); }
}

// ---------- Agent ----------
async function runAgent() {
  const input = $("a-input").value.trim();
  if (!input) { toast("请填写任务描述", "error"); return; }
  try {
    const data = await api("/api/agent/run", {
      method: "POST",
      body: withLLM({ agent_type: $("a-type").value, user_input: input, max_iterations: parseInt($("a-max").value, 10) || 6 }),
    });
    $("a-result").textContent = JSON.stringify(data, null, 2);
    toast("Agent 运行完成", "success");
  } catch (e) { toast("运行失败：" + e.message, "error"); }
}

// ---------- 短视频解析 ----------
async function analyze() {
  const url = $("s-url").value.trim();
  const text = $("s-text").value.trim();
  if (!url && !text) { toast("请填写链接或文案", "error"); return; }
  try {
    const data = url
      ? await api("/api/short-video/analyze-url", { method: "POST", body: withLLM({ url }) })
      : await api("/api/short-video/analyze-text", { method: "POST", body: withLLM({ text }) });
    $("s-result").textContent = JSON.stringify(data, null, 2);
    toast("分析完成", "success");
  } catch (e) { toast("分析失败：" + e.message, "error"); }
}

// ---------- 绑定事件 ----------
function bind() {
  $("btnGen").addEventListener("click", genTopics);
  $("btnApprove").addEventListener("click", approveTopics);
  $("btnKSearch").addEventListener("click", kbSearch);
  $("btnKIngest").addEventListener("click", kbIngest);
  $("btnARun").addEventListener("click", runAgent);
  $("btnSAnalyze").addEventListener("click", analyze);

  // API 配置弹窗
  $("btnApiConfig").addEventListener("click", openApiModal);
  $("btnApiClose").addEventListener("click", () => $("apiModal").classList.add("hidden"));
  $("btnApiSave").addEventListener("click", saveApiConfig);
  $("btnApiClear").addEventListener("click", clearApiConfig);
  $("btnApiTest").addEventListener("click", testApiConfig);
  $("cfg-provider").addEventListener("change", () => {
    toggleCustomBaseUrl();
    if (!$("cfg-model").value.trim() && PROVIDER_DEFAULT_MODEL[$("cfg-provider").value]) {
      $("cfg-model").value = PROVIDER_DEFAULT_MODEL[$("cfg-provider").value];
    }
  });
  $("apiModal").addEventListener("click", (e) => { if (e.target.id === "apiModal") $("apiModal").classList.add("hidden"); });

  $("baseUrl").addEventListener("change", (e) => { state.base = e.target.value.trim() || window.location.origin; checkHealth(); });
  $("baseUrl").value = state.base;

  // AI 视频异步生成
  $("av-submit").addEventListener("click", aiSubmit);
  $("av-query").addEventListener("click", aiQuery);
  $("av-poll").addEventListener("click", aiPoll);
  $("av-apply").addEventListener("click", avApplyJson);
  $("av-get").addEventListener("click", avExportJson);
}

bind();
initAIVideo();
renderLLMStatus();
checkHealth();
setInterval(checkHealth, 15000);

// ---------- AI 视频异步生成 ----------
// 模型规格由后端 /api/video/models 提供（单一事实来源）；前端仅做动态联动与校验。
let avModels = [];
let avPollTimer = null;

function avFindModel(id) {
  return avModels.find((m) => m.id === id) || null;
}

// 根据模型最大时长生成可选秒数列表（>16 秒用步长 5，并补全最大值）
function buildDurationOptions(maxDuration) {
  const opts = [];
  if (maxDuration <= 16) {
    for (let s = 1; s <= maxDuration; s++) opts.push(s);
  } else {
    for (let s = 5; s <= maxDuration; s += 5) opts.push(s);
    if (opts[opts.length - 1] !== maxDuration) opts.push(maxDuration);
  }
  return opts;
}

async function initAIVideo() {
  try {
    const data = await api("/api/video/models");
    avModels = (data && data.models) || [];
  } catch (e) {
    avModels = [];
    console.warn("获取视频模型列表失败：", e.message);
  }
  const sel = $("av-model");
  sel.innerHTML = "";
  avModels.forEach((m) => {
    const o = document.createElement("option");
    o.value = m.id;
    o.textContent = m.name;
    sel.appendChild(o);
  });
  sel.addEventListener("change", avOnModelChange);
  if (avModels.length) avOnModelChange();
  else $("av-err").textContent = "未能加载模型列表，请确认后端 /api/video/models 可用";
}

// 切换模型 → 动态更新时长可选项 + 置灰不支持的分辨率
function avOnModelChange() {
  const m = avFindModel($("av-model").value);
  if (!m) return;
  // 时长
  const dur = $("av-duration");
  const cur = parseInt(dur.value, 10);
  const opts = buildDurationOptions(m.max_duration);
  dur.innerHTML = "";
  opts.forEach((s) => {
    const o = document.createElement("option");
    o.value = s;
    o.textContent = s + " 秒";
    dur.appendChild(o);
  });
  if (cur && cur <= m.max_duration) dur.value = cur;
  else dur.value = opts[opts.length - 1];
  // 分辨率：不支持的置灰不可选，并自动切到第一个支持的
  const resSel = $("av-resolution");
  Array.from(resSel.options).forEach((o) => { o.disabled = !m.resolutions.includes(o.value); });
  const selOpt = resSel.options[resSel.selectedIndex];
  if (selOpt && selOpt.disabled) {
    const firstOk = Array.from(resSel.options).find((o) => !o.disabled);
    if (firstOk) resSel.value = firstOk.value;
  }
}

function avSetErr(msg) {
  const e = $("av-err");
  e.textContent = msg || "";
  e.style.display = msg ? "inline" : "none";
}

function avValidate() {
  const m = avFindModel($("av-model").value);
  if (!m) return "请选择模型";
  const dur = parseInt($("av-duration").value, 10);
  if (!dur || dur <= 0) return "请选择时长";
  if (dur > m.max_duration) return `模型 ${m.name} 最长 ${m.max_duration} 秒`;
  const res = $("av-resolution").value;
  if (!m.resolutions.includes(res)) return `模型 ${m.name} 不支持分辨率 ${res}`;
  if (!$("av-prompt").value.trim()) return "请填写提示词 Prompt";
  return null;
}

async function aiSubmit() {
  avSetErr("");
  const err = avValidate();
  if (err) { avSetErr(err); toast(err, "error"); return; }
  const btn = $("av-submit");
  btn.disabled = true;
  try {
    const payload = {
      model: $("av-model").value,
      duration: parseInt($("av-duration").value, 10),
      resolution: $("av-resolution").value,
      style: $("av-style").value,
      prompt: $("av-prompt").value.trim(),
    };
    const data = await api("/api/video/submit", { method: "POST", body: payload });
    $("av-taskId").value = data.task_id;          // 自动回填任务 ID
    $("av-result").textContent = JSON.stringify(data, null, 2);
    avRenderStatus(data);
    toast("已提交，任务 ID：" + data.task_id, "success");
  } catch (e) {
    avSetErr(e.message);
    toast("提交失败：" + e.message, "error");
  } finally {
    btn.disabled = false;
  }
}

function avRenderStatus(data) {
  const box = $("av-status");
  if (!data) { box.innerHTML = ""; return; }
  const status = data.status || (data.payload && data.payload.status) || "未知";
  const progress = data.progress != null ? data.progress
    : (data.payload && data.payload.progress);
  const videoUrl = (data.result && data.result.video_url) || data.video_url || null;
  const tierClass = {
    submitted: "pending", processing: "pending", rate_limited: "pending",
    succeeded: "ok", failed: "err", timeout: "err",
  }[status] || "pending";
  let html = `<span class="badge ${tierClass}">${esc(status)}</span>`;
  if (progress != null) {
    const p = Math.max(0, Math.min(100, Number(progress) || 0));
    html += `<div class="av-progress"><div class="av-bar" style="width:${p}%"></div></div><span class="av-pct">${p}%</span>`;
  }
  if (videoUrl) {
    html += `<div class="av-video"><video src="${esc(videoUrl)}" controls></video>` +
            `<div><a href="${esc(videoUrl)}" target="_blank" rel="noopener">打开视频链接</a></div></div>`;
  }
  box.innerHTML = html;
}

async function aiQuery() {
  const id = $("av-taskId").value.trim();
  if (!id) { toast("请填写任务 ID", "error"); return null; }
  try {
    const data = await api("/api/video/status/" + encodeURIComponent(id));
    $("av-result").textContent = JSON.stringify(data, null, 2);
    avRenderStatus(data);
    return data;
  } catch (e) {
    toast("查询失败：" + e.message, "error");
    return null;
  }
}

function aiPoll() {
  if (avPollTimer) {
    clearInterval(avPollTimer); avPollTimer = null;
    $("av-poll").textContent = "自动轮询";
    return;
  }
  const id = $("av-taskId").value.trim();
  if (!id) { toast("请先提交或填写任务 ID", "error"); return; }
  $("av-poll").textContent = "停止轮询";
  avPollTimer = setInterval(async () => {
    const d = await aiQuery();
    if (d) {
      const s = d.status || (d.payload && d.payload.status);
      if (["succeeded", "failed", "timeout"].includes(s)) {
        clearInterval(avPollTimer); avPollTimer = null;
        $("av-poll").textContent = "自动轮询";
        toast("任务结束：" + s, s === "succeeded" ? "success" : "error");
      }
    }
  }, 3000);
}

// 代码回显赋值：暴露全局 API，支持编程方式给表单赋值（手动选择 / 代码赋值 双通道）
const AIVideo = {
  set(obj = {}) {
    if (!obj) return;
    if (obj.model) { $("av-model").value = obj.model; avOnModelChange(); }
    if (obj.duration != null) $("av-duration").value = obj.duration;
    if (obj.resolution) $("av-resolution").value = obj.resolution;
    if (obj.style) $("av-style").value = obj.style;
    if (obj.prompt != null) $("av-prompt").value = obj.prompt;
    if (obj.taskId != null) $("av-taskId").value = obj.taskId;
  },
  get() {
    return {
      model: $("av-model").value,
      duration: $("av-duration").value,
      resolution: $("av-resolution").value,
      style: $("av-style").value,
      prompt: $("av-prompt").value,
      taskId: $("av-taskId").value,
    };
  },
  submit: aiSubmit,
  query: aiQuery,
  poll: aiPoll,
};
window.AIVideo = AIVideo;

function avApplyJson() {
  const raw = $("av-json").value.trim();
  if (!raw) { toast("请粘贴 JSON", "error"); return; }
  try {
    AIVideo.set(JSON.parse(raw));
    toast("已应用回显", "success");
  } catch (e) {
    toast("JSON 解析失败：" + e.message, "error");
  }
}

function avExportJson() {
  $("av-json").value = JSON.stringify(AIVideo.get(), null, 2);
  toast("已导出当前值", "success");
}
