# Getting your Azure keys

Goal: provision the one Azure resource this quickstart requires, then copy three values into `.env`:

1. `AZURE_OPENAI_ENDPOINT`
2. `AZURE_OPENAI_API_KEY`
3. `AZURE_OPENAI_DEPLOYMENT` (the name you pick for the deployment — not the model name)

That's it. Everything else in `.env.example` is optional.

---

## 1. Sign in and choose a subscription

Open [https://portal.azure.com](https://portal.azure.com), sign in, and confirm you're in the subscription you want to bill. Click the subscription selector in the top bar if you need to switch.

## 2. Create an Azure OpenAI resource

- Click **Create a resource** (top-left).
- Search for **Azure OpenAI** and select the "Azure OpenAI" offering.
- Click **Create**.

Fill in the form:

| Field | Value |
|---|---|
| Subscription | your subscription |
| Resource group | pick or create, e.g. `rg-ai-quickstart` |
| Region | any region with `gpt-4o-mini` available, e.g. East US 2, Sweden Central |
| Name | unique, e.g. `aoai-<your-handle>` |
| Pricing tier | Standard S0 |

Click **Review + create**, then **Create**. Wait for deployment to finish (1–2 minutes).

## 3. Open the resource

Click **Go to resource** once it's deployed, or find it under **All resources**.

## 4. Launch Azure AI Foundry / Azure OpenAI Studio

In the left nav of the Azure OpenAI resource, click **Go to Azure AI Foundry** (or **Azure OpenAI Studio**, depending on which portal you're routed to). A new tab opens.

## 5. Deploy gpt-4o-mini

Inside Foundry:

- Left nav: **Model catalog** (or **Deployments** > **Create new deployment**).
- Search for `gpt-4o-mini` and click it.
- Click **Deploy**.
- In the dialog:
  - **Deployment name**: `gpt-4o-mini` (keep it identical to the model name — the default `.env` expects this).
  - **Deployment type**: Standard is fine for demos.
  - **Tokens per Minute Rate Limit**: the default is fine; you can lower it to cap cost.
- Click **Deploy**.

Wait for status to show **Succeeded**.

## 6. Copy the endpoint and key

Go back to the Azure Portal tab with your Azure OpenAI resource.

- Left nav: **Keys and Endpoint**.
- Copy **Endpoint** — paste it into `.env` as `AZURE_OPENAI_ENDPOINT`.
- Copy **KEY 1** — paste it into `.env` as `AZURE_OPENAI_API_KEY`.

## 7. Confirm deployment name

In Foundry under **Deployments**, confirm the deployment name you chose in step 5. Paste it into `.env` as `AZURE_OPENAI_DEPLOYMENT`. The default in `.env.example` is `gpt-4o-mini` — only change this if you picked a different name.

## 8. Run

From the repo root:

```bash
./run.sh
```

## 9. (Optional) Azure AI Search

If you want the research agent to search a real index instead of the local SQLite FTS5 fallback:

- Create an **Azure AI Search** resource in the portal (Basic tier is fine for demos).
- Create an index (the default name the quickstart expects is `quickstart-docs`).
- Copy **Url** and **Primary admin key** from the resource's **Keys** blade.
- Set `AZURE_AI_SEARCH_ENDPOINT`, `AZURE_AI_SEARCH_KEY`, and `AZURE_AI_SEARCH_INDEX` in `.env`.

If any of these three are empty or placeholder, the quickstart falls back to the local FTS5 index — no action needed.

## 10. (Optional) Application Insights

- Create an **Application Insights** resource (workspace-based is fine).
- Copy the **Connection String** from the Overview blade.
- Set `APPLICATIONINSIGHTS_CONNECTION_STRING` in `.env`.

With this set, traces also flow to App Insights; without it, traces are still visible via the UI Inspector panel.

---

## Budget sanity check

Default budgets in `.env.example` are generous but bounded:

- `SESSION_TOKEN_BUDGET=200000`
- `SESSION_USD_BUDGET=2.00`

At list prices for `gpt-4o-mini`, a typical chat session with a few tool calls costs fractions of a cent. Tune these down for belt-and-suspenders safety.
