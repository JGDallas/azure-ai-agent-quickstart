# Managed identity with Azure OpenAI

Microsoft Entra ID authentication removes long-lived API keys from your application. In Azure, assign a managed identity to the compute that calls Azure OpenAI (Container Apps, App Service, AKS) and grant it the Cognitive Services OpenAI User role on the Azure OpenAI resource.

In code, `DefaultAzureCredential` from the azure-identity package picks up the managed identity automatically. The same code works locally: when you are signed in to `az login` or VS Code, DefaultAzureCredential falls back to your developer credential. This is the recommended path for any workload beyond quick demos.
