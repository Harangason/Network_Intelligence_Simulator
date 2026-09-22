import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { Presentation, PresentationFile } from '@oai/artifact-tool';

const SKILL_DIR='F:/CodexOrdner/plugins/cache/openai-primary-runtime/presentations/26.905.11957/skills/presentations';
const workspaceDir='I:/PycharmProjects/My_first_Network_Simulator';
const tempDir=path.join(workspaceDir,'.ppt_inspect');
const stagingDir=path.join(workspaceDir,'.codex-finalizer');
const finalPath=path.join(workspaceDir,'presentation_output/NIS_interaktiv_muster_ECU_v2.pptx');
const imagePath='H:/OneDrive/Download/ChatGPT Image 6. Sept. 2026, 10_37_58.png';
const imageBytes=await fs.readFile(imagePath);
await fs.mkdir(stagingDir,{recursive:true});

const C={bg:'#061321',panel:'#0D1D2D',white:'#F3F7FC',muted:'#AEBBCD',teal:'#18D2E2',green:'#75E841',blue:'#1BA8EA',amber:'#F7C744',line:'#1D3B4D'};
const p=Presentation.create({slideSize:{width:1280,height:720}});
const steps=[
 {n:'01',kicker:'MODELLHIERARCHIE',title:'Die ECU bündelt Funktionen',body:'Eine ECU ist ein Steuergerät. Sie enthält mindestens eine Funktion. Jede Funktion beschreibt eine Aufgabe des Systems und kann eigene logische Interfaces besitzen.',key:'ECU  →  Funktion  →  logisches Interface',accent:C.green},
 {n:'02',kicker:'NACHRICHTEN UND SIGNALE',title:'Nachrichten transportieren Signale',body:'Signale enthalten einzelne Informationen. Das logische Interface ordnet sie Nachrichten zu, die über ein Netzwerk übertragen werden.',key:'Im Beispiel: CAN-FD-Nachrichten mit bis zu 64 Byte Nutzlast',accent:C.blue},
 {n:'03',kicker:'NUTZLASTGRENZE',title:'Passt ein Signal nicht mehr, folgt eine neue Nachricht',body:'Die erste Nachricht nutzt im Beispiel 64 von 64 Byte. Weitere Signale kommen in eine neue Nachricht. Diese ist zunächst nur teilweise gefüllt.',key:'Die Nutzlastgrenze bestimmt, wann eine weitere Nachricht beginnt.',accent:C.amber},
];
function addText(slide,text,pos,style={}){
 const s=slide.shapes.add({geometry:'textbox',position:pos,fill:'none',line:{fill:'none',width:0}});
 s.text=text; s.text.style={typeface:'Aptos',fontSize:style.fontSize??22,bold:style.bold??false,color:style.color??C.white,autoFit:'shrink',...(style.align?{alignment:style.align}:{})}; return s;
}
for(let i=0;i<steps.length;i++){
 const d=steps[i], slide=p.slides.add(); slide.background.fill=C.bg;
 addText(slide,'NIS  |  INTERAKTIVES MUSTER',{left:54,top:28,width:480,height:24},{fontSize:16,bold:true,color:C.teal});
 addText(slide,d.kicker,{left:54,top:74,width:700,height:24},{fontSize:16,bold:true,color:d.accent});
 addText(slide,d.title,{left:54,top:103,width:1160,height:60},{fontSize:38,bold:true});
 slide.shapes.add({geometry:'rect',position:{left:54,top:175,width:104,height:4},fill:C.teal,line:{fill:'none',width:0}});
 slide.images.add({blob:imageBytes,contentType:'image/png',alt:'Beispiel: ECU, Funktionen, logische Interfaces, Nachrichten und Signale',fit:'contain',position:{left:42,top:193,width:745,height:500}});
 addText(slide,d.n,{left:835,top:224,width:100,height:70},{fontSize:54,bold:true,color:d.accent});
 addText(slide,d.body,{left:835,top:310,width:370,height:150},{fontSize:23,color:C.muted});
 addText(slide,d.key,{left:835,top:500,width:370,height:86},{fontSize:20,bold:true,color:C.white});
 // A restrained progress indicator makes the three-step interaction explicit.
 for(let j=0;j<3;j++) slide.shapes.add({geometry:'rect',position:{left:835+j*124,top:616,width:108,height:5},fill:j<=i?d.accent:C.line,line:{fill:'none',width:0}});
 addText(slide,`${d.n} / 03   ·   Weiterklicken für den nächsten Schritt`,{left:835,top:635,width:390,height:25},{fontSize:15,color:C.muted});
 slide.speakerNotes.textFrame.setText('Muster für eine geführte Erklärung: Mit jedem Weiterklick wechselt die Aussage und der Hervorhebungsfokus.');
}
const candidatePath=path.join(stagingDir,'candidate-interactive-sample.pptx');
await (await PresentationFile.exportPptx(p)).save(candidatePath);
const {finalizePresentation}=await import(pathToFileURL(path.join(SKILL_DIR,'container_tools/artifact_tool_utils.mjs')).href);
const result=await finalizePresentation({
 workspaceDir,candidatePath,finalPath,
 pythonExecutable:'C:/Users/marti/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',
 integrityValidatorPath:path.join(SKILL_DIR,'container_tools/inspect_presentation_package_integrity.py'),
 layoutValidatorPath:path.join(SKILL_DIR,'container_tools/inspect_presentation_layout_geometry.py'),
 layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit'],
 requiredNativeTableOwnerSlides:[],requiredNativeChartOwnerSlides:[],verifyArtifactToolImport:true,
 receiptPath:path.join(stagingDir,'validation-interactive-sample-v2.json'),
});
for(let i=0;i<p.slides.items.length;i++){
 const preview=await p.export({slide:p.slides.items[i],format:'png',scale:1});
 await fs.writeFile(path.join(tempDir,`interactive-sample-${i+1}.png`),new Uint8Array(await preview.arrayBuffer()));
}
console.log(JSON.stringify({finalPath,slideCount:p.slides.items.length,result},null,2));
