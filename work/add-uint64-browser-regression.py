from pathlib import Path
p=Path('frontend/src/lib/technology-parameters.test.mjs');s=p.read_text(encoding='utf-8').replace('sp_alias','spb_alias');p.write_text(s,encoding='utf-8')
p=Path('frontend/e2e/technology-parameter-review.spec.ts');s=p.read_text(encoding='utf-8');s+='''

test('actual uint64 protocol value survives legacy numeric JSON, form edit, SQL persistence and reload @technology-review', async ({page}) => {
  const project = 'nis-e2e-uint64-' + randomUUID();
  const headers = {'X-Project-ID':project,'Content-Type':'application/json'};
  const initial = await (await page.request.get('/api/engineering/workflow/parameters',{headers})).json();
  const maximum = '18446744073709551615';
  const seed = JSON.stringify({parameters:{industry:'custom',technology:'sparkplug_b',spb_alias:'__EXACT_INTEGER__',
    parameter_provenance:{spb_alias:{value:'__EXACT_INTEGER__',source:'USER_CONFIRMED',status:'CONFIRMED'}}},expected_token:initial.edit_token})
    .replaceAll('"__EXACT_INTEGER__"', maximum);
  const seeded = await page.request.patch('/api/engineering/workflow/parameters',{headers,data:seed});
  expect(seeded.ok(),await seeded.text()).toBe(true);
  await page.goto(`/studio?mode=parameters&project=${project}`);
  await expect(page.locator('#technology')).toHaveValue('sparkplug_b');
  await expect(page.locator('#spb_alias')).toHaveAttribute('type','text');
  await expect(page.locator('#spb_alias')).toHaveValue(maximum);
  const catalog = await (await page.request.get('/api/technologies')).json();
  const profile = catalog.domains.flatMap((d:{technologies:Array<{id:string}>})=>d.technologies).find((p:{id:string})=>p.id==='sparkplug_b');
  for (const field of profile.parameter_schema.filter((f:{required?:boolean,type:string})=>f.required&&f.type==='text')) {
    await page.locator(`[name="${field.key}"]`).fill('isolated-test-source');
  }
  const edited = '18446744073709551614';
  await page.locator('#spb_alias').fill(edited);
  await page.getByRole('button',{name:'Parameter speichern →',exact:true}).click();
  await expect(page.getByText('Technologie- und Timing-Parameter gespeichert.')).toBeVisible();
  const saved = await (await page.request.get('/api/engineering/workflow/parameters',{headers})).json();
  expect(saved.parameters.technology_parameters.sparkplug_b.values.spb_alias).toBe(edited);
  expect(saved.parameters.technology_parameters.sparkplug_b.provenance.spb_alias.value).toBe(edited);
  await page.reload();
  await expect(page.locator('#spb_alias')).toHaveValue(edited);
});
''';p.write_text(s,encoding='utf-8')
