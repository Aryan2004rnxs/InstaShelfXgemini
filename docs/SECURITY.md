# InstaShelf Agent — Security & Risk Policy Specification

## 1. Security Principles
1. **AI Proposes, Code Authorizes**: Gemini LLM models generate action proposals. The deterministic Policy Engine enforces authorization and permission rules.
2. **Untrusted Data Boundary**: Scraped Instagram captions, YouTube descriptions, and transcripts are strictly isolated inside `UNTRUSTED DATA` containers before processing. Hostile instructions embedded in external content cannot alter system prompts or escalate permissions.
3. **Append-Only Action Auditing**: Every tool call is validated and recorded in an append-only Action Ledger with an idempotency key.

---

## 2. Policy Matrix

| Action Name | Risk Tier | Permission | Approval Required | Description |
| :--- | :--- | :--- | :--- | :--- |
| `SAVE_SHELF` | **SAFE** | ALLOW | No | Save item metadata to DB / Sheets |
| `GENERATE_KNOWLEDGE_MAP` | **SAFE** | ALLOW | No | Extract concept graph |
| `GENERATE_STUDY_MATERIAL` | **SAFE** | ALLOW | No | Synthesize Master Notes & flashcards |
| `NOTIFY_USER` | **SAFE** | ALLOW | No | Send Telegram updates |
| `ARCHIVE_DUPLICATE` | **LOW** | ALLOW | No | Move duplicate item to archive |
| `REORDER_CURRICULUM` | **LOW** | ALLOW | No | Re-prioritize learning mission roadmap |
| `CREATE_MISSION` | **LOW** | ALLOW | No | Generate new Learning Mission |
| `RESTRUCTURE_MISSION` | **MEDIUM** | ALLOW (+Undo) | No | Restructure active curriculum |
| `DELETE_ITEM` | **HIGH** | BLOCK | **Yes** | Permanent removal of item data |
| `EXTERNAL_BROADCAST` | **HIGH** | BLOCK | **Yes** | Send external broadcast message |
| `EXECUTE_SYSTEM_CMD` | **CRITICAL** | BLOCK | Forbidden | Execute shell or system commands |

---

## 3. Prompt Injection Defense Architecture

```
                       EXTERNAL UNTRUSTED DATA
       (Instagram Captions / YouTube Transcripts / PDFs / Paste)
                                  │
                                  ▼
                   UNTRUSTED DATA DATA CONTAINER
            Sanitization & System Instruction Insulation
                                  │
                                  ▼
                       GEMINI 3.5+ PARSER
             Structured Output Validation (Pydantic)
                                  │
                                  ▼
                        DETERMINISTIC AGENT CONTEXT
```
