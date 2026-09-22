import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { FileBlob, PresentationFile } from '@oai/artifact-tool';

const SKILL_DIR='F:/CodexOrdner/plugins/cache/openai-primary-runtime/presentations/26.905.11957/skills/presentations';
const workspaceDir='I:/PycharmProjects/My_first_Network_Simulator';
const sourcePath=path.join(workspaceDir,'presentation_output/Projekte_AI_NIS_ueberarbeitet_Docker_LLM_uebersichtlich_v3.pptx');
const imagePath='H:/OneDrive/Download/ChatGPT Image 6. Sept. 2026, 10_37_58.png';
const outDir=path.join(workspaceDir,'presentation_output');
const stagingDir=path.join(workspaceDir,'.codex-finalizer');
const finalPath=path.join(outDir,'Projekte_AI_NIS_ueberarbeitet_Docker_LLM_uebersichtlich_slide9_final.pptx');
await fs.mkdir(outDir,{recursive:true}); await fs.mkdir(stagingDir,{recursive:true});
const presentation=await PresentationFile.importPptx(await FileBlob.load(sourcePath));
const sourceSlide=presentation.slides.items[7];
const slide=sourceSlide.duplicate();
slide.moveTo(8);

for (const shape of (slide.shapes?.items ?? [])) {
  let text=''; try { text=shape.text?.toString?.() ?? ''; } catch {}
  if (text.includes('DATENMODELL')) shape.text='DATENMODELL';
  if (text.includes('Ein gemeinsames Modell verbindet alle technischen Objekte')) shape.text='Von der ECU bis zum Signal';
  if (text.includes('Das gemeinsame Modell verbindet Architektur, Signale, Simulation und Nachweise.')) shape.text='So werden Funktionen, Nachrichten und Signale im Modell miteinander verknüpft.';
}

// Cover the duplicated content area while keeping the imported master, header and footer.
slide.shapes.add({
  geometry:'rect', position:{left:52.8,top:136.3,width:1176,height:520},
  fill:'#061321', line:{fill:'none',width:0},
});
const imageBytes=await fs.readFile(imagePath);
slide.images.add({
  blob:imageBytes, contentType:'image/png', alt:'Hierarchie von ECU über Funktionen und Nachrichten bis zu Signalen',
  fit:'contain', position:{left:52.8,top:145,width:760,height:505},
});
const heading=slide.shapes.add({
  geometry:'textbox', position:{left:850,top:190,width:330,height:34}, fill:'none', line:{fill:'none',width:0},
});
heading.text='Hierarchie des Modells';
heading.text.style={fontSize:24,bold:true,color:'#F4F7FB',typeface:'Aptos'};
const body=slide.shapes.add({
  geometry:'textbox', position:{left:850,top:245,width:340,height:250}, fill:'none', line:{fill:'none',width:0},
});
body.text='Eine ECU bündelt Funktionen.\n\nJede Funktion nutzt logische Interfaces.\n\nNachrichten transportieren die Signale.\n\nWird die zulässige Nutzlast überschritten, entsteht eine neue Nachricht.';
body.text.style={fontSize:18,color:'#AEBBCD',typeface:'Aptos',autoFit:'shrink'};
const callout=slide.shapes.add({
  geometry:'textbox', position:{left:850,top:535,width:340,height:75}, fill:'none', line:{fill:'none',width:0},
});
callout.text='Merksatz\nSignale werden in Nachrichten verpackt.';
callout.text.style={fontSize:18,bold:true,color:'#29D3E3',typeface:'Aptos',autoFit:'shrink'};

// Keep visible page numbers consistent after inserting the new slide.
for (let i=0;i<presentation.slides.items.length;i++) {
  for (const shape of (presentation.slides.items[i].shapes?.items ?? [])) {
    let text=''; try { text=shape.text?.toString?.() ?? ''; } catch {}
    const frame=shape.frame;
    if (/^\d{2}$/.test(text) && frame && frame.top>640 && frame.left>1100) shape.text=String(i+1).padStart(2,'0');
  }
}

const candidatePath=path.join(stagingDir,'candidate-slide9.pptx');
await (await PresentationFile.exportPptx(presentation)).save(candidatePath);
const {finalizePresentation}=await import(pathToFileURL(path.join(SKILL_DIR,'container_tools/artifact_tool_utils.mjs')).href);
const result=await finalizePresentation({
 workspaceDir,candidatePath,finalPath,
 pythonExecutable:'C:/Users/marti/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',
 integrityValidatorPath:path.join(SKILL_DIR,'container_tools/inspect_presentation_package_integrity.py'),
 layoutValidatorPath:path.join(SKILL_DIR,'container_tools/inspect_presentation_layout_geometry.py'),
 layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit'],
 requiredNativeTableOwnerSlides:[],requiredNativeChartOwnerSlides:[],verifyArtifactToolImport:true,
 receiptPath:path.join(stagingDir,'validation-slide9-final.json'),
});
console.log(JSON.stringify({slideCount:presentation.slides.items.length,finalPath,result},null,2));
