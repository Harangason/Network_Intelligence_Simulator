import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
const base=process.env.SIMULATOR_TEST_URL;
if(!base) throw new Error('SIMULATOR_TEST_URL must select an isolated test instance.');
const out=fileURLToPath(new URL('../../backend/test-output/',import.meta.url));
const project='network-project-chat-ux-'+Date.now();
const report={project,checks:[],errors:[]};const browsers=[];
try {
 for(const channel of ['chrome','msedge']) browsers.push(await chromium.launch({channel,headless:true}));
 const a=await browsers[0].newPage({viewport:{width:1440,height:1000}}), b=await browsers[1].newPage();
 const submissions=[];
 a.on('request',request=>{if(request.url().endsWith('/api/agent/chat')&&request.method()==='POST')submissions.push(request.postDataJSON());});
 for(const page of [a,b])page.on('pageerror',error=>report.errors.push(error.message));
 const url=`${base}/studio/engineering?project=${project}`;
 await a.goto(url);await a.getByRole('button',{name:'AI Assistant öffnen',exact:true}).click();
 await a.getByText('Architektur erstellen',{exact:true}).waitFor();
 await a.getByRole('textbox',{name:'Nachricht an den Engineering-Assistenten'}).fill('Erstelle eine Kamerafunktion zur Überwachung der Umgebung');
 await a.getByRole('button',{name:'Senden',exact:true}).click();
 const first=a.locator('.agent-widget-panel .engineering-question-card').last();
 await first.getByRole('radio',{name:/360°/}).waitFor({timeout:60000});
 assert.equal(await first.getByRole('radio',{name:/360°/}).isChecked(),true);
 await first.getByRole('radio',{name:'Frontbereich',exact:true}).check();
 assert.equal(await first.getByRole('radio',{name:/360°/}).isChecked(),false);
 await first.getByRole('radio',{name:/360°/}).check();
 await first.getByText('Warum?',{exact:true}).click();
 await a.screenshot({path:out+'chat-ux-question.png'});
 await first.getByRole('button',{name:'Auswahl übernehmen',exact:true}).click();
 await a.getByRole('checkbox',{name:/Objektliste/}).waitFor({timeout:30000});
 report.checks.push('Single select exclusive, recommended preselection, rationale, structured answer resumes multi-select');
 await a.waitForTimeout(1200);
 await b.goto(url);await b.getByRole('button',{name:'AI Assistant öffnen',exact:true}).click();
 await b.getByRole('checkbox',{name:/Objektliste/}).waitFor({timeout:30000});
 assert.equal(await b.locator('.agent-widget-panel .engineering-question-card').first().getByRole('button',{name:'Auswahl übernehmen'}).isDisabled(),true);
 report.checks.push('Edge resumes the same durable conversation; already answered question disabled');
 const multi=a.locator('.agent-widget-panel .engineering-question-card').last();
 const free=multi.getByRole('checkbox',{name:/Freiraum/});await free.click();assert.equal(await free.isChecked(),false);await free.press('Space');
 await multi.getByRole('button',{name:'Auswahl übernehmen'}).click();
 await a.getByRole('radio',{name:/Vier Weitwinkelkameras/}).waitFor({timeout:30000});
 await a.locator('.agent-widget-panel .engineering-question-card').last().getByRole('button',{name:'Auswahl übernehmen'}).click();
 await a.getByRole('radio',{name:/Vorschlag erstellen/}).waitFor({timeout:30000});
 await a.locator('.agent-widget-panel .engineering-question-card').last().getByRole('button',{name:'Auswahl übernehmen'}).click();
 await a.getByRole('button',{name:'Vorschlag freigeben',exact:true}).waitFor({timeout:60000});
 assert.equal(submissions.filter(s=>s.input).length,4);
 for(const s of submissions.filter(s=>s.input)){assert.equal(s.input.type,'QUESTION_ANSWER');assert.ok(s.input.question_id);assert.ok(s.input.selected_options.length);}
 const objects=async(page,resource)=>(await page.request.get(`${base}/api/engineering/${resource}`,{headers:{'X-Project-ID':project}})).json();
 assert.equal((await objects(a,'hardware-nodes')).items.length,0);
 report.checks.push('Four structured decisions -> recommendation -> validated architecture; no model writes');
 const resize=a.getByRole('button',{name:'Breite des Assistentenfensters ändern',exact:true});await resize.focus();await resize.press('ArrowLeft');
 let bounds=await a.locator('.agent-widget-panel').boundingBox();assert.ok(bounds.width>=380&&bounds.width<=440);
 await a.getByRole('button',{name:'Vorschlag freigeben',exact:true}).click();
 await a.getByRole('button',{name:'Ins Modell übernehmen',exact:true}).waitFor();assert.equal((await objects(a,'hardware-nodes')).items.length,0);
 await a.getByRole('button',{name:'Ins Modell übernehmen',exact:true}).click();
 await a.getByText('23 Modellobjekte bestätigt.',{exact:true}).waitFor({timeout:30000});
 const hardwareA=(await objects(a,'hardware-nodes')).items,hardwareB=(await objects(b,'hardware-nodes')).items;
 assert.equal(hardwareA.length,5);assert.deepEqual(hardwareA.map(x=>x.id).sort(),hardwareB.map(x=>x.id).sort());
 report.checks.push('Approval and apply separated; Chrome and Edge see identical five hardware IDs');
 const findingCard=a.locator('.agent-widget-panel [data-response-type=FINDING]').last();
 await findingCard.getByText('Entscheidung: Offen',{exact:true}).click();
 await findingCard.getByLabel('Umgang mit dem Finding').selectOption('ACCEPTED_RISK');
 await findingCard.getByLabel('Begründung',{exact:true}).fill('Für den reinen Strukturentwurf akzeptiert; Dimensionierung erfolgt vor Simulation.');
 await findingCard.getByRole('button',{name:'Entscheidung speichern',exact:true}).click();
 await findingCard.getByText('Entscheidung: Risiko akzeptiert',{exact:true}).waitFor();
 const sharedState=await (await b.request.get(`${base}/api/engineering/agent/conversation`,{headers:{'X-Project-ID':project}})).json();
 assert.ok(Object.values(sharedState.data.decisions).some(d=>d.status==='ACCEPTED_RISK'&&d.review_on_change));
 report.checks.push('Risk acceptance with rationale persists in PostgreSQL and is visible from Edge');
 await a.screenshot({path:out+'chat-ux-applied.png'});
 await a.getByRole('button',{name:'Engineering-Assistent schließen',exact:true}).click();await a.getByRole('button',{name:'AI Assistant öffnen',exact:true}).click();
 await a.getByText('23 Modellobjekte bestätigt.',{exact:true}).waitFor();
 await a.setViewportSize({width:390,height:844});
 bounds=await a.locator('.agent-widget-panel').boundingBox();assert.equal(Math.round(bounds.width),390);assert.equal(Math.round(bounds.height),844);
 await a.screenshot({path:out+'chat-ux-mobile.png'});
  const darkColor=await a.locator('.agent-widget-panel').evaluate(el=>getComputedStyle(el).backgroundColor);
 await a.evaluate(()=>{const palette={'--background':'#ffffff','--surface':'#f8fafc','--surface-raised':'#e2e8f0','--surface-hover':'#f1f5f9','--border':'#cbd5e1','--text':'#0f172a','--muted':'#475569'};for(const [key,value] of Object.entries(palette))document.documentElement.style.setProperty(key,value);});
 const lightColor=await a.locator('.agent-widget-panel').evaluate(el=>getComputedStyle(el).backgroundColor);assert.notEqual(lightColor,darkColor);assert.equal(await a.locator('.agent-widget-panel textarea[aria-label]').evaluate(el=>getComputedStyle(el).backgroundColor),lightColor);
 await a.screenshot({path:out+'chat-ux-light.png'});
 report.checks.push('Open/close keeps conversation; keyboard resize bounded; mobile full-height drawer; dark/light theme-token palettes');
 const href=await a.getByRole('link',{name:'Im Workspace öffnen',exact:true}).last().getAttribute('href');assert.ok(href.includes('/studio/agent?'));
 await b.goto(new URL(href,base).href);await b.getByRole('heading',{name:'Engineering Assistant',exact:true}).waitFor();
 report.checks.push('Workspace navigation keeps project and conversation');
 assert.deepEqual(report.errors,[]);
 await fs.writeFile(out+'chat-ux-browser-report.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));
} catch(error){console.error(error);process.exitCode=1;const failedPage=browsers[0]?.contexts()[0]?.pages()[0];if(failedPage){await failedPage.screenshot({path:out+'chat-ux-failure.png'});await fs.writeFile(out+'chat-ux-failure.html',await failedPage.content());}await fs.writeFile(out+'chat-ux-browser-failure.json',JSON.stringify({...report,failure:String(error)},null,2));}
finally{for(const browser of browsers)await Promise.race([browser.close(),new Promise(r=>setTimeout(r,5000))]);process.exit(process.exitCode??0);}





