import { App } from "@modelcontextprotocol/ext-apps";

"use strict";
const PHASE_ORDER = ["doctor","product-profile","competitors","keywords",
  "platform-tiktok","platform-instagram","platform-meta-ads","platform-youtube",
  "curation","report","strategy"];
const PHASE_NAMES = {
  doctor:"Setup","product-profile":"Product profile", competitors:"Competitors",
  keywords:"Keywords","platform-tiktok":"TikTok","platform-instagram":"Instagram",
  "platform-meta-ads":"Meta Ads","platform-youtube":"YouTube Shorts",
  curation:"Curation", report:"Report", strategy:"Strategy", delivery:"Save to AdAnt"};
const GHOST_CANDIDATES = ["curation","report","strategy"];
const PLATFORM_PREFIX = "platform-";
const LOG_CAP = 80;
const state = { phases:new Map(), doctor:new Map(), artifacts:new Map(),
  events:0, firstTs:null, lastTs:null, lastNeedUser:null, workspace:null,
  subject:null, selected:null, open:new Set(), fullLog:false, workflow:null,
  summary:null, next:null, risk:null, etaMinutes:null, widgetSessionId:null,
  restoredSessionId:null };
let transportLabel = "connecting…";

const svg = {
  check: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--ok)" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>',
  circle: '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="var(--line)" stroke-width="2.4"><circle cx="12" cy="12" r="9"></circle></svg>',
  cross: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--err)" stroke-width="2.6" stroke-linecap="round"><path d="M18 6 6 18"></path><path d="m6 6 12 12"></path></svg>',
  warn: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--warn)" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v4"></path><path d="M12 17h.01"></path><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"></path></svg>',
};
function phaseMatches(id, prefix){ return id === prefix || id.startsWith(prefix + "-"); }
function baseOrder(id){
  if (state.workflow && Array.isArray(state.workflow.stages)){
    for (let i = 0; i < state.workflow.stages.length; i++)
      if ((state.workflow.stages[i].phases || []).some(prefix => phaseMatches(id, prefix))) return i;
  }
  for (let i = 0; i < PHASE_ORDER.length; i++)
    if (phaseMatches(id, PHASE_ORDER[i])) return i;
  return PHASE_ORDER.length;
}
function upcomingStages(phases){
  if (!state.workflow || !Array.isArray(state.workflow.stages))
    return GHOST_CANDIDATES.filter(id => !state.phases.has(id) || state.phases.get(id).status === "pending")
      .map(id => ({id, label:PHASE_NAMES[id] || id}));
  const stages = state.workflow.stages;
  const states = stages.map(stage => {
    const matches = phases.filter(p => (stage.phases || []).some(prefix => phaseMatches(p.id, prefix)));
    if (matches.some(p => p.status === "active")) return "active";
    if (matches.length && matches.every(p => p.status === "done" || p.status === "warning")) return "done";
    if (matches.some(p => p.status === "error")) return "error";
    return "pending";
  });
  let current = states.findIndex(value => value === "active");
  if (current < 0) for (let i = 0; i < states.length; i++)
    if (states[i] === "done" || states[i] === "error") current = i;
  return stages.filter((_stage, index) => index > current && states[index] === "pending").slice(0, 4);
}
function fmtClock(seconds){
  const m = Math.floor(seconds / 60), s = Math.floor(seconds % 60);
  return m + ":" + String(s).padStart(2, "0");
}
function phaseBudget(p){
  if (p.timeoutSeconds != null) return Number(p.timeoutSeconds);
  if (!state.workflow || !Array.isArray(state.workflow.stages)) return null;
  const stage = state.workflow.stages.find(item => (item.phases || []).some(prefix => phaseMatches(p.id, prefix)));
  return stage && stage.budget_seconds != null ? Number(stage.budget_seconds) : null;
}
function phaseElapsed(p){
  if (p.duration != null) return Number(p.duration);
  return p.started ? Math.max(0, (Date.now() - p.started) / 1000) : 0;
}
function budgetLabel(p){
  const elapsed = phaseElapsed(p), budget = phaseBudget(p);
  if (!budget) return fmtClock(elapsed);
  const over = elapsed > budget;
  return fmtClock(elapsed) + " / " + fmtClock(budget) + (over ? " · over" : "");
}
function workspaceRoot(){
  if (!state.workspace) return null;
  return state.workspace.split("/").slice(0, -2).join("/") || null;
}
function absolutize(path){
  if (!path || path.startsWith("/")) return path;
  const root = workspaceRoot();
  return root ? root + "/" + path : path;
}
function kindOf(path){
  const ext = (path.split(".").pop() || "").toLowerCase();
  if (["png","jpg","jpeg","webp","gif"].includes(ext)) return "image";
  if (ext === "pdf") return "pdf";
  if (ext === "html") return "html";
  if (["json","md","txt","csv","log"].includes(ext)) return "text";
  return "file";
}
function statText(counts){
  if (!counts) return null;
  for (const [k, v] of Object.entries(counts))
    if (typeof v === "number" && k !== "duration_seconds" && k !== "exit") return v + " " + k.replace(/_/g, " ");
  return null;
}
function onEvent(ev){
  state.events += 1;
  const ts = Date.parse(ev.ts);
  if (!Number.isNaN(ts)){ if (!state.firstTs) state.firstTs = ts; state.lastTs = ts; }
  if (ev.subject) state.subject = ev.subject;
  if (ev.workflow) state.workflow = ev.workflow;
  if (ev.summary) state.summary = ev.summary;
  if (ev.next) state.next = ev.next;
  if (ev.risk) state.risk = ev.risk;
  if (ev.eta_minutes != null) state.etaMinutes = ev.eta_minutes;
  if (ev.phase === "doctor" && ev.status === "progress"){
    const m = (ev.message || "").match(/^([a-z0-9-]+): (ok|missing|unknown) \((.*)\)$/);
    if (m) state.doctor.set(m[1], { state:m[2], detail:m[3] });
  }
  let p = state.phases.get(ev.phase);
  if (!p){ p = { id:ev.phase, status:"pending", msg:"", started:ts, duration:null, timeoutSeconds:null, log:[], counts:{} }; state.phases.set(ev.phase, p); }
  if (ev.timeout_seconds != null) p.timeoutSeconds = Number(ev.timeout_seconds);
  if (ev.status === "start"){ p.status = "active"; p.started = ts; p.msg = ev.message || ""; }
  else if (ev.status === "progress"){ if (p.status !== "done") p.status = "active"; p.msg = ev.message || p.msg; }
  else if (ev.status === "done"){ p.status = "done"; p.duration = (ev.counts && ev.counts.duration_seconds) || null; }
  else if (ev.status === "warning"){ p.status = "warning"; p.msg = ev.message || p.msg; }
  else if (ev.status === "error"){ p.status = "error"; p.msg = ev.message || p.msg; }
  if (ev.counts && ev.counts.duration_seconds != null) p.duration = Number(ev.counts.duration_seconds);
  if (ev.message){
    p.log.push((ev.ts || "").slice(11, 19) + "  " + ev.message);
    if (p.log.length > LOG_CAP) p.log.shift();
  }
  if (ev.counts) for (const [k, v] of Object.entries(ev.counts))
    if (typeof v === "number" && k !== "duration_seconds" && k !== "exit") p.counts[k] = v;
  if (ev.status === "need-user") state.lastNeedUser = ev;
  else if (ev.phase === "doctor" && ev.status === "done" && state.lastNeedUser && state.lastNeedUser.phase === "doctor") state.lastNeedUser = null;
  const art = ev.artifact ? { path:absolutize(ev.artifact.path), label:ev.artifact.label }
    : ev.thumb ? { path:absolutize(ev.thumb), label:ev.message || ev.thumb.split("/").pop() } : null;
  if (art && art.path && !state.artifacts.has(art.path))
    state.artifacts.set(art.path, { ...art, kind:kindOf(art.path), phase:ev.phase, ts:(ev.ts || "").slice(11, 16) });
  scheduleRender();
}
let renderQueued = false;
function scheduleRender(){ if (!renderQueued){ renderQueued = true; requestAnimationFrame(()=>{ renderQueued = false; render(); }); } }
function el(tag, cls, text){ const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; }
function icon(name){ const s = el("span"); s.style.flex = "none"; s.style.display = "inline-flex"; s.innerHTML = svg[name]; return s; }

