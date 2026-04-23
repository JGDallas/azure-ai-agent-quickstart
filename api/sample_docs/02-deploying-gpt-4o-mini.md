# Deploying gpt-4o-mini

To call gpt-4o-mini, you must create a deployment of it in your Azure OpenAI resource. The deployment name is independent of the model name — you can call a deployment "gpt-4o-mini" or anything else. Your SDK calls use the deployment name, not the model name.

Create a deployment from the Azure AI Foundry portal (Deployments > Create new deployment), selecting the base model and picking a sku such as Standard or GlobalStandard. Quota is allocated at the region + sku level. gpt-4o-mini is the recommended default for low-cost chat and agent use cases because it is substantially cheaper than gpt-4o while still supporting function calling and streaming.
