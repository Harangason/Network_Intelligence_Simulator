import { FileBlob, PresentationFile } from '@oai/artifact-tool';
const p = await PresentationFile.importPptx(await FileBlob.load('H:/OneDrive/Download/Projekte_AI_NIS_ueberarbeitet_Docker_LLM.pptx'));
for (let i=0;i<p.slides.items.length;i++) {
  const s=p.slides.items[i];
  console.log(`---SLIDE ${i+1}---`);
  for (const sh of (s.shapes?.items ?? [])) {
    let t=''; try { t=sh.text?.toString?.() ?? sh.text ?? ''; } catch {}
    if (t) console.log(JSON.stringify({id:sh.id, name:sh.name, text:t, frame:sh.frame}));
  }
}
