# Observing LLM apps with Application Insights

Application Insights is the default telemetry backend in Azure. The `azure-monitor-opentelemetry` Python distro wires OpenTelemetry exporters to App Insights in one call: `configure_azure_monitor(connection_string=...)`. After that, every HTTP call, exception, and custom span shows up in the App Insights portal.

For LLM workloads, instrument: model deployment name, prompt/completion token counts, tool-call name and latency, error category (rate limit vs content filter vs other), and the final answer length. These four or five fields are enough to debug most production issues.
