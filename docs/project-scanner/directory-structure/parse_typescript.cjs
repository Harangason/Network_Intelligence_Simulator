/**
 * DE: Liest TypeScript-/JavaScript-Dateien mit dem installierten Compilerparser.
 * EN: Reads TypeScript/JavaScript files with the installed compiler parser.
 * Project modules are parsed, never imported or evaluated.
 */
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '../../..');
const ts = require(path.join(root, 'frontend/node_modules/typescript'));
const inventory = JSON.parse(fs.readFileSync(path.join(__dirname, 'inventory.json'), 'utf8'));
const output = {};

function clean(value, limit = 420) {
  return String(value || '').replace(/\s+/g, ' ').trim().slice(0, limit);
}

for (const record of inventory.files) {
  if (!/\.(?:ts|tsx|js|jsx|mjs|cjs)$/.test(record.path) || record.bytes > 2000000 || record.error) continue;
  const source = fs.readFileSync(path.join(root, record.path), 'utf8');
  const file = ts.createSourceFile(record.path, source, ts.ScriptTarget.Latest, true);
  const symbols = [], imports = [], testTitles = [], texts = [];
  function add(node, name, kind, scope) {
    const line = file.getLineAndCharacterOfPosition(node.getStart(file)).line + 1;
    const description = clean((node.jsDoc || []).map(doc => typeof doc.comment === 'string' ? doc.comment : '').join(' '));
    symbols.push({ name: scope + name, kind, line, description });
  }
  function visit(node, scope = '') {
    let childScope = scope;
    if (ts.isImportDeclaration(node) && ts.isStringLiteral(node.moduleSpecifier)) imports.push(node.moduleSpecifier.text);
    if (ts.isExportDeclaration(node) && node.moduleSpecifier && ts.isStringLiteral(node.moduleSpecifier)) imports.push(node.moduleSpecifier.text);
    if (ts.isCallExpression(node) && node.expression.getText(file) === 'require' && node.arguments[0] && ts.isStringLiteral(node.arguments[0])) imports.push(node.arguments[0].text);
    const definitions = [
      [ts.isFunctionDeclaration, 'Funktion'], [ts.isClassDeclaration, 'Klasse'],
      [ts.isInterfaceDeclaration, 'Interface'], [ts.isTypeAliasDeclaration, 'Typ'],
      [ts.isEnumDeclaration, 'Enum'], [ts.isMethodDeclaration, 'Methode'],
    ];
    for (const [predicate, kind] of definitions) {
      if (predicate(node) && node.name) {
        const name = node.name.getText(file);
        add(node, name, kind, scope);
        childScope = scope + name + '.';
        break;
      }
    }
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer && (ts.isArrowFunction(node.initializer) || ts.isFunctionExpression(node.initializer))) {
      add(node, node.name.text, 'Funktionsvariable', scope);
      childScope = scope + node.name.text + '.';
    }
    if (ts.isCallExpression(node) && /^(?:test|it|describe)(?:\.(?:skip|only))?$/.test(node.expression.getText(file)) && node.arguments[0] && ts.isStringLiteral(node.arguments[0])) testTitles.push(clean(node.arguments[0].text));
    if (ts.isJsxText(node)) {
      const value = clean(node.getText(file), 130);
      if (value.length >= 8 && texts.length < 6) texts.push(value);
    }
    ts.forEachChild(node, child => visit(child, childScope));
  }
  visit(file);
  const moduleComments = ts.getLeadingCommentRanges(source, 0) || [];
  const description = clean(moduleComments.map(comment => source.slice(comment.pos, comment.end).replace(/^\/\*+|\*\/$|^\/\//g, '').replace(/\n\s*\*/g, '\n')).join(' '), 600);
  const details = {
    symbols,
    imports: [...new Set(imports)].sort(),
    test_titles: [...new Set(testTitles)],
    module_description: description,
    evidence: 'TypeScript-Compilerparser, Definitionen, Imports und Test-/UI-Texte gelesen; Verhalten nicht ausgeführt',
  };
  if (!description && /\.(?:tsx|jsx)$/.test(record.path) && texts.length) details.module_description = 'Oberflächentexte: ' + texts.join(' · ');
  if (file.parseDiagnostics.length) {
    details.parse_error = file.parseDiagnostics.map(d => ts.flattenDiagnosticMessageText(d.messageText, ' ')).join('; ');
    details.evidence = 'TypeScript-Compilerparser mit Parserbefunden; Struktur teilweise extrahiert';
  }
  if (/\/route\.ts$/.test(record.path)) {
    const route = record.path.replace(/^frontend\/src\/app/, '').replace(/\/route\.ts$/, '');
    const methods = symbols.filter(s => /^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)$/.test(s.name)).map(s => s.name);
    details.routes = methods.map(method => ({ path: route, methods: [method], line: symbols.find(s => s.name === method).line }));
  }
  output[record.path] = details;
}
fs.writeFileSync(path.join(__dirname, 'typescript-details.json'), JSON.stringify(output, null, 2) + '\n');
console.log(JSON.stringify({ files: Object.keys(output).length, symbols: Object.values(output).reduce((total, file) => total + file.symbols.length, 0) }));
