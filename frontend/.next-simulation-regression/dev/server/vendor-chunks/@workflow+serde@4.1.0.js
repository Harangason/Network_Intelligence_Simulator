"use strict";
/*
 * ATTENTION: An "eval-source-map" devtool has been used.
 * This devtool is neither made for production nor for readable output files.
 * It uses "eval()" calls to create a separate source file with attached SourceMaps in the browser devtools.
 * If you are trying to read the output file, select a different devtool (https://webpack.js.org/configuration/devtool/)
 * or disable the default devtool with "devtool: false".
 * If you are looking for production-ready output files, see mode: "production" (https://webpack.js.org/configuration/mode/).
 */
exports.id = "vendor-chunks/@workflow+serde@4.1.0";
exports.ids = ["vendor-chunks/@workflow+serde@4.1.0"];
exports.modules = {

/***/ "(ssr)/./node_modules/.pnpm/@workflow+serde@4.1.0/node_modules/@workflow/serde/dist/index.js":
/*!*********************************************************************************************!*\
  !*** ./node_modules/.pnpm/@workflow+serde@4.1.0/node_modules/@workflow/serde/dist/index.js ***!
  \*********************************************************************************************/
/***/ ((__unused_webpack___webpack_module__, __webpack_exports__, __webpack_require__) => {

eval("__webpack_require__.r(__webpack_exports__);\n/* harmony export */ __webpack_require__.d(__webpack_exports__, {\n/* harmony export */   WORKFLOW_DESERIALIZE: () => (/* binding */ WORKFLOW_DESERIALIZE),\n/* harmony export */   WORKFLOW_SERIALIZE: () => (/* binding */ WORKFLOW_SERIALIZE)\n/* harmony export */ });\n/**\n * Symbol used to define custom serialization for user-defined class instances.\n * The static method should accept an instance and return serializable data.\n *\n * @example\n * ```ts\n * import { WORKFLOW_SERIALIZE, WORKFLOW_DESERIALIZE } from '@workflow/serde';\n *\n * class MyClass {\n *   constructor(public value: string) {}\n *\n *   static [WORKFLOW_SERIALIZE](instance: MyClass) {\n *     return { value: instance.value };\n *   }\n *\n *   static [WORKFLOW_DESERIALIZE](data: { value: string }) {\n *     return new MyClass(data.value);\n *   }\n * }\n * ```\n */\nconst WORKFLOW_SERIALIZE = Symbol.for('workflow-serialize');\n/**\n * Symbol used to define custom deserialization for user-defined class instances.\n * The static method should accept serialized data and return a class instance.\n *\n * @see WORKFLOW_SERIALIZE for usage example\n */\nconst WORKFLOW_DESERIALIZE = Symbol.for('workflow-deserialize');\n//# sourceMappingURL=index.js.map//# sourceURL=[module]\n//# sourceMappingURL=data:application/json;charset=utf-8;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiKHNzcikvLi9ub2RlX21vZHVsZXMvLnBucG0vQHdvcmtmbG93K3NlcmRlQDQuMS4wL25vZGVfbW9kdWxlcy9Ad29ya2Zsb3cvc2VyZGUvZGlzdC9pbmRleC5qcyIsIm1hcHBpbmdzIjoiOzs7OztBQUFBO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNBLFlBQVksMkNBQTJDO0FBQ3ZEO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQSxnQkFBZ0I7QUFDaEI7QUFDQTtBQUNBLDJDQUEyQyxlQUFlO0FBQzFEO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDTztBQUNQO0FBQ0E7QUFDQTtBQUNBO0FBQ0E7QUFDQTtBQUNPO0FBQ1AiLCJzb3VyY2VzIjpbIkk6XFxQeWNoYXJtUHJvamVjdHNcXE15X2ZpcnN0X05ldHdvcmtfU2ltdWxhdG9yXFxmcm9udGVuZFxcbm9kZV9tb2R1bGVzXFwucG5wbVxcQHdvcmtmbG93K3NlcmRlQDQuMS4wXFxub2RlX21vZHVsZXNcXEB3b3JrZmxvd1xcc2VyZGVcXGRpc3RcXGluZGV4LmpzIl0sInNvdXJjZXNDb250ZW50IjpbIi8qKlxuICogU3ltYm9sIHVzZWQgdG8gZGVmaW5lIGN1c3RvbSBzZXJpYWxpemF0aW9uIGZvciB1c2VyLWRlZmluZWQgY2xhc3MgaW5zdGFuY2VzLlxuICogVGhlIHN0YXRpYyBtZXRob2Qgc2hvdWxkIGFjY2VwdCBhbiBpbnN0YW5jZSBhbmQgcmV0dXJuIHNlcmlhbGl6YWJsZSBkYXRhLlxuICpcbiAqIEBleGFtcGxlXG4gKiBgYGB0c1xuICogaW1wb3J0IHsgV09SS0ZMT1dfU0VSSUFMSVpFLCBXT1JLRkxPV19ERVNFUklBTElaRSB9IGZyb20gJ0B3b3JrZmxvdy9zZXJkZSc7XG4gKlxuICogY2xhc3MgTXlDbGFzcyB7XG4gKiAgIGNvbnN0cnVjdG9yKHB1YmxpYyB2YWx1ZTogc3RyaW5nKSB7fVxuICpcbiAqICAgc3RhdGljIFtXT1JLRkxPV19TRVJJQUxJWkVdKGluc3RhbmNlOiBNeUNsYXNzKSB7XG4gKiAgICAgcmV0dXJuIHsgdmFsdWU6IGluc3RhbmNlLnZhbHVlIH07XG4gKiAgIH1cbiAqXG4gKiAgIHN0YXRpYyBbV09SS0ZMT1dfREVTRVJJQUxJWkVdKGRhdGE6IHsgdmFsdWU6IHN0cmluZyB9KSB7XG4gKiAgICAgcmV0dXJuIG5ldyBNeUNsYXNzKGRhdGEudmFsdWUpO1xuICogICB9XG4gKiB9XG4gKiBgYGBcbiAqL1xuZXhwb3J0IGNvbnN0IFdPUktGTE9XX1NFUklBTElaRSA9IFN5bWJvbC5mb3IoJ3dvcmtmbG93LXNlcmlhbGl6ZScpO1xuLyoqXG4gKiBTeW1ib2wgdXNlZCB0byBkZWZpbmUgY3VzdG9tIGRlc2VyaWFsaXphdGlvbiBmb3IgdXNlci1kZWZpbmVkIGNsYXNzIGluc3RhbmNlcy5cbiAqIFRoZSBzdGF0aWMgbWV0aG9kIHNob3VsZCBhY2NlcHQgc2VyaWFsaXplZCBkYXRhIGFuZCByZXR1cm4gYSBjbGFzcyBpbnN0YW5jZS5cbiAqXG4gKiBAc2VlIFdPUktGTE9XX1NFUklBTElaRSBmb3IgdXNhZ2UgZXhhbXBsZVxuICovXG5leHBvcnQgY29uc3QgV09SS0ZMT1dfREVTRVJJQUxJWkUgPSBTeW1ib2wuZm9yKCd3b3JrZmxvdy1kZXNlcmlhbGl6ZScpO1xuLy8jIHNvdXJjZU1hcHBpbmdVUkw9aW5kZXguanMubWFwIl0sIm5hbWVzIjpbXSwiaWdub3JlTGlzdCI6WzBdLCJzb3VyY2VSb290IjoiIn0=\n//# sourceURL=webpack-internal:///(ssr)/./node_modules/.pnpm/@workflow+serde@4.1.0/node_modules/@workflow/serde/dist/index.js\n");

/***/ })

};
;