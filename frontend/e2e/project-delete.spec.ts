import { test, expect } from 'playwright/test';
import { randomUUID } from 'node:crypto';

test('gallery trash confirms exact project, persists deletion and preserves its neighbour', async ({ page }) => {
  const project = 'nis-e2e-delete-' + randomUUID();
  const other = 'nis-e2e-keep-' + randomUUID();
  for (const id of [project, other]) {
    const response = await page.request.patch('/api/engineering/workflow/context', { headers:{'X-Project-ID':id},
      data:{engineering_wizard_settings:{project_name:id,model_type:'custom'}} });
    expect(response.ok()).toBe(true);
  }
  const saved = await page.request.post('/api/engineering/projects/save', {headers:{'X-Project-ID':project},data:{}});
  expect(saved.ok()).toBe(true);
  expect((await saved.json()).path).toContain(`${project}/project.nis-project.json`);
  await page.goto('/projects');
  page.once('dialog', dialog => dialog.dismiss());
  await page.getByRole('button', {name:`Projekt ${project} löschen`,exact:true}).click();
  await expect(page.getByRole('link').filter({hasText:project})).toBeVisible();
  page.once('dialog', async dialog => { expect(dialog.message()).toContain(project); await dialog.accept(); });
  await page.getByRole('button', {name:`Projekt ${project} löschen`,exact:true}).click();
  await expect(page.getByRole('button', {name:`Projekt ${project} löschen`,exact:true})).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole('link').filter({hasText:project})).toHaveCount(0);
  await expect(page.getByRole('link').filter({hasText:other})).toBeVisible();
  const stale = await page.request.patch('/api/engineering/workflow/context', {headers:{'X-Project-ID':project},data:{}});
  expect(stale.status()).toBe(400);
});
