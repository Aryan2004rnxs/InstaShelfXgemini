# InstaShelf Agent — Technical Architecture Specification

**Product Identity**: InstaShelf Agent — Autonomous Learning Manager  
**Framework**: Google Agent Development Kit (`google-adk`) & Gemini 3.5+  
**Deployment**: Google Cloud Run + Google Cloud Firestore + Google Cloud Pub/Sub  

---

## 1. Product Architecture Diagram

```
                               USER / TOUCHPOINTS
                 Telegram Bot  │  Wabi-Sabi Web Workspace  │  REST APIs
                                       │
                                       ▼
                            ┌─────────────────────┐
                            │     AGENT INBOX     │
                            │ URL / Video / Image │
                            │ Screenshot / PDF    │
                            │ Audio / Text        │
                            └──────────┬──────────┘
                                       │ (Multimodal Payload / Goal Request)
                                       ▼
                         ┌───────────────────────────┐
                         │ ADK LEARNING MANAGER LOOP │
                         │ Long-Horizon Goal Engine  │
                         └─────────────┬─────────────┘
                                       │
           ┌───────────────────────────┼───────────────────────────┐
           ▼                           ▼                           ▼
    RESEARCH AGENT              KNOWLEDGE AGENT             EVALUATION AGENT
    Candidate Search &          Concept Hierarchy &          Intervention Impact &
    Source Match Score          Distance-to-Goal             Self-Correction Loop
           │                           │                           │
           └───────────────────────────┼───────────────────────────┘
                                       ▼
                           ┌───────────────────────┐
                           │   STRATEGY ENGINE     │
                           │  Intervention Memory  │
                           └───────────┬───────────┘
                                       │
                                       ▼
                           ┌───────────────────────┐
                           │ AUTONOMOUS OUTCOMES   │
                           │ - Reduced Distance    │
                           │ - Master Notes & Quiz │
                           │ - Mission Roadmap     │
                           └───────────────────────┘
```

---

## 2. Runtime & Cloud Infrastructure Diagram

```
                            CLOUD RUN BACKEND CONTAINER
                               FastAPI + BG Workers
                                       │
                ┌──────────────────────┴──────────────────────┐
                │                                             │ (Proactive Event Trigger)
                ▼                                             ▼
┌──────────────────────────────────────┐     ┌──────────────────────────────────┐
│   GOOGLE AGENT DEVELOPMENT KIT (ADK) │     │      CLOUD SCHEDULER / PUBSUB    │
│     InstaShelfADKOrchestrator        │◄────┤     Periodic Mission Health &    │
│    (Resumable Checkpoint Engine)     │     │      Knowledge Debt Evaluator    │
└──────────────────┬───────────────────┘     └──────────────────────────────────┘
                   │
                   ▼
         ┌───────────────────┐
         │   TOOL GATEWAY    │
         │ Validation & Auth │
         └─────────┬─────────┘
                   ▼
         ┌───────────────────┐
         │   POLICY ENGINE   │
         │ Risk Classifier   │
         │ SAFE / LOW / MED  │
         │ HIGH / CRITICAL   │
         └─────────┬─────────┘
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
┌─────────────────┐   ┌─────────────────┐
│ AUTO EXECUTOR   │   │ APPROVAL GATE   │
└────────┬────────┘   └────────┬────────┘
         │                     │
         └──────────┬──────────┘
                    ▼
         ┌───────────────────┐
         │ VERIFIER LAYER    │
         └─────────┬─────────┘
                   ▼
         ┌───────────────────┐
         │   ACTION LEDGER   │
         └─────────┬─────────┘
                   ▼
┌────────────────────────────────────────────────────────┐
│              PRIMARY CLOUD PERSISTENCE                 │
│   Google Cloud Firestore Task, Mission & Memory        │
│   SQLite Local Dev Fallback  │ Google Sheets Export    │
└────────────────────────────────────────────────────────┘
```

---

## 3. Safety, Policy Engine & Verification Diagram

```
                 GEMINI 3.5+ REASONING & MULTIMODAL LAYER
                                    │
                                    ▼
                             PROPOSED ACTION
                                    │
                                    ▼
                       DETERMINISTIC POLICY ENGINE
                    Risk Classification & Permission Check
                                    │
           ┌────────────────────────┴────────────────────────┐
           ▼                                                 ▼
      SAFE / LOW / MEDIUM                                  HIGH / CRITICAL
   Automatic Execution (+ Undo)                       Approval Required / Blocked
           │                                                 │
           └────────────────────────┬────────────────────────┘
                                    ▼
                          EXECUTOR & VERIFIER
                                    │
                                    ▼
                        APPEND-ONLY ACTION LEDGER
                     Immutable Operational Audit Log
```
