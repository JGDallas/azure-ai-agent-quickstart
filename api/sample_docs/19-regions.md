# Azure OpenAI regions

Azure OpenAI is available in many but not all Azure regions. Model availability also varies by region — a model may be available in East US 2 but not yet in West Europe, for example. Always check the Foundry portal for current availability in your target region.

For multi-region deployments, use GlobalStandard SKUs where possible — they route traffic to the nearest healthy region and simplify capacity planning. Data residency requirements may force Standard (regional) deployments instead.
