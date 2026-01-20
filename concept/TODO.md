What we're doing RIGHT:
  - ✓ Using MCP server to interact with FHIR
  - ✓ Tool abstraction (search, create, read, etc.)
  - ✓ AI-powered anonymization logic
  - ✓ Streaming workflow to frontend

What's WRONG (not truly agentic):
  - ✗ We're manually orchestrating tools - the backend decides when to call search/create
  - ✗ AI doesn't see the tools - Gemini only does anonymization, not tool selection
  - ✗ Hardcoded workflow - always search → anonymize → create
  - ✗ No autonomous decision-making - AI can't decide "I need more patient data, let me call read_patient"