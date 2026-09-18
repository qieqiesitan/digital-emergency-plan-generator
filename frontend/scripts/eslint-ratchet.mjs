#!/usr/bin/env node
/**
 * ESLint 债务棘轮：允许历史遗留错误存在，但**不允许增加**。
 *
 * 背景：前端有 245 条历史 eslint error（26 个 @ts-nocheck 文件、56 处 any、
 * 41 处 react-hooks/refs 等）。一次性清零需要大规模补类型，不能阻塞日常交付；
 * 但"新代码继续加债"必须被拦住，否则永远还不完。
 *
 * 用法：
 *   node scripts/eslint-ratchet.mjs            # CI/本地检查：超过基线即失败
 *   node scripts/eslint-ratchet.mjs --update   # 债务减少后刷新基线
 */
import { ESLint } from "eslint";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const baselinePath = resolve(here, "..", "eslint-baseline.json");
const update = process.argv.includes("--update");

const eslint = new ESLint({ cwd: resolve(here, ".."), errorOnUnmatchedPattern: false });
const results = await eslint.lintFiles(["."]);

let errors = 0;
let warnings = 0;
const byRule = {};
for (const file of results) {
  for (const msg of file.messages) {
    const key = `${msg.severity === 2 ? "error" : "warning"}:${msg.ruleId ?? "parse"}`;
    byRule[key] = (byRule[key] ?? 0) + 1;
    if (msg.severity === 2) errors += 1;
    else warnings += 1;
  }
}

const current = { errors, warnings, byRule, recordedAt: new Date().toISOString().slice(0, 10) };

if (update) {
  writeFileSync(baselinePath, `${JSON.stringify(current, null, 2)}\n`, "utf8");
  console.log(`已更新 eslint 基线：errors=${errors} warnings=${warnings}`);
  process.exit(0);
}

let baseline;
try {
  baseline = JSON.parse(readFileSync(baselinePath, "utf8"));
} catch {
  console.error("缺少 eslint-baseline.json；先执行 node scripts/eslint-ratchet.mjs --update");
  process.exit(1);
}

const regressions = [];
for (const [key, count] of Object.entries(byRule)) {
  const allowed = baseline.byRule?.[key] ?? 0;
  if (count > allowed) regressions.push(`${key}: ${allowed} → ${count}`);
}
if (errors > baseline.errors) regressions.push(`errors 总数: ${baseline.errors} → ${errors}`);
if (warnings > baseline.warnings) regressions.push(`warnings 总数: ${baseline.warnings} → ${warnings}`);

const improved = baseline.errors - errors;
console.log(`eslint 棘轮：errors=${errors}（基线 ${baseline.errors}）warnings=${warnings}（基线 ${baseline.warnings}）`);
if (regressions.length > 0) {
  console.error("新增债务，请修掉后再提交（或先在本地把基线内的问题解决）：");
  for (const item of regressions) console.error(`  - ${item}`);
  process.exit(1);
}
if (improved > 0) {
  console.log(`债务已减少 ${improved} 条，可执行 node scripts/eslint-ratchet.mjs --update 收紧基线。`);
}
console.log("未新增债务 ✅");
