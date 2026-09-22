import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { FileBlob, PresentationFile } from '@oai/artifact-tool';

const SKILL_DIR='F:/CodexOrdner/plugins/cache/openai-primary-runtime/presentations/26.905.11957/skills/presentations';
const workspaceDir='I:/PycharmProjects/My_first_Network_Simulator';
const sourcePath=path.join(workspaceDir,'presentation_output/Projekte_AI_NIS_ueberarbeitet_Docker_LLM_uebersichtlich_v2.pptx');
const outDir=path.join(workspaceDir,'presentation_output');
const stagingDir=path.join(workspaceDir,'.codex-finalizer');
const finalPath=path.join(outDir,'Projekte_AI_NIS_ueberarbeitet_Docker_LLM_uebersichtlich_v3.pptx');
await fs.mkdir(outDir,{recursive:true}); await fs.mkdir(stagingDir,{recursive:true});
const presentation=await PresentationFile.importPptx(await FileBlob.load(sourcePath));
const replacements=new Map([
 ['Root Cause\nFinding\nAkzeptanz\nRepair\nRegression', 'Trace lesen – Ablauf und Zeitpunkt verstehen\nRoot Cause – technische Hauptursache finden\nFinding – Befund mit Nachweis dokumentieren\nRepair – Änderung umsetzen und testen\nRegression – keine neuen Fehler einführen'],
 ['Der technische Kern bleibt gleich: Teilnehmer erzeugen Daten, Netze transportieren sie, Simulation und Trace machen Verhalten prüfbar.', 'Root Cause bedeutet: die technische Hauptursache hinter dem sichtbaren Fehler. Der Trace liefert den zeitlichen Nachweis.'],
]);
let changed=0;
for (const slide of presentation.slides.items) {
  for (const shape of (slide.shapes?.items ?? [])) {
    let text=''; try { text=shape.text?.toString?.() ?? ''; } catch {}
    for (const [oldText,newText] of replacements) {
      if (text.includes(oldText)) { shape.text=text.replace(oldText,newText); changed++; text=text.replace(oldText,newText); }
    }
  }
}
const candidatePath=path.join(stagingDir,'candidate-slide4.pptx');
await (await PresentationFile.exportPptx(presentation)).save(candidatePath);
const {finalizePresentation}=await import(pathToFileURL(path.join(SKILL_DIR,'container_tools/artifact_tool_utils.mjs')).href);
const result=await finalizePresentation({
 workspaceDir,candidatePath,finalPath,
 pythonExecutable:'C:/Users/marti/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',
 integrityValidatorPath:path.join(SKILL_DIR,'container_tools/inspect_presentation_package_integrity.py'),
 layoutValidatorPath:path.join(SKILL_DIR,'container_tools/inspect_presentation_layout_geometry.py'),
 layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit'],
 requiredNativeTableOwnerSlides:[],requiredNativeChartOwnerSlides:[],verifyArtifactToolImport:true,
 receiptPath:path.join(stagingDir,'validation-v3.json'),
});
console.log(JSON.stringify({changed,finalPath,result},null,2));
