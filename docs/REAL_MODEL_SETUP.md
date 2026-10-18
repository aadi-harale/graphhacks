# Real model setup (OpenRouter, local only)

Moved from the README.


The Track 01 agent uses an OpenAI-compatible Python client. **OpenRouter is supported as an optional API endpoint** without changing FalkorDB or the user interface. The database remains the *local* Docker FalkorDB instance. The current public Vercel site is still a simulation.

**Security:** Never paste or commit a key; if a key has appeared in a chat, revoke it and create a fresh limited-use key at https://openrouter.ai/keys. On Windows PowerShell, in the project directory:

~~~powershell
# Enter your NEW OpenRouter key into this local shell, hidden.
$secure = Read-Host "New OpenRouter API key" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try { $env:OPENAI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
$env:OPENAI_BASE_URL = "https://openrouter.ai/api/v1"
$env:SAHIAAYA_AGENT_MODEL = "openrouter/free"
docker compose up -d --no-deps --force-recreate app
docker compose exec app python -c "import os; print('OpenRouter endpoint:', os.getenv('OPENAI_BASE_URL') == 'https://openrouter.ai/api/v1'); print('Key configured:', bool(os.getenv('OPENAI_API_KEY'))); print('Model:', os.getenv('SAHIAAYA_AGENT_MODEL'))"
# Run ONE real-model case first. Can be rate-limited or fail; no pass is assumed.
docker compose exec app python -m scripts.live_model_gate --accept-api-cost --only unattributed
~~~

The variable named \`OPENAI_API_KEY\` is deliberately reused because the application uses the OpenAI-compatible SDK; it now contains your **OpenRouter** credential, not an OpenAI Platform key. \`OPENAI_BASE_URL\` is configurable in Docker Compose and otherwise defaults to the official OpenAI API URL. \`openrouter/free\` uses an available free model that can support requested features; its model selection can vary, and rate limits/availability may prevent reliable six-case evidence. For a final judge recording, prefer a fixed tool-capable OpenRouter model with a supported quota. If the first case fails, inspect the case's \`error\` field before paying or rerunning all six. **No live OpenRouter model test has been performed by this documentation change.**