function collapsedRow(label, meta, iconName, onToggle, isOpen){
  const row = el("div", "crow" + (isOpen ? " open" : ""));
  row.appendChild(iconName === "spin" ? Object.assign(el("span", "spin"), {}) : icon(iconName));
  row.appendChild(el("span", "name", label));
  row.appendChild(el("span", "meta", meta || ""));
  row.appendChild(el("span", "chev", "▶"));
  if (onToggle) row.addEventListener("click", onToggle);
  return row;
}
function phaseRowMeta(p){
  const bits = [];
  const stat = statText(p.counts);
  if (stat) bits.push(stat);
  if (p.duration != null) bits.push(budgetLabel(p));
  return bits.join(" · ") || (p.status === "error" ? "failed" : p.status === "warning" ? "fallback used" : "done");
}

function render(){
  const phases = [...state.phases.values()]
    .sort((a, b) => baseOrder(a.id) - baseOrder(b.id) || a.id.localeCompare(b.id));
  const research = phases.filter(p => p.id !== "doctor" && p.id !== "workflow");
  const doctor = state.phases.get("doctor");
  const active = research.filter(p => p.status === "active");
  const done = research.filter(p => p.status === "done" || p.status === "warning" || p.status === "error");
  const started = research.filter(p => p.status !== "pending");
  const phasesDone = started.length > 0 && active.length === 0 && started.every(p => p.status === "done" || p.status === "warning");
  const allDone = state.workflow ? phasesDone && state.workflow.status === "complete" : phasesDone;
  const anyError = research.some(p => p.status === "error");

  /* header */
  const title = document.getElementById("title");
  const status = document.getElementById("status");
  if (state.subject) title.textContent = state.subject;
  if (allDone){
    if (!title.classList.contains("sweep")){ title.classList.add("sweep"); title.textContent = "Research complete"; }
    status.classList.add("hidden");
  } else if (active.length){
    status.classList.remove("hidden"); status.classList.add("shimmer"); status.style.color = "";
    status.textContent = active.map(p => PHASE_NAMES[p.id] || p.id).slice(0, 3).join(" · ");
  } else if (anyError){
    status.classList.remove("hidden", "shimmer"); status.style.color = "var(--err)";
    status.textContent = "a step failed";
  } else if (doctor && doctor.status === "active"){
    status.classList.remove("hidden"); status.classList.add("shimmer");
    status.textContent = "Checking your setup";
  }
  document.getElementById("flowbar").classList.toggle("idle", allDone || anyError || state.lastNeedUser != null);
  document.getElementById("maincol").classList.toggle("dim", state.lastNeedUser != null);

  /* alert */
  const alertBox = document.getElementById("alertBox");
  alertBox.classList.toggle("hidden", !state.lastNeedUser);
  if (state.lastNeedUser){
    document.getElementById("alertTitle").textContent = "Action needed — " + (PHASE_NAMES[state.lastNeedUser.phase] || state.lastNeedUser.phase);
    document.getElementById("alertMsg").textContent = state.lastNeedUser.message;
  }

  /* collapsed rows: setup first, then finished phases */
  const rows = document.getElementById("doneRows"); rows.textContent = "";
  if (doctor){
    const isOpen = state.open.has("doctor");
    const passed = [...state.doctor.values()].filter(c => c.state === "ok").length;
    const meta = doctor.status === "done" ? passed + " checks" + (doctor.duration != null ? " · " + fmtClock(doctor.duration) : "")
      : doctor.status === "error" ? "needs attention" : "checking";
    const iconName = doctor.status === "done" ? "check" : doctor.status === "error" ? "cross" : "spin";
    rows.appendChild(collapsedRow("Setup", meta, iconName,
      ()=>{ state.open.has("doctor") ? state.open.delete("doctor") : state.open.add("doctor"); render(); }, isOpen));
    if (isOpen || (doctor.status === "active" && state.doctor.size)){
      const panel = el("div", "subpanel");
      for (const [name, c] of state.doctor)
        panel.appendChild(el("div", null, (c.state === "ok" ? "✓ " : c.state === "missing" ? "✕ " : "• ") + name + " — " + c.detail));
      rows.appendChild(panel);
    }
  }
  for (const p of done){
    const isOpen = state.open.has(p.id);
    rows.appendChild(collapsedRow(PHASE_NAMES[p.id] || p.id, phaseRowMeta(p), p.status === "done" ? "check" : p.status === "warning" ? "warn" : "cross",
      ()=>{ state.open.has(p.id) ? state.open.delete(p.id) : state.open.add(p.id); render(); }, isOpen));
    if (isOpen && p.log.length) rows.appendChild(el("div", "subpanel", p.log.join("\n")));
  }

  /* Now card */
  const nowWrap = document.getElementById("nowWrap"); nowWrap.textContent = "";
  if (active.length && !allDone){
    nowWrap.appendChild(el("div", "slabel", "Now"));
    const card = el("div", "now");
    const head = el("div", "nhead");
    head.appendChild(el("span", "spin"));
    const platforms = active.filter(p => p.id.startsWith(PLATFORM_PREFIX));
    const headTitle = platforms.length > 1 ? "Browsing platforms" : (PHASE_NAMES[active[0].id] || active[0].id);
    const nt = el("span", "ntitle shimmer", headTitle);
    head.appendChild(nt);
    const meta = [];
    if (active.length > 1) meta.push(active.length + " in parallel");
    if (state.workflow) meta.push(state.workflow.mode === "fast-draft" ? "fast draft" : "production");
    const headMeta = el("span", "nmeta", meta.join(" · "));
    if (active.length === 1){
      headMeta.dataset.phaseClock = active[0].id;
      headMeta.dataset.phasePrefix = meta.join(" · ");
    }
    head.appendChild(headMeta);
    card.appendChild(head);
    const laneSet = platforms.length > 1
      ? research.filter(p => p.id.startsWith(PLATFORM_PREFIX))
      : (active.length > 1 ? active : []);
    for (const p of laneSet){
      const lane = el("div", "lane");
      if (p.status === "active") lane.appendChild(el("span", "spin"));
      else lane.appendChild(icon(p.status === "done" ? "check" : p.status === "warning" ? "warn" : p.status === "error" ? "cross" : "circle"));
      const lname = el("span", "lname", PHASE_NAMES[p.id] || p.id);
      if (p.status === "active") lname.classList.add("shimmer");
      lane.appendChild(lname);
      const detail = el("span", "ldetail", p.status === "done" ? phaseRowMeta(p) : p.status === "pending" ? "queued" : (p.msg || ""));
      if (p.status === "active") detail.dataset.phaseClock = p.id;
      lane.appendChild(detail);
      card.appendChild(lane);
    }
    if (!laneSet.length && active[0] && active[0].msg){
      const lane = el("div", "lane");
      lane.appendChild(el("span", "ldetail", active[0].msg));
      card.appendChild(lane);
    }
    const briefItems = [
      ["Found so far", state.summary, ""],
      ["Next", state.next, ""],
      ["Risk", state.risk, "risk"],
      ["ETA", state.etaMinutes != null ? String(state.etaMinutes) + " min" : null, ""],
    ].filter(item => item[1]);
    if (briefItems.length){
      const brief = el("div", "brief");
      for (const [label, value, cls] of briefItems){
        const row = el("div", "briefrow" + (cls ? " " + cls : ""));
        row.appendChild(el("b", null, label)); row.appendChild(el("span", null, value)); brief.appendChild(row);
      }
      card.appendChild(brief);
    }
    const merged = active.flatMap(p => p.log.slice(state.fullLog ? -LOG_CAP : -3).map(line => [line, p.id]))
      .sort((a, b) => a[0] < b[0] ? -1 : 1).slice(state.fullLog ? -200 : -3);
    if (merged.length){
      const log = el("div", "nowlog" + (state.fullLog ? " full" : ""), merged.map(x => x[0]).join("\n"));
      card.appendChild(log);
    }
    const expand = el("div", "expand");
    const link = el("a", null, state.fullLog ? "Collapse activity" : "View full activity");
    link.addEventListener("click", ()=>{ state.fullLog = !state.fullLog; render(); });
    expand.appendChild(link);
    card.appendChild(expand);
    nowWrap.appendChild(card);
  }

  /* finale */
  const finale = document.getElementById("finale");
  finale.classList.toggle("hidden", !allDone);
  if (allDone && !finale.dataset.built){
    finale.dataset.built = "1"; finale.textContent = "";
    const arts = [...state.artifacts.values()];
    const main = arts.filter(a => a.kind === "pdf").pop() || arts.filter(a => a.kind === "html").pop() || arts[arts.length - 1];
    if (main){
      const card = buildResCard(main, true);
      finale.appendChild(card);
    }
    const totals = {};
    for (const p of research) for (const [k, v] of Object.entries(p.counts)) totals[k] = (totals[k] > v ? totals[k] : v);
    const keys = Object.keys(totals).slice(0, 4);
    if (keys.length){
      const stats = el("div", "stats"); stats.style.marginTop = "12px";
      for (const k of keys){
        const box = el("div", "stat");
        box.appendChild(el("b", null, String(totals[k])));
        box.appendChild(el("span", null, k.replace(/_/g, " ")));
        stats.appendChild(box);
      }
      finale.appendChild(stats);
    }
    const lbl = el("div", "slabel", "Full run"); lbl.style.margin = "12px 0 6px"; finale.appendChild(lbl);
  }

  /* results */
  const resWrap = document.getElementById("resWrap"); resWrap.textContent = "";
  const arts = [...state.artifacts.values()];
  if (arts.length && !allDone){
    resWrap.appendChild(el("div", "slabel", "Results"));
    const featured = arts.filter(a => a.kind === "pdf" || a.kind === "html");
    const rest = arts.filter(a => !featured.includes(a));
    for (const a of featured.slice(-2)) resWrap.appendChild(buildResCard(a, false));
    if (rest.length){
      const box = el("div", "resrows");
      for (const a of rest.slice(-6)){
        const row = el("div", "crow" + (state.selected === a.path ? " open" : ""));
        row.appendChild(el("span", "kind", a.kind.toUpperCase()));
        row.appendChild(el("span", "name", a.label));
        row.appendChild(el("span", "meta", a.ts));
        row.appendChild(el("span", "chev", "▶"));
        row.addEventListener("click", ()=>{ openPreview(a); });
        box.appendChild(row);
      }
      resWrap.appendChild(box);
    }
  }

  /* ghosts */
  const ghostWrap = document.getElementById("ghostWrap"); ghostWrap.textContent = "";
  if (started.length && !allDone){
    const upcoming = upcomingStages(phases);
    if (upcoming.length){
      ghostWrap.appendChild(el("div", "slabel", "Up next"));
      const row = el("div", "ghosts");
      for (const stage of upcoming){
        const chip = el("span");
        chip.appendChild(icon("circle"));
        const budget = stage.budget_seconds ? " · " + fmtClock(stage.budget_seconds) : "";
        chip.appendChild(el("span", null, (stage.label || PHASE_NAMES[stage.id] || stage.id) + budget));
        row.appendChild(chip);
      }
      ghostWrap.appendChild(row);
    }
  }

  document.getElementById("app").classList.toggle("haspreview", state.selected != null);
  document.getElementById("evCount").textContent = state.events + " events" + (allDone ? " · archived" : "");
  document.getElementById("wsline").textContent = transportLabel;
  updateClocks();
  saveUiSession();
}
function buildResCard(a, big){
  const card = el("div", "rescard" + (state.selected === a.path ? " sel" : ""));
  if (a.kind === "image"){
    const img = document.createElement("img"); img.className = "thumbimg"; img.alt = "";
    fetchArtifact(a.path).then(payload => {
      if (payload.encoding === "base64") img.src = "data:" + payload.mimeType + ";base64," + payload.data;
    }).catch(()=>{});
    card.appendChild(img);
  } else {
    const cover = el("div", "cover");
    cover.appendChild(el("span", "ck", "ADANT RESEARCH"));
    cover.appendChild(el("span", "cn", (state.subject || a.label).slice(0, 44)));
    card.appendChild(cover);
  }
  const info = el("div", "rinfo");
  info.appendChild(el("div", "rname", a.label));
  info.appendChild(el("div", "rmeta", a.kind.toUpperCase() + " · " + a.ts + (big ? " · delivered in chat" : "")));
  info.appendChild(el("div", "ract", "Preview"));
  card.appendChild(info);
  card.addEventListener("click", ()=>{ openPreview(a); });
  return card;
}
function updateClocks(){
  const now = Date.now();
  const completeTs = state.workflow && state.workflow.completed ? Date.parse(state.workflow.completed) : null;
  const elapsed = state.firstTs ? Math.max(0, ((completeTs || now) - state.firstTs) / 1000) : 0;
  const target = state.workflow && Number(state.workflow.target_seconds);
  document.getElementById("elapsed").textContent = state.firstTs
    ? fmtClock(elapsed) + (target ? " / " + fmtClock(target) : "") : "";
  const ratio = target ? elapsed / target : 0;
  document.getElementById("timefill").style.width = Math.min(1, ratio) * 100 + "%";
  const bar = document.getElementById("timebar");
  bar.classList.toggle("warn", ratio >= .8 && ratio <= 1);
  bar.classList.toggle("over", ratio > 1);
  for (const node of document.querySelectorAll("[data-phase-clock]")){
    const p = state.phases.get(node.dataset.phaseClock);
    if (!p) continue;
    const phaseRatio = phaseBudget(p) ? phaseElapsed(p) / phaseBudget(p) : 0;
    const prefix = node.dataset.phasePrefix || "";
    node.textContent = (prefix ? prefix + " · " : "") + budgetLabel(p) + (p.msg && !prefix ? " · " + p.msg : "");
    node.classList.toggle("warn", phaseRatio >= .8 && phaseRatio <= 1);
    node.classList.toggle("over", phaseRatio > 1);
  }
}
setInterval(updateClocks, 1000);

