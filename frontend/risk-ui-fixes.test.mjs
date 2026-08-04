import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)));

function readSource(relativePath) {
  return fs.readFileSync(path.join(root, relativePath), "utf8");
}

function readRootFile(relativePath) {
  return fs.readFileSync(path.join(path.resolve(root, ".."), relativePath), "utf8");
}

test("routes register risk overview and risk method pages", () => {
  const src = readSource("src/routes/index.tsx");
  assert.match(src, /RiskOverviewPage/);
  assert.match(src, /RiskMethodListPage/);
  assert.match(src, /RiskMethodEditorPage/);
  assert.match(src, /\/enterprises\/:id\/risk-overview/);
  assert.match(src, /\/enterprises\/:id\/risk-methods/);
  assert.match(src, /\/enterprises\/:id\/risk-methods\/:methodId/);
});

test("risk management tab navigates to registered risk routes", () => {
  const src = readSource("src/pages/Enterprise/RiskManagementTab.tsx");
  assert.match(src, /risk-overview/);
  assert.match(src, /risk-methods/);
});

test("risk hierarchy tree uses valid emoji escapes", () => {
  const src = readSource("src/components/enterprise/RiskHierarchyTree.tsx");
  assert.doesNotMatch(src, /\\U0001F/);
});

test("risk hierarchy tree exposes inline action buttons", () => {
  const src = readSource("src/components/enterprise/RiskHierarchyTree.tsx");
  assert.match(src, /onAction:\s*\(action: string, meta: TreeNodeMeta\) => void/);
  assert.match(src, /onAction\(action\.key, meta\)/);
  assert.match(src, /"add-object"/);
  assert.match(src, /"edit"/);
  assert.match(src, /"delete"/);
});

test("smart guide modal uses plain Chinese title", () => {
  const src = readSource("src/components/enterprise/RiskSmartGuideModal.tsx");
  assert.match(src, /title="AI 智能生成风险层级"/);
});

test("risk management tab handles generic edit/delete and defaults object zone", () => {
  const src = readSource("src/pages/Enterprise/RiskManagementTab.tsx");
  assert.match(src, /case "edit":/);
  assert.match(src, /case "delete":/);
  assert.match(src, /initialValues: \{ zone_id: meta\.id \}/);
  assert.match(src, /initialValues=\{form\.initialValues\}/);
});

test("smart guide backend accepts preview hierarchy without database ids", () => {
  const schema = readRootFile("backend/app/schemas/risk_management.py");
  const service = readRootFile("backend/app/services/risk_ai_service.py");
  assert.match(schema, /class SmartGuideZone/);
  assert.match(service, /_normalize_smart_guide_hierarchy/);
});
