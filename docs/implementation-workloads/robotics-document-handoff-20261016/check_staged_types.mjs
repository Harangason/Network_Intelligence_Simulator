import ts from '../../../frontend/node_modules/typescript/lib/typescript.js';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

// A read-only compiler overlay; application files and the active gate inputs
// remain untouched. Run the regular typecheck again after the real handoff.
const work = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(work, '../../..');
const frontend = path.join(root, 'frontend');
const configPath = path.join(frontend, 'tsconfig.json');
const config = ts.readConfigFile(configPath, ts.sys.readFile);
const parsed = ts.parseJsonConfigFileContent(config.config, ts.sys, frontend);
const options = { ...parsed.options, incremental: false, noEmit: true };
const host = ts.createCompilerHost(options);
const overlay = file => path.join(work, 'staged', path.relative(root, file));
const originalRead = host.readFile;
const originalExists = host.fileExists;
host.readFile = file => fs.existsSync(overlay(file)) ? fs.readFileSync(overlay(file), 'utf8') : originalRead(file);
host.fileExists = file => fs.existsSync(overlay(file)) || originalExists(file);
const program = ts.createProgram(parsed.fileNames, options, host);
const diagnostics = ts.getPreEmitDiagnostics(program);
const result = diagnostics.map(item => ({ file: item.file?.fileName, line: item.file && item.start !== undefined ? item.file.getLineAndCharacterOfPosition(item.start).line + 1 : undefined,
  code: item.code, message: ts.flattenDiagnosticMessageText(item.messageText, '\n') }));
fs.writeFileSync(path.join(work, 'staged-typecheck.json'), JSON.stringify({ staged_only: true, diagnostics: result }, null, 2));
console.log(JSON.stringify({ staged_only: true, diagnostics: result }));
process.exitCode = result.length ? 1 : 0;
