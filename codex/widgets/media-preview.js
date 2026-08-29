import { App } from "@modelcontextprotocol/ext-apps";

"use strict";
const GET_JOB_TOOL = "adant_get_media_job";
const CANCEL_JOB_TOOL = "adant_cancel_media_job";
const POLL_INTERVAL_MS = 5000;
const terminal = new Set(["completed", "failed", "canceled"]);
const card = document.getElementById("card");
const media = document.getElementById("media");
const title = document.getElementById("title");
const subtitle = document.getElementById("subtitle");
const status = document.getElementById("status");
const analysis = document.getElementById("analysis");
const error = document.getElementById("error");
const credits = document.getElementById("credits");
const refresh = document.getElementById("refresh");
const cancel = document.getElementById("cancel");
const open = document.getElementById("open");
let app;
let view = null;
let pollTimer = null;

function resultData(result) {
  return result && (result.structuredContent || result.result?.structuredContent);
}

function normalize(data) {
  if (!data || typeof data !== "object") return null;
  const nestedJob = data.job && typeof data.job === "object" ? data.job : null;
  const local = Boolean(
    nestedJob || data.uploadId || data.path || data.outputPath || data.analysis,
  );
  const job = nestedJob || data;
  return {
    raw: data,
    job,
    local,
    status: job.status || "completed",
    title: job.title || (data.analysis ? "AdAnt media analysis" : local ? "Local media edit" : "AdAnt media generation"),
    subtitle: data.outputPath || data.path || (job.jobId ? `Job ${job.jobId}` : "Local media operation"),
    kind: job.kind || data.kind,
    artifactUrl: job.artifactUrl || data.url || null,
    analysis: typeof data.analysis === "string" ? data.analysis : null,
    error: job.error || data.error?.message || null,
  };
}

function capitalize(value) {
  return value ? value[0].toUpperCase() + value.slice(1) : "Unknown";
}

function pill(label, value) {
  if (value === null || value === undefined) return null;
  const node = document.createElement("span");
  node.className = "pill";
  node.textContent = `${label}: ${Number(value).toFixed(2)} credits`;
  return node;
}

function renderMedia() {
  media.replaceChildren();
  if (!view?.artifactUrl) {
    const placeholder = document.createElement("div");
    placeholder.className = "placeholder";
    if (!terminal.has(view?.status)) {
      const spinner = document.createElement("span");
      spinner.className = "spinner";
      placeholder.appendChild(spinner);
    }
    const text = document.createElement("span");
    text.textContent = view?.analysis
      ? "Analysis complete"
      : view?.status === "failed"
        ? "Generation failed"
        : view?.status === "canceled"
          ? "Generation canceled"
          : "Generating your media…";
    placeholder.appendChild(text);
    media.appendChild(placeholder);
    return;
  }
  let element;
  if (view.kind === "video") {
    element = document.createElement("video");
    element.controls = true;
    element.playsInline = true;
  } else if (view.kind === "audio") {
    element = document.createElement("audio");
    element.controls = true;
  } else {
    element = document.createElement("img");
    element.alt = view.title;
  }
  element.src = view.artifactUrl;
  media.appendChild(element);
}

function schedulePoll() {
  window.clearTimeout(pollTimer);
  if (!view?.job.jobId || view.local || terminal.has(view.status) || document.hidden) return;
  pollTimer = window.setTimeout(refreshJob, POLL_INTERVAL_MS);
}

function render() {
  if (!view) return;
  card.dataset.status = view.status;
  title.textContent = view.title;
  subtitle.textContent = view.subtitle;
  status.textContent = capitalize(view.status);
  analysis.hidden = !view.analysis;
  analysis.textContent = view.analysis || "";
  error.hidden = !view.error;
  error.textContent = view.error || "";
  credits.replaceChildren(
    ...[
      pill("Estimated", view.job.estimatedCredits),
      pill("Final", view.job.finalCredits),
    ].filter(Boolean),
  );
  refresh.hidden = view.local || !view.job.jobId || terminal.has(view.status);
  cancel.hidden = view.local || view.status !== "running";
  open.hidden = !view.artifactUrl;
  renderMedia();
  schedulePoll();
}

function ingest(result) {
  const next = normalize(resultData(result) || result);
  if (next) {
    view = next;
    render();
  }
}

async function callTool(name, args) {
  const result = await app.callServerTool({ name, arguments: args });
  if (result?.isError) throw new Error(result.content?.[0]?.text || "Tool call failed");
  ingest(result);
}

async function refreshJob() {
  if (!view?.job.jobId || view.local || terminal.has(view.status)) return;
  refresh.disabled = true;
  try {
    await callTool(GET_JOB_TOOL, { jobId: view.job.jobId });
  } catch (cause) {
    error.hidden = false;
    error.textContent = cause instanceof Error ? cause.message : "Unable to refresh this job.";
  } finally {
    refresh.disabled = false;
  }
}

refresh.addEventListener("click", refreshJob);
cancel.addEventListener("click", async () => {
  if (!view?.job.jobId || view.local) return;
  cancel.disabled = true;
  try {
    await callTool(CANCEL_JOB_TOOL, { jobId: view.job.jobId });
  } catch (cause) {
    error.hidden = false;
    error.textContent = cause instanceof Error ? cause.message : "Unable to cancel this job.";
  } finally {
    cancel.disabled = false;
  }
});
open.addEventListener("click", async () => {
  if (!view?.artifactUrl) return;
  try {
    await app.openLink({ url: view.artifactUrl });
  } catch (cause) {
    error.hidden = false;
    error.textContent = cause instanceof Error ? cause.message : "Unable to open this media.";
  }
});
document.addEventListener("visibilitychange", schedulePoll);

(async function connect() {
  app = new App(
    { name: "AdAnt Media", version: "2.0.0" },
    { availableDisplayModes: ["inline", "fullscreen"], autoResize: true },
  );
  app.ontoolresult = ingest;
  await app.connect();
  await refreshJob();
})().catch((cause) => {
  error.hidden = false;
  error.textContent = cause instanceof Error ? cause.message : "Unable to connect the media preview.";
});