/* ---------- preview ---------- */
async function openPreview(art){
  state.selected = art.path; render();
  const col = document.getElementById("previewcol"); col.textContent = "";
  const box = el("div", "preview");
  const head = el("div", "phead");
  head.appendChild(el("span", "kind", art.kind.toUpperCase()));
  head.appendChild(el("span", "pname", art.label));
  const close = el("button", "close", "✕");
  close.addEventListener("click", ()=>{ state.selected = null; col.textContent = ""; render(); });
  head.appendChild(close);
  box.appendChild(head);
  const body = el("div", "pbody");
  body.appendChild(el("div", "note", "loading…"));
  box.appendChild(body);
  col.appendChild(box);
  try {
    const payload = await fetchArtifact(art.path);
    body.textContent = "";
    if (payload.mimeType.startsWith("image/")){
      const img = document.createElement("img");
      img.src = "data:" + payload.mimeType + ";base64," + payload.data;
      body.appendChild(img);
    } else if (payload.mimeType === "text/html"){
      const frame = document.createElement("iframe");
      frame.setAttribute("sandbox", "");
      frame.srcdoc = payload.data;
      body.appendChild(frame);
    } else if (payload.encoding === "text"){
      body.appendChild(el("pre", null, payload.data.slice(0, 200000)));
    } else if (payload.mimeType === "application/pdf"){
      const frame = document.createElement("iframe");
      frame.src = "data:application/pdf;base64," + payload.data;
      body.appendChild(frame);
      body.appendChild(el("div", "note", "If the PDF does not render here, open it from the chat delivery."));
    } else {
      body.appendChild(el("div", "note", "No inline preview for this file type."));
    }
  } catch (error){
    body.textContent = "";
    body.appendChild(el("div", "note", "Preview unavailable: " + (error && error.message || error)));
  }
}

