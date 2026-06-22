import { test, expect } from '@playwright/test';

const BASE = 'http://localhost:5173';
const API = 'http://localhost:8000/api/v1';
const U = 'qa_e2e_test@test.com';
const P = 'test123456';

async function login(p: any) {
  await p.goto(BASE + '/login');
  await p.fill('input[id*="email"]', U);
  await p.fill('input[type="password"]', P);
  await p.click('button[type="submit"]');
  await p.waitForURL(/\/(enterprises|dashboard)/, { timeout: 10000 });
}

test.describe('Auth', () => {
  test('login succeeds', async ({ page }) => {
    await login(page);
    await expect(page).toHaveURL(/\/(enterprises|dashboard)/);
  });
});

test.describe('Enterprise CRUD', () => {
  test('list page loads', async ({ page }) => {
    await login(page);
    await expect(page.locator('body')).toContainText(/企业/);
  });
  test('create page opens', async ({ page }) => {
    await login(page);
    await page.goto(BASE + '/enterprises');
    await page.click('text=新建企业');
    await expect(page).toHaveURL(/\/enterprises\/new/);
  });
});

test.describe('Detail', () => {
  test('detail tabs visible', async ({ page, request }) => {
    const r = await request.post(API + '/auth/login', { data: { email: U, password: P } });
    const t = (await r.json()).data.access_token;
    const r2 = await request.post(API + '/enterprises', { headers: { Authorization: 'Bearer ' + t }, data: { name: 'E2E_' + Date.now() } });
    const ent = (await r2.json()).data;
    await login(page);
    await page.goto(BASE + '/enterprises/' + ent.id);
    await expect(page.locator('text=基本信息')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('text=组织架构')).toBeVisible();
    await expect(page.locator('text=风险源')).toBeVisible();
    await expect(page.locator('text=应急资源')).toBeVisible();
    await expect(page.locator('text=周边环境')).toBeVisible();
  });
  test('org editor modal opens', async ({ page, request }) => {
    const r = await request.post(API + '/auth/login', { data: { email: U, password: P } });
    const t = (await r.json()).data.access_token;
    const r2 = await request.post(API + '/enterprises', { headers: { Authorization: 'Bearer ' + t }, data: { name: 'E2E_Org_' + Date.now() } });
    const ent = (await r2.json()).data;
    await login(page);
    await page.goto(BASE + '/enterprises/' + ent.id);
    await page.click('text=组织架构'); await page.waitForTimeout(500);
    await page.click('text=编辑组织架构'); await page.waitForTimeout(1000);
    await expect(page.locator('.ant-modal-title')).toBeVisible({ timeout: 5000 });
  });
  test('surrounding editor modal opens', async ({ page, request }) => {
    const r = await request.post(API + '/auth/login', { data: { email: U, password: P } });
    const t = (await r.json()).data.access_token;
    const r2 = await request.post(API + '/enterprises', { headers: { Authorization: 'Bearer ' + t }, data: { name: 'E2E_Surr_' + Date.now() } });
    const ent = (await r2.json()).data;
    await login(page);
    await page.goto(BASE + '/enterprises/' + ent.id);
    await page.click('text=周边环境'); await page.waitForTimeout(500);
    await page.click('text=编辑周边环境'); await page.waitForTimeout(1000);
    await expect(page.locator('.ant-modal-title')).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Risk/Resource', () => {
  test('add risk source modal opens', async ({ page, request }) => {
    const r = await request.post(API + '/auth/login', { data: { email: U, password: P } });
    const t = (await r.json()).data.access_token;
    const r2 = await request.post(API + '/enterprises', { headers: { Authorization: 'Bearer ' + t }, data: { name: 'E2E_Risk_' + Date.now() } });
    const ent = (await r2.json()).data;
    await login(page); await page.goto(BASE + '/enterprises/' + ent.id);
    await page.click('text=风险源'); await page.waitForTimeout(500);
    await page.click('text=添加风险源'); await page.waitForTimeout(1000);
    await expect(page.locator('.ant-modal-title')).toBeVisible({ timeout: 5000 });
  });
  test('add resource modal opens', async ({ page, request }) => {
    const r = await request.post(API + '/auth/login', { data: { email: U, password: P } });
    const t = (await r.json()).data.access_token;
    const r2 = await request.post(API + '/enterprises', { headers: { Authorization: 'Bearer ' + t }, data: { name: 'E2E_Res_' + Date.now() } });
    const ent = (await r2.json()).data;
    await login(page); await page.goto(BASE + '/enterprises/' + ent.id);
    await page.click('text=应急资源'); await page.waitForTimeout(500);
    await page.click('text=添加资源'); await page.waitForTimeout(1000);
    await expect(page.locator('.ant-modal-title')).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Page Access', () => {
  test('plans', async ({ page }) => { await login(page); await page.goto(BASE + '/plans'); await expect(page.locator('body')).toBeVisible(); });
  test('settings', async ({ page }) => { await login(page); await page.goto(BASE + '/settings'); await expect(page.locator('body')).toBeVisible(); });
  test('dashboard', async ({ page }) => { await login(page); await page.goto(BASE + '/dashboard'); await expect(page.locator('body')).toBeVisible(); });
});