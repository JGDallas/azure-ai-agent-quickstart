# Retrieval-Augmented Generation (RAG) patterns

RAG is the pattern of retrieving relevant passages from a corpus and passing them into a chat completion as context. The minimal pipeline is: chunk documents, embed them, store embeddings in a vector index, embed the query, retrieve top-k chunks, and concatenate them into the prompt.

Common refinements include hybrid retrieval (keyword + vector), reranking the top-N candidates with a cross-encoder before sending to the model, and citing retrieved sources in the final answer. RAG is the right default for any scenario where the answer lives in documents the model was not trained on.
