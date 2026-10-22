import fs from 'node:fs';
import path from 'node:path';
import { registerHooks } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
const out = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(out, '../../../..');
const stages = [path.join(out, 'staged'), path.join(out, '../integration/staged')];
const canonical = filename => {
  const stage = stages.find(root => filename.startsWith(root + path.sep));
  return stage ? path.join(repo, path.relative(stage, filename)) : filename;
};
registerHooks({
  resolve(specifier, context, next) {
    if (context.parentURL?.startsWith('file:')) {
      const original = fileURLToPath(context.parentURL), actual = canonical(original);
      if (actual !== original) context = { ...context, parentURL: pathToFileURL(actual).href };
    }
    return next(specifier, context);
  },
  load(url, context, next) {
    if (url.startsWith('file:')) {
      const actual = canonical(fileURLToPath(url));
      const rel = path.relative(repo, actual);
      if (rel.startsWith('frontend' + path.sep) && /\.(?:ts|tsx|mjs)$/.test(actual)) {
        const overlay = stages.map(root => path.join(root, rel)).find(file => fs.existsSync(file));
        if (overlay) return { format: actual.endsWith('.ts') ? 'module-typescript' : 'module',
          source: fs.readFileSync(overlay, 'utf8'), shortCircuit: true };
      }
    }
    return next(url, context);
  },
});
