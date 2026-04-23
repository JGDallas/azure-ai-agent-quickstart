# Azure AI Search

Azure AI Search (formerly Azure Cognitive Search) is a managed search service that supports keyword, vector, and hybrid retrieval. For RAG it is the usual default on Azure: you create an index with a vector field and a content field, push documents via the REST API or the azure-search-documents SDK, and query with text, vector, or both.

Azure AI Search integrates cleanly with Azure OpenAI via the Foundry "Add your data" feature, which handles chunking, embedding, and retrieval for you. For full control, do the retrieval yourself and pass the top-k snippets into the chat completion as context.
