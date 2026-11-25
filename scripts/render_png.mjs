// Render a local SVG or HTML file to PNG with the Playwright browser.
//   cd frontend && node ../scripts/render_png.mjs <input> <output> <width> <height>
import { createRequire } from "node:module";
import { resolve } from "node:path";

const require = createRequire(resolve(process.cwd(), "package.json"));
const { chromium } = require("@playwright/test");

const [input, output, width, height] = process.argv.slice(2);
const browser = await chromium.launch();
const page = await browser.newPage({
  viewport: { width: Number(width), height: Number(height) || 100 },
  deviceScaleFactor: 2,
});
await page.goto(`file://${resolve(input)}`);
// A height of 0 captures the whole page, however tall it is.
await page.screenshot({ path: resolve(output), fullPage: Number(height) === 0 });
await browser.close();
