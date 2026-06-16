# PMG Project 1 - Group 13

Welcome to the repository for **PMG Project 1 - Group 13**.

## Getting Started
Run the local app server:

```bash
python3 app_server.py
```

Open:

```text
http://127.0.0.1:4174/
```

## Optional AI Readout
The website can explain the current charts with a free local Ollama model.

1. Install Ollama from `https://ollama.com/download`
2. Pull the default model:

```bash
ollama pull llama3
```

3. Start Ollama if it is not already running:

```bash
ollama serve
```

4. Run the app:

```bash
python3 app_server.py
```

The AI Readout uses `http://127.0.0.1:11434` and model `llama3` by default. You can override those when starting the app:

```bash
OLLAMA_BASE_URL=http://127.0.0.1:11434 OLLAMA_MODEL=llama3 python3 app_server.py
```

If Ollama is not installed or not running, the site still works and shows a template fallback analysis.

## Data Sources
- Wikipedia Pageviews: public curiosity and historical page spikes
- Google Trends: historical search curiosity
- YouTube Data API: optional live video momentum when `config.local.json` contains a key
