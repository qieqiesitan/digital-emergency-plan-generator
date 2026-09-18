#!/usr/bin/env node
/**
 * 源码卫生检查：src/ 下不得出现 UTF-8 BOM。
 *
 * 背景：本项目历史上因 BOM 出过事故（shell 脚本 shebang 失效；package-release.sh
 * 专门做过去 BOM 规范化）。BOM 还会让 apply_patch / diff 这类按字节匹配的工具
 * 行为异常——2026-09-18 修复 lint 债务时就撞到过（Toast.tsx 带 BOM 导致补丁打不上）。
 *
 * 用法：node scripts/check-source-hygiene.mjs（CI 阻塞）
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join, relative, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");
const scanDirs = [join(root, "src")];
const exts = [".ts", ".tsx", ".css", ".js", ".jsx", ".mjs"];

/** @type {string[]} */
const offenders = [];
let scanned = 0;

function walk(dir) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      walk(full);
      continue;
    }
    if (!exts.some((ext) => entry.endsWith(ext))) continue;
    scanned += 1;
    const head = readFileSync(full).subarray(0, 3);
    if (head[0] === 0xef && head[1] === 0xbb && head[2] === 0xbf) {
      offenders.push(relative(root, full).replace(/\\/g, "/"));
    }
  }
}

for (const dir of scanDirs) {
  try {
    walk(dir);
  } catch (err) {
    if (err.code !== "ENOENT") throw err;
  }
}

if (offenders.length > 0) {
  console.error(`发现 ${offenders.length} 个带 UTF-8 BOM 的源文件（必须去除）：`);
  for (const file of offenders) console.error(`  - ${file}`);
  process.exit(1);
}

console.log(`源码卫生检查通过：${scanned} 个文件无 BOM`);
