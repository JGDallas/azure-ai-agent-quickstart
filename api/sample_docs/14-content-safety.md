# Content safety filters

Azure OpenAI includes content filtering that runs on both prompts and completions. The default configuration blocks or annotates content that falls into hate, violence, sexual, or self-harm categories. Jailbreak and prompt-injection detection can be enabled additionally.

If a prompt or completion is blocked, the API returns a specific error code with the category that triggered. Surface that to your users with a friendly message rather than the raw error. For sensitive scenarios, lower or raise filter thresholds via the Content Filter management experience in Azure AI Foundry.
