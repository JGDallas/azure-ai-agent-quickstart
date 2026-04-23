# Azure OpenAI pricing basics

Language models are billed per 1,000,000 tokens, with separate prices for input (prompt) and output (completion) tokens. gpt-4o-mini is the entry-level chat model and is roughly an order of magnitude cheaper than gpt-4o. Public list pricing for gpt-4o-mini at time of writing is around $0.15 per million input tokens and $0.60 per million output tokens.

Provisioned Throughput Units (PTUs) offer dedicated capacity at a fixed hourly rate and are worth evaluating once steady-state traffic is predictable. For demos and prototypes, pay-as-you-go Standard is almost always the right default.
