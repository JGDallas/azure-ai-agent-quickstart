# Responsible AI principles

Microsoft's Responsible AI Standard organizes LLM practice around six principles: fairness, reliability and safety, privacy and security, inclusiveness, transparency, and accountability. For an agent system, the practical questions are: what data is going to the model, what does it output, what actions can it take, and how do you audit those actions later.

Concrete defaults that align with the standard: keep conversation history on the user's side, redact PII before sending to the model, require explicit confirmation before destructive tool calls, and log every tool invocation with inputs, outputs, and actor identity.
