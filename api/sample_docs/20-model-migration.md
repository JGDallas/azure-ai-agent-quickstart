# Migrating between models

When moving a deployment from an older model (say gpt-3.5-turbo) to a newer one (gpt-4o-mini), the biggest risk is silent behavior change. Prompts that worked fine may become terser, chattier, or differently structured. Run an offline evaluation set against both deployments and compare scores before flipping the switch in production.

Migration is also a good moment to re-check token budgets. Newer models often have larger context windows, which tempts longer prompts; newer models also price differently for input vs output tokens, which can flip the economics of your workload.
