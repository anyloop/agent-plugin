import { createHash } from "node:crypto";
import {
  mkdirSync,
  readFileSync,
  readdirSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { spawnSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const widgetRoot = dirname(fileURLToPath(import.meta.url));
const repositoryRoot = resolve(widgetRoot, "../../..");
const configPath = resolve(widgetRoot, "vite.config.ts");
const destinations = [
  resolve(repositoryRoot, "plugins/adant/local-server/src/adant_local/assets"),
  resolve(
    repositoryRoot,
    "plugins/adant-claude/local-server/src/adant_local/assets",
  ),
];
const serverWidgetDestination = resolve(
  repositoryRoot,
  "apps/server/src/mcp/generated/media-preview-widget.json",
);
const checkOnly = process.env.ADANT_WIDGET_CHECK === "1";
const widgets = [
  { key: "researchProgress", base: "research-progress" },
  { key: "mediaPreview", base: "media-preview" },
];

function build(base) {
  const result = spawnSync(
    "pnpm",
    ["exec", "vite", "build", "--config", configPath],
    {
      cwd: repositoryRoot,
      env: { ...process.env, ADANT_WIDGET: base },
      stdio: "inherit",
    },
  );
  if (result.status !== 0) process.exit(result.status ?? 1);
  const bundledHtml = readFileSync(
    resolve(widgetRoot, ".build", base, `${base}.html`),
    "utf8",
  );
  const html = Buffer.from(bundledHtml.replace(/[\t ]+$/gm, ""));
  const sha256 = createHash("sha256").update(html).digest("hex");
  return { file: `${base}.${sha256.slice(0, 12)}.html`, sha256, html };
}

const built = Object.fromEntries(
  widgets.map(({ key, base }) => [key, build(base)]),
);
const manifest = `${JSON.stringify(
  Object.fromEntries(
    widgets.map(({ key }) => [
      key,
      { file: built[key].file, sha256: built[key].sha256 },
    ]),
  ),
  null,
  2,
)}\n`;

for (const destination of destinations) {
  if (checkOnly) {
    for (const { key } of widgets) {
      const current = readFileSync(resolve(destination, built[key].file));
      if (!current.equals(built[key].html)) {
        throw new Error(`widget asset is stale in ${destination}`);
      }
    }
    if (
      readFileSync(resolve(destination, "widget-manifest.json"), "utf8") !==
      manifest
    ) {
      throw new Error(`widget manifest is stale in ${destination}`);
    }
    continue;
  }
  mkdirSync(destination, { recursive: true });
  for (const entry of readdirSync(destination)) {
    if (/^(research-progress|media-preview)\.[a-f0-9]{12}\.html$/.test(entry)) {
      rmSync(resolve(destination, entry));
    }
  }
  for (const { key } of widgets) {
    writeFileSync(resolve(destination, built[key].file), built[key].html);
  }
  writeFileSync(resolve(destination, "widget-manifest.json"), manifest);
}

const serverWidget = `${JSON.stringify({
  file: built.mediaPreview.file,
  sha256: built.mediaPreview.sha256,
  html: built.mediaPreview.html.toString("utf8"),
})}\n`;
if (checkOnly) {
  if (readFileSync(serverWidgetDestination, "utf8") !== serverWidget) {
    throw new Error("server media-preview widget is stale");
  }
} else {
  mkdirSync(dirname(serverWidgetDestination), { recursive: true });
  writeFileSync(serverWidgetDestination, serverWidget);
}
