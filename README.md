## Setting Up the Python Environment with uv
1. **Init project**:
   ```bash
   uv init --python 3.13.5 ai-assistant
   cd ai-assistant
   ```
2. **Venv**
   ```bash
   uv venv
   source .venv/bin/activate
   ```

3. **Dependencies**
   ```bash
   uv add langchain_core langchain-openai langgraph ipython python-dotenv structlog pytest pytest-cov pytest-mock
   ```