/* ---------- transports ---------- */
function resetState(){
  state.phases.clear(); state.doctor.clear(); state.artifacts.clear();
  state.events = 0; state.firstTs = null; state.lastTs = null; state.lastNeedUser = null;
  state.subject = null; state.selected = null; state.open.clear(); state.fullLog = false;
  state.workflow = null; state.summary = null; state.next = null; state.risk = null; state.etaMinutes = null;
  state.widgetSessionId = null; state.restoredSessionId = null;
  const finale = document.getElementById("finale"); delete finale.dataset.built; finale.textContent = "";
  const title = document.getElementById("title"); title.classList.remove("sweep"); title.textContent = "AdAnt Research";
}
function saveUiSession(){
  if (!state.widgetSessionId) return;
  try {
    sessionStorage.setItem("adant-progress:" + state.widgetSessionId, JSON.stringify({
      selected:state.selected, open:[...state.open], fullLog:state.fullLog,
    }));
  } catch (_e) {}
}
function restoreUiSession(){
  if (!state.widgetSessionId || state.restoredSessionId === state.widgetSessionId) return;
  state.restoredSessionId = state.widgetSessionId;
  try {
    const saved = JSON.parse(sessionStorage.getItem("adant-progress:" + state.widgetSessionId) || "null");
    if (!saved) return;
    state.selected = typeof saved.selected === "string" ? saved.selected : null;
    state.open = new Set(Array.isArray(saved.open) ? saved.open : []);
    state.fullLog = saved.fullLog === true;
  } catch (_e) {}
}
function ingestSnapshot(snap){
  if (!snap || !Array.isArray(snap.events)) return;
  if (snap.workspace !== state.workspace || snap.widgetSessionId !== state.widgetSessionId || snap.events.length < state.events){
    resetState(); state.workspace = snap.workspace;
  }
  state.widgetSessionId = snap.widgetSessionId || snap.workspace || "default";
  restoreUiSession();
  if (snap.workflow) state.workflow = snap.workflow;
  for (const ev of snap.events.slice(state.events)) onEvent(ev);
  scheduleRender();
}
let mode = "none";
async function fetchArtifact(path){
  if (mode === "bridge"){
    const result = await mcpApp.callServerTool({ name: "research_artifact_read", arguments: { path } });
    if (result && result.isError) throw new Error((result.content && result.content[0] && result.content[0].text) || "read failed");
    return result.structuredContent;
  }
  const response = await fetch("artifact?path=" + encodeURIComponent(path));
  if (!response.ok) throw new Error(await response.text());
  const mime = (response.headers.get("Content-Type") || "").split(";")[0];
  if (mime.startsWith("image/") || mime === "application/pdf"){
    const buffer = new Uint8Array(await response.arrayBuffer());
    let binary = ""; for (const b of buffer) binary += String.fromCharCode(b);
    return { mimeType: mime, encoding: "base64", data: btoa(binary) };
  }
  return { mimeType: mime, encoding: "text", data: await response.text() };
}
function connectSse(){
  mode = "sse"; transportLabel = "local · events.jsonl";
  const source = new EventSource("events");
  source.onmessage = (message)=>{ try {
    const payload = JSON.parse(message.data);
    if (payload.snapshot) ingestSnapshot(payload.snapshot); else onEvent(payload);
  } catch (_e) {} };
  source.onerror = ()=>{};
  scheduleRender();
}
let mcpApp = null;
async function connectBridge(){
  const app = new App(
    { name: "AdAnt Research", version: "2.0.0" },
    { availableDisplayModes: ["inline", "fullscreen"] },
  );
  app.ontoolresult = (result)=>{ ingestSnapshot(result && result.structuredContent); };
  await app.connect();
  mcpApp = app;
  mode = "bridge"; transportLabel = "in-app · live";
  const poll = async ()=>{
    try {
      const result = await app.callServerTool({ name: "research_progress_snapshot", arguments: {} });
      ingestSnapshot(result && result.structuredContent);
    } catch (_e) {}
  };
  await poll();
  setInterval(poll, 2500);
}
(async function connect(){
  if (window.parent !== window){
    try { await connectBridge(); return; } catch (_e) {}
  }
  if (location.protocol === "http:" || location.protocol === "https:") connectSse();
  else transportLabel = "no live transport";
  scheduleRender();
})();
