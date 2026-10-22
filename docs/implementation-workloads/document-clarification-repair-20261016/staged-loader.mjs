import { registerHooks } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const work = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(work, '../../..');
const replacement = url => {
  if (!url.startsWith('file:')) return;
  const relative = path.relative(root, fileURLToPath(url));
  if (relative.startsWith('..') || path.isAbsolute(relative)) return;
  const staged = path.join(work, 'staged', relative);
  if (fs.existsSync(staged) && fs.statSync(staged).isFile()) return pathToFileURL(staged).href;
};
// Run existing pure tests against the prepared source bytes while keeping the
// canonical source files frozen. No database, API or inference substitution.
registerHooks({
  resolve(specifier, context, next) {
    if (context.parentURL && specifier.startsWith('.')) {
      const url = new URL(specifier, context.parentURL).href;
      if (replacement(url)) return { url, shortCircuit: true };
    }
    return next(specifier, context);
  },
  load(url, context, next) { return next(replacement(url) ?? url, context); },
});
