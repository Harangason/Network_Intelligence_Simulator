import fs from 'node:fs/promises';
import path from 'node:path';
import { FileBlob, PresentationFile } from '@oai/artifact-tool';

const sourcePath = 'H:/OneDrive/Download/Projekte_AI_NIS_ueberarbeitet_Docker_LLM.pptx';
const outDir = 'I:/PycharmProjects/My_first_Network_Simulator/.ppt_inspect';
await fs.mkdir(outDir, { recursive: true });
const presentation = await PresentationFile.importPptx(await FileBlob.load(sourcePath));
const snapshot = await presentation.inspect({ kind: 'slide,textbox,shape,image,table,chart,notes,layout', maxChars: 50000 });
await fs.writeFile(path.join(outDir, 'snapshot.ndjson'), snapshot.ndjson);
const montage = await presentation.export({ format: 'webp', montage: true, scale: 1 });
await fs.writeFile(path.join(outDir, 'montage.webp'), new Uint8Array(await montage.arrayBuffer()));
console.log(snapshot.ndjson);
console.log('slides', presentation.slides.items.length);
console.log('size', presentation.slideSize);
