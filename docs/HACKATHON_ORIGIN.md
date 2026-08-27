# InstaShelf Agent — Hackathon Provenance & Code Disclosure

**Submission**: InstaShelf Agent — Autonomous Learning Manager  
**Track**: TASKMASTER (Google's All Things Agentic Hackathon 2026)

In strict accordance with the official hackathon rules regarding pre-existing code and work incorporated into submissions, this document provides a transparent breakdown of **pre-existing baseline components** vs. **components designed, architected, and built during the submission period**.

---

## 1. Pre-Existing Baseline Components (Created Prior to Submission Period)
*The original InstaShelf prototype was a basic single-step content bookmarking script.*

- **Original UI Theme**: Initial Japanese Wabi-Sabi aesthetic stylesheet template.
- **Third-Party API Wrappers**: Basic Apify Instagram scraper wrapper (`scraper.py`) and standard YouTube Data API v3 helper functions (`enrichment.py`).
- **Data Backup Helper**: `sheets.py` Google Sheets append function.

---

## 2. Hackathon-Built Components (Built Entirely During Submission Period)
*All autonomous agent architecture, multi-agent reasoning, state persistence, policy engines, and multimodal fusion systems were created for the All Things Agentic Hackathon.*

- 🧠 **Google ADK Autonomous Learning Manager (`agents/orchestrator.py`)**:
  - Long-horizon objective management engine ("Make me interview-ready in RAG").
  - Formulates success contracts, calculates Distance to Goal (e.g. 58% ➔ 86%), manages state transitions, and streams telemetry.
- 🎯 **Goal Achievement Engine & Success Contracts (`services/goal_engine.py`)**:
  - Formal schema measuring concept coverage (>= 90%), weak concepts (< 2), benchmark score (>= 80%), and claim conflicts (== 0).
- 📊 **Evaluation Agent & Self-Correction Loop (`services/evaluation_agent.py`)**:
  - Measures intervention score deltas before vs. after (+32 points) and stores Intervention Memory.
- 🎯 **Strategy Selection Layer (`services/strategy_engine.py`)**:
  - Dynamic strategy selector choosing optimal intervention format based on user intervention memory.
- 🕵️ **Knowledge Auditor & "Learning the Wrong Thing" Detection (`services/knowledge_auditor.py`)**:
  - Detects when user saves redundant content (e.g. 15 vector DB videos when vector DB is already mastered and evaluation is the weak concept).
  - Autonomously redirects priorities, archives redundant items, and surfaces evaluation resources.
- 📉 **Actionable Knowledge Debt Engine (`services/knowledge_debt.py`)**:
  - Formula-driven Knowledge Debt Index (0-100) and automated backlog paydown (merging duplicates, archiving stale links).
- 🔮 **Multimodal Content Fusion ("Teach Me From What I Showed You") (`services/multimodal_inbox.py`)**:
  - Fuses Reel Video + Architecture Screenshot + Handwritten Notes + Spoken Audio Note into a single visual knowledge evaluation.
- 🛡️ **Tool Gateway & Risk-Aware Policy Engine (`tools/tool_gateway.py`, `services/policy_engine.py`)**:
  - Deterministic permission check, rate limiting, risk classification (`SAFE`, `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`), and approval gating.
- 📜 **Append-Only Action Ledger (`memory/action_ledger.py`)**:
  - Immutable audit trail recording every agent tool invocation, input hash, risk level, and verification status.
- 🕸️ **Evidence Graph Engine (`memory/evidence_graph.py`)**:
  - Links agent conclusions to observable evidence (screenshots, quiz results, video timestamps).
- ⏰ **Proactive Mission Health Scheduler (`services/proactive_scheduler.py`)**:
  - Cloud Scheduler + Pub/Sub background loop evaluating mission health with no-action suppression.
- ⚡ **Agent Resource Budgeting (`services/agent_budget.py`)**:
  - Enforces max tool calls, LLM requests, daily actions, and runtime per mission.
- 🧪 **20-Scenario Agent Reliability Benchmark (`tests/agent_benchmark.py`)**:
  - Automated test benchmark verifying model compliance, idempotency, prompt injection defense, policy gating, and crash recovery.
