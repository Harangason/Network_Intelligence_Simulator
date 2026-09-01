# AI Model Routing

Model routing follows the rule: deterministic first, small model second, large model only when necessary.

Initial routing:

- simple rule: heuristic
- structured semantic lookup: ontology
- semantic similarity: embedding adapter
- complex context: future LLM plus RAG
- relationship reasoning: future graph plus LLM
