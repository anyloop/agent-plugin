import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import { viteSingleFile } from "vite-plugin-singlefile";

const widgetRoot = dirname(fileURLToPath(import.meta.url));
const widget = process.env.ADANT_WIDGET;
if (widget !== "research-progress" && widget !== "media-preview") {
  throw new Error("ADANT_WIDGET must be research-progress or media-preview");
}

export default defineConfig({
  root: widgetRoot,
  plugins: [viteSingleFile()],
  build: {
    emptyOutDir: true,
    minify: true,
    outDir: resolve(widgetRoot, ".build", widget),
    rollupOptions: { input: resolve(widgetRoot, `${widget}.html`) },
  },
});
