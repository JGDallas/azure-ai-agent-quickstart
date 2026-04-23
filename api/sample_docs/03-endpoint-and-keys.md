# Endpoint and API keys

Every Azure OpenAI resource exposes a base endpoint of the form `https://<resource-name>.openai.azure.com`. Two rotating API keys are provisioned by default. To find them in the Azure Portal, open your Azure OpenAI resource and click "Keys and Endpoint". Either KEY 1 or KEY 2 works; rotate them on a schedule for production workloads.

Prefer Microsoft Entra ID (Azure AD) authentication for production: it eliminates long-lived secrets and enables role-based access control via the Cognitive Services OpenAI User role. API keys are convenient for local development and demos.
