# Rate limits and quotas

Azure OpenAI quota is allocated per region, per subscription, per model, expressed in Tokens Per Minute (TPM) and Requests Per Minute (RPM). Exceeding either returns HTTP 429 with a `Retry-After` header. Implement exponential backoff with jitter and respect the hint.

Provisioned Throughput Units (PTUs) replace the per-minute caps with dedicated capacity and are the right answer for latency-sensitive production traffic. For bursty demos, a single Standard deployment is usually fine.
