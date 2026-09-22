import fs from 'node:fs/promises';
import path from 'node:path';
import { FileBlob, PresentationFile } from '@oai/artifact-tool';
const outDir='I:/PycharmProjects/My_first_Network_Simulator/.ppt_inspect/final';
await fs.mkdir(outDir,{recursive:true});
const p=await PresentationFile.importPptx(await FileBlob.load('I:/PycharmProjects/My_first_Network_Simulator/presentation_output/Projekte_AI_NIS_ueberarbeitet_Docker_LLM_uebersichtlich_slide9_final.pptx'));
const montage=await p.export({format:'webp',montage:true,scale:1});
await fs.writeFile(path.join(outDir,'montage.webp'),new Uint8Array(await montage.arrayBuffer()));
for (let i=0;i<p.slides.items.length;i++) {
 const img=await p.slides.items[i].export({format:'png',scale:1.5});
 await fs.writeFile(path.join(outDir,`slide-${i+1}.png`),new Uint8Array(await img.arrayBuffer()));
}
console.log('rendered',p.slides.items.length);
