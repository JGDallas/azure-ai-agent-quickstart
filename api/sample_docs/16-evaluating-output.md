# Evaluating LLM output

"LLM-as-judge" evaluation asks a model to score another model's response on named criteria. Typical criteria for RAG are groundedness (does the answer follow from the retrieved context?), relevance (does it answer the question?), and coherence (is it well-formed?). Scores are usually on a 1-5 scale with a short rationale.

For production, graduate to the azure-ai-evaluation SDK, which ships built-in evaluators, dataset-level aggregation, and integration with Azure AI Foundry evaluation runs. For prototypes, a single inline LLM call is plenty.
