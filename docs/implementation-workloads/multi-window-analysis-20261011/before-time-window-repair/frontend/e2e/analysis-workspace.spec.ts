import {test,expect,type Page} from 'playwright/test';
import {randomUUID} from 'node:crypto';

async function imported(page:Page,view:string='messages') {
  const project='nis-e2e-multi-window-'+randomUUID();
  await page.goto(`/trace-analysis?project=${project}`);
  const buffer=Buffer.from(Array.from({length:20},(_,i)=>JSON.stringify({time_s:i/10,time_basis:'clock-a',message_id:'pressure-message',message_name:'Druckbericht',source_name:'Sensor',destination_names:['Controller'],status:i===3?'dropped':'transmitted',faults:i===3?['MESSAGE_LOSS']:[],signals:[{signal_id:'pressure',signal:'Druck',value:i,unit:'bar',quality:'VALID'}]})).join('\n'));
  await page.locator('input[type=file]').setInputFiles({name:'workspace.jsonl',mimeType:'application/octet-stream',buffer});
  await expect(page).toHaveURL(/import=/);
  const url=new URL(page.url());url.searchParams.set('view',view);await page.goto(url.toString());
  await expect(page.locator('.trace-control-panel')).toContainText('20 Ereignisse im Speicher');
  return project;
}
async function open(page:Page,view:string,independent=false) {
  const tools=page.getByRole('region',{name:'Analysefenster und Arbeitsbereich'});
  await tools.getByRole('combobox',{name:'Ansicht',exact:true}).selectOption(view);
  const popup=page.waitForEvent('popup');
  await tools.getByRole('button',{name:independent?'Unabhängig öffnen':'↗ In neuem Fenster öffnen',exact:true}).click();
  const secondary=await popup;await secondary.waitForLoadState('domcontentloaded');
  await expect(secondary.locator('.trace-control-panel > p').filter({hasText:'Ereignisse im Speicher'})).toHaveText(/^[1-9]\d* Ereignisse im Speicher/);
  return secondary;
}
test('E2E-01 sequence selection focuses the corresponding original signals across windows',async({page})=>{
  const project=await imported(page,'sequence');const signals=await open(page,'signals');
  await page.locator('.e2e-sequence-event').nth(3).click();
  await expect(signals.getByLabel('Gemeinsamer Trace-Kontext',{exact:true})).toContainText('Druckbericht');
  await expect(signals.getByLabel('Signal-Analyse',{exact:true})).toContainText('Druck');
  await expect(signals.getByLabel('Gemeinsamer Zeitcursor')).toContainText('0.3 s');
  expect(new URL(signals.url()).searchParams.get('project')).toBe(project);
  await signals.getByLabel('Fensterkopplung').selectOption('INDEPENDENT');
  await page.locator('.e2e-sequence-event').nth(5).click();
  await expect(signals.getByLabel('Gemeinsamer Zeitcursor')).toContainText('0.3 s');
  await signals.getByLabel('Fensterkopplung').selectOption('FOLLOW_PRIMARY');
  await expect(signals.getByLabel('Gemeinsamer Zeitcursor')).toContainText('0.5 s');
});
test('E2E-02 bus-load time filter restricts the coupled original event window',async({page})=>{
  await imported(page,'load');const events=await open(page,'events');
  await page.getByLabel('Von (s)',{exact:true}).fill('0.4');await page.getByLabel('Bis (s)',{exact:true}).fill('0.8');
  await expect(events.getByLabel('Von (s)',{exact:true})).toHaveValue('0.4');await expect(events.getByLabel('Bis (s)',{exact:true})).toHaveValue('0.8');
  const times=await events.locator('.trace-table tbody tr td:first-child button').allTextContents();
  expect(times.length).toBeGreaterThan(0);for(const text of times){const t=parseFloat(text);expect(t).toBeGreaterThanOrEqual(.4);expect(t).toBeLessThanOrEqual(.8);}
});
test('E2E-03 an original finding builds a readable root-cause context, never an invented cause',async({page})=>{
  await imported(page,'findings');const root=await open(page,'root-cause');
  await page.getByRole('button',{name:'Ereigniskontext',exact:true}).first().click();
  await expect(root.getByLabel('Gemeinsamer Trace-Kontext',{exact:true})).toContainText('Druckbericht');
  await expect(root.getByLabel('Gemeinsamer Zeitcursor')).toContainText('0.3 s');
  await expect(root.locator('.trace-control-panel')).toContainText('zeitliche Nachbarschaft allein beweist keine Ursache');
});
async function run(page:Page,project:string,fault:boolean) {
  const config={name:fault?'Fault reference':'Golden reference',duration_s:.08,seed:42,max_events:1000,formats:['universal-jsonl'],networks:[{id:'can-main',name:'Virtueller CAN',technology:'can_fd',bitrate:500000,arbitration_bitrate:500000,data_bitrate:2000000}],hardware:{devices:[{id:'sensor',name:'Sensor',type:'sensor',ports:[{id:'p1',physical_type:'can',network_interfaces:[{id:'if-sensor',technology:'can_fd',network:'can-main'}]}]},{id:'ecu',name:'ECU',type:'ecu',ports:[{id:'p2',physical_type:'can',network_interfaces:[{id:'if-ecu',technology:'can_fd',network:'can-main'}]}]}]},communications:[{id:'route-temperature',name:'Temperaturpfad',sender_interface:'if-sensor',receiver_interfaces:['if-ecu'],network:'can-main',technology:'can_fd',cycle_ms:10,payload_bytes:8,signal_ids:['sig-temperature']}],engineering_model:{messages:[{id:'msg-1',name:'Temperaturbericht',cycle_ms:10,interface_id:'if-sensor'}],signals:[{id:'sig-temperature',name:'Temperature',message_id:'msg-1',start_bit:0,length_bits:16,byte_order:'little_endian',factor:.1,offset_value:-40,unit:'degC',min_value:-40,max_value:215,communication:{cycle_ms:10},configuration:{resolution:.1}}],behaviors:[{signal_id:'sig-temperature',behavior_type:'SINE',model_label:'RULE_BASED',parameters:{period_s:1}}]},scenario:{name:fault?'Fault':'Golden',mode:fault?'USER_DEFINED_FAULT':'NORMAL',faults:fault?[{id:'fault',scope:'MESSAGE',type:'MESSAGE_LOSS',target:{route_id:'route-temperature'},start_s:0,end_s:.08,magnitude:1,source:'user',approved:true}]:[]}};
  const headers={'X-Project-ID':project};const response=await page.request.post('/api/simulations',{headers,data:{config}});expect(response.status(),await response.text()).toBe(202);const id=(await response.json()).id;
  await expect.poll(async()=>(await(await page.request.get(`/api/simulations/${id}?view=metadata`,{headers})).json()).status,{timeout:90000}).toBe('completed');return id as string;
}
test('E2E-04 real Golden and Fault runs stay separate and expose original differences',async({page})=>{
  const project='nis-e2e-compare-'+randomUUID(),golden=await run(page,project,false),fault=await run(page,project,true);
  await page.goto(`/trace-analysis?project=${project}&job=${golden}&view=trace`);
  await expect(page.locator('.trace-control-panel > p').filter({hasText:'Ereignisse im Speicher'})).toHaveText(/^[1-9]\d* Ereignisse im Speicher/);
  const popup=page.waitForEvent('popup');await page.getByRole('button',{name:'⇄ Vergleich öffnen',exact:true}).click();const compare=await popup;
  await compare.getByLabel('Rechter Vergleichslauf').selectOption(fault);
  await expect(compare.locator('.analysis-difference').first()).toBeVisible();
  await expect(compare.getByLabel('Linker Vergleichslauf')).toHaveValue(golden);
  await page.getByLabel('Von (s)',{exact:true}).fill('0.04');
  await expect(compare.getByLabel('Linker Vergleichslauf')).toHaveValue(golden);await expect(compare.getByLabel('Rechter Vergleichslauf')).toHaveValue(fault);
  const other=await compare.request.get(`/api/simulations/${golden}?view=metadata`,{headers:{'X-Project-ID':'foreign-'+project}});expect(other.status()).toBe(404);
});
test('E2E-05 restored simulation cursor follows into a bounded read-only trace window',async({page})=>{
  const project='nis-e2e-sim-window-'+randomUUID(),id=await run(page,project,false);
  await page.goto(`/studio/simulation?project=${project}&job=${id}`);
  const time=page.getByLabel('Simulationszeit',{exact:true});
  await expect(time).toHaveAttribute('max','0.08');
  await expect(page.locator('.simulation-timeline')).toContainText('PAUSED');
  const trace=await open(page,'trace');
  await page.bringToFront();
  await time.focus();await time.press('Home');
  await expect(time).toHaveValue('0');
  for(let i=0;i<30;i++){
    await time.press('ArrowRight');
    await expect(time).toHaveValue(String((i+1)/1000));
  }
  await expect(time).toHaveValue('0.03');
  await expect(page.getByLabel('Gemeinsamer Zeitcursor')).toContainText('0.03 s');
  await expect(trace.getByLabel('Gemeinsamer Zeitcursor')).toContainText('0.03 s');
  expect(await trace.locator('.simulation-command-bar').count()).toBe(0);
  const headers={'X-Project-ID':project};expect((await(await page.request.get('/api/simulations',{headers})).json()).jobs).toHaveLength(1);
});
test('E2E-06 signal selection reaches the analysis assistant; profiles restore only views; ending the session clears all windows',async({page})=>{
  await imported(page,'signals');const assistant=await open(page,'assistant');
  await page.getByRole('button',{name:/Druck: .*; 0.4/}).first().click();
  await expect(assistant.locator('.analysis-assistant-context')).toContainText('pressure');await expect(assistant.getByLabel('Gemeinsamer Zeitcursor')).toContainText('0.4 s');
  const tools=page.getByRole('region',{name:'Analysefenster und Arbeitsbereich'});await tools.getByText(/Arbeitsbereiche und Fenster/).click();await tools.getByLabel('Profilname').fill('Signals + Assistant');await tools.getByRole('button',{name:'Arbeitsbereich speichern',exact:true}).click();await expect(tools.getByLabel('Gespeichertes Profil')).toContainText('Signals + Assistant');
  const popup=page.waitForEvent('popup');await tools.getByRole('button',{name:'Arbeitsbereich wiederherstellen',exact:true}).click();const restored=await popup;await expect(restored.locator('.analysis-assistant-context')).toContainText('pressure');
  await tools.getByRole('button',{name:'Analysesitzung in allen Fenstern beenden',exact:true}).click();await expect(assistant.getByLabel('Gemeinsamer Zeitcursor')).toContainText('Unbekannt');await expect(restored.getByRole('region',{name:'Analysefenster und Arbeitsbereich'})).toContainText('Sitzung beendet');
});
