// Compile the real frontend project using read-only staged file overlays.
// No canonical source, cache, generated route type or node_modules is changed.
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
const out = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(out, '../../../..');
const require = createRequire(path.join(repo, 'frontend/package.json'));
const ts = require('typescript');
const dirs = [path.join(out, '../integration/staged'), path.join(out, 'staged')];
const normalize = value => path.resolve(value).replaceAll('\\', '/').toLowerCase();
const overlay = new Map();
function collect(dir, base = dir) {
  if (!fs.existsSync(dir)) return;
  for (const item of fs.readdirSync(dir, { withFileTypes: true })) {
    const filename = path.join(dir, item.name);
    if (item.isDirectory()) collect(filename, base);
    else if (filename.endsWith('.ts') || filename.endsWith('.tsx')) {
      const relative = path.relative(base, filename);
      if (relative.startsWith('frontend')) overlay.set(normalize(path.join(repo, relative)), filename);
    }
  }
}
dirs.forEach(dir => collect(dir));
const configPath = path.join(repo, 'frontend/tsconfig.json');
const config = ts.readConfigFile(configPath, ts.sys.readFile);
const parsed = ts.parseJsonConfigFileContent(config.config, ts.sys, path.dirname(configPath));
const options = { ...parsed.options, noEmit: true, incremental: false };
const host = ts.createCompilerHost(options);
const read = host.readFile.bind(host);
host.readFile = file => read(overlay.get(normalize(file)) ?? file);
const program = ts.createProgram(parsed.fileNames, options, host);
const diagnostics = ts.getPreEmitDiagnostics(program);
const report = ts.formatDiagnosticsWithColorAndContext(diagnostics, {
  getCurrentDirectory: () => repo, getCanonicalFileName: value => value, getNewLine: () => '\n',
});
fs.writeFileSync(path.join(out, 'staged-typecheck.log'), report || 'Staged overlay typecheck passed. Canonical files unchanged.\n');
process.stdout.write(report || `Staged overlay typecheck passed (${overlay.size} overlays).\n`);
process.exitCode = diagnostics.length ? 1 : 0;
