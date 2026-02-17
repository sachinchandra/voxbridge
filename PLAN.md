# VoxBridge — AI-First Contact Center Platform

## The Vision

**Replace Genesys, not integrate with it.**

Contact centers today spend $75-240/seat/month on platforms designed for
human agents, then bolt on AI as an afterthought. We flip this: AI agents
are the default. Humans handle escalations. No seats. No queues. No hold music.

**One line pitch:** "AI agents that answer your company's phones — deploy in
minutes, not months. Handles 80% of calls automatically. Escalates the rest
to your team with full context."

---

## The Market (Why This Is Worth Building)

### Market Size
- Contact center software market: **$64B in 2025 → $264B by 2034** (16.5% CAGR)
- CCaaS market alone: **$7B in 2025 → $30B by 2034**
- **17 million** contact center agents worldwide
- **60,850** contact centers in North America (3.3M agent seats)
- Gartner: AI will autonomously resolve **80% of common issues by 2029**

### The Pain We're Solving
| Pain Point | Today's Reality | Our Solution |
|---|---|---|
| **Agent turnover: 30-45%/yr** | $10K-20K to replace each agent | AI agents don't quit |
| **Cost: $15-25/hr per agent** | 60-75% of OpEx is human labor | $0.06/min (~$3.60/hr) |
| **Training: 90 days to ramp** | New agents = 8-12mo to full productivity | Update prompt, instant deploy |
| **Volume spikes: 200-500%** | Understaffed → long wait times → lost customers | AI scales instantly, 0 queue |
| **24/7 coverage** | 3 shifts × agent cost, or offshore outsourcing | AI runs 24/7 at same cost |
| **Quality inconsistency** | Sample 2-5% of calls for QA | 100% calls scored + analyzed |

### Cost Comparison Per 10,000 Calls/Month (3 min avg)
```
Traditional (Genesys + Humans):
  Platform: 50 agents × $150/seat    = $7,500/mo
  Agent salary: 50 × $3,500/mo       = $175,000/mo
  Telephony: 30,000 min × $0.01      = $300/mo
  Total:                              = $182,800/mo
  Cost per call:                      = $18.28

VoxBridge AI Contact Center:
  Platform: 30,000 min × $0.06       = $1,800/mo
  10 humans for escalations (20%):    = $35,000/mo
  Total:                              = $36,800/mo
  Cost per call:                      = $3.68

  SAVINGS: 80% ($146,000/mo)
```

---

## Who We're Targeting

### Phase 1 Target: SMB with 5-50 Agent Contact Centers
- **Why:** Fastest sales cycle, most price-sensitive, least locked into Genesys/NICE
- **Industries:** E-commerce, SaaS, healthcare clinics, real estate, insurance agencies
- **Decision maker:** Head of Customer Support or CEO (in smaller companies)
- **Budget:** Currently spending $5K-50K/month on contact center ops
- **Sales motion:** Self-serve signup, credit card, no enterprise sales team needed

### Phase 2 Target: Mid-Market with 50-500 Agents
- **Why:** Big enough to justify $10K-50K/month, still flexible
- **Industries:** Insurance companies, regional banks, healthcare systems, logistics
- **Decision maker:** VP of Customer Experience, CIO
- **Budget:** $50K-500K/month on contact center
- **Sales motion:** Demo-driven, POC with 1 department, expand

### Phase 3 Target: Enterprise with 500+ Agents
- **Why:** Biggest revenue per customer, longest sales cycle
- **Industries:** Banking, telecom, airlines, large healthcare
- **Decision maker:** C-suite + procurement
- **Use our MOAT:** Native Genesys/Avaya/Cisco integration — migrate them
  off legacy platforms gradually. AI handles the easy calls first.

---

## What We Build — Feature Set

### Tier 1: Core Platform (Sprint 1-4) — "Replace Your Phone Lines"

**AI Agents**
- Create AI agents via dashboard or API
- Configure: system prompt, personality, knowledge base
- Choose STT/LLM/TTS providers (Deepgram, OpenAI, Claude, ElevenLabs)
- Set first message, end-call phrases, max duration
- Test in-browser playground before going live

**Phone Numbers**
- Buy phone numbers from dashboard (US, UK, CA — via Twilio/Telnyx)
- Assign numbers to AI agents (1 click)
- Inbound: customer calls → AI agent answers instantly
- Outbound: trigger calls via API (appointment reminders, follow-ups)

**Call Management**
- Real-time call dashboard (live calls, queue status, AI vs human)
- Call history with full transcripts + recordings
- Search calls by keyword, date, outcome, sentiment
- Export call data (CSV, API)

**Smart Escalation**
- AI detects when to transfer to human (anger, complexity, "talk to a person")
- Transfers with full context summary (what the caller wants, what AI tried)
- Configurable escalation rules per agent
- Fallback to voicemail if no humans available

**Function Calling / Integrations**
- AI agents can call external APIs mid-conversation
- "Check order status", "Book appointment", "Look up account"
- Webhook-based: point to your API, define the schema
- Pre-built: Salesforce, HubSpot, Zendesk, Shopify, Calendly

### Tier 2: Intelligence Layer (Sprint 5-8) — "See Everything"

**Real-Time Analytics**
- Per-agent: calls handled, avg duration, resolution rate, sentiment score
- Per-company: total calls, AI containment rate, cost savings
- Compare: AI agent performance vs human baseline
- Alerts: unusual volume, angry callers, failed API calls

**Knowledge Base (RAG)**
- Upload PDFs, docs, URLs → AI learns your business
- Vector search: AI retrieves relevant info during calls
- Auto-update: re-crawl URLs on schedule
- Per-agent knowledge: different agents = different knowledge

**Quality Assurance (100% Coverage)**
- Every call auto-scored on: accuracy, tone, resolution, compliance
- Flag risky calls (PII exposure, angry callers, compliance issues)
- Compare AI quality vs human quality benchmarks
- Weekly QA reports auto-generated

**Conversation Design Studio**
- Visual flow builder for complex call flows
- Decision trees + free-form AI hybrid
- Test flows with simulated calls
- Version control: A/B test different prompts

### Tier 3: Enterprise (Sprint 9-12) — "Replace Genesys"

**Multi-Department Routing**
- Route calls by intent: sales → Sales AI, support → Support AI, billing → Billing AI
- IVR replacement: "Press 1 for..." becomes AI understanding what you want
- Skill-based routing when escalating to humans

**Contact Center Connectors**
- Genesys AudioHook connector: plug VoxBridge AI into existing Genesys setup
- Amazon Connect connector
- Avaya / Cisco connectors
- Migrate call types gradually: start with FAQ calls, expand to complex

**Agent Assist Mode**
- AI listens to live human-agent calls in real-time
- Provides: suggested responses, knowledge lookups, compliance warnings
- Auto-generates call summary + next steps after call
- This is the "land" strategy for enterprise — add value before replacing

**Compliance & Security**
- PCI DSS: auto-redact credit card numbers from transcripts/recordings
- HIPAA: BAA available, data encryption at rest + in transit
- SOC 2 Type II compliance
- Data residency options (US, EU, APAC)
- Audit logs for all actions

**Workforce Management (Hybrid)**
- Dashboard for managing human escalation team
- Predict volume → recommend human staffing levels
- "AI handles X% this month, humans handle Y%"
- Track AI containment rate and improvement over time

---

## Pricing Model

### Usage-Based Pricing (No Per-Seat Fees)

**This is the KEY differentiator vs Genesys/NICE/Five9.**
They charge per seat ($75-240/agent/month). We charge per minute.
For AI-handled calls, there are no agents = no seats.

| Plan | Monthly Fee | Per-Minute Rate | Includes |
|------|-------------|----------------|----------|
| **Starter** | Free | $0.08/min | 100 min free, 1 agent, 1 number, Twilio |
| **Growth** | $49/mo | $0.06/min | 10 agents, 5 numbers, all STT/LLM/TTS, transcripts |
| **Business** | $199/mo | $0.05/min | 50 agents, 20 numbers, RAG, analytics, function calling |
| **Enterprise** | Custom | $0.03-0.04/min | Unlimited, Genesys/Avaya connectors, SSO, SLA, dedicated support |

### Per-Minute Breakdown (What's Inside $0.06/min)
```
STT (Deepgram):         $0.005/min  (pass-through)
LLM (OpenAI GPT-4o-mini): $0.003/min  (pass-through)
TTS (ElevenLabs):       $0.010/min  (pass-through)
Telephony (Twilio):     $0.007/min  (pass-through)
Platform margin:        $0.035/min  (OUR REVENUE)
────────────────────────────────────
Total:                  $0.060/min
```

**Platform margin: ~58%** — This is higher than Vapi because we're selling
to businesses (not developers) and providing the full contact center
experience (analytics, QA, escalation, integrations) not just a pipeline.

### Revenue Model at Scale
```
Scenario: 1,000 customers, avg 5,000 min/month each

Monthly revenue:
  Platform fees: 1,000 × $100 avg    = $100,000
  Usage: 5M min × $0.035 margin      = $175,000
  Total:                              = $275,000/mo = $3.3M ARR

Enterprise (10 customers × $5K/mo):  = $50,000/mo additional

Total:                                = $3.9M ARR
```

---

## Implementation Plan — Revised Sprints

### Sprint 1 (Week 1-2): Agent API + Database

**Backend — New API endpoints:**
```
POST   /api/v1/agents              # Create AI agent
GET    /api/v1/agents              # List agents
GET    /api/v1/agents/{id}         # Get agent config
PATCH  /api/v1/agents/{id}         # Update agent
DELETE /api/v1/agents/{id}         # Delete agent
GET    /api/v1/agents/{id}/stats   # Agent performance stats
```

**Database — New tables:**
```sql
-- AI Agents (the core entity)
agents (
  id, customer_id, name, status,
  system_prompt, first_message, end_call_phrases,
  stt_provider, stt_config,
  llm_provider, llm_model, llm_config,
  tts_provider, tts_voice_id, tts_config,
  max_duration_seconds, interruption_enabled,
  tools, knowledge_base_id,
  escalation_config,
  created_at, updated_at
)

-- Phone numbers assigned to agents
phone_numbers (
  id, customer_id, agent_id,
  phone_number, provider, provider_sid,
  country, capabilities, status,
  created_at
)

-- Call records (every call through the platform)
calls (
  id, customer_id, agent_id,
  phone_number_id, direction,
  from_number, to_number,
  started_at, ended_at, duration_seconds,
  status, end_reason,
  transcript JSONB,
  recording_url,
  sentiment_score, resolution,
  escalated_to_human BOOLEAN,
  cost_cents INTEGER,
  metadata JSONB,
  created_at
)

-- Function call logs (tool use during calls)
tool_calls (
  id, call_id, agent_id,
  function_name, arguments JSONB,
  result JSONB, duration_ms,
  created_at
)
```

**Deliverables:**
- [ ] Database migration (agents, phone_numbers, calls, tool_calls tables)
- [ ] Agent CRUD API with validation
- [ ] Agent stats endpoint (calls, avg duration, resolution rate)
- [ ] Tests for all endpoints

### Sprint 2 (Week 3-4): Dashboard — Agent Builder + Call Logs

**New Dashboard Pages:**
```
/agents              → List all AI agents with status/stats
/agents/new          → Create agent (wizard-style)
/agents/{id}         → Edit agent config
/agents/{id}/test    → Test agent (placeholder for playground)
/calls               → Call history table with search/filter
/calls/{id}          → Call detail: transcript, recording, timeline
/numbers             → Phone numbers list
/numbers/buy         → Search & buy new numbers
/analytics           → Charts: calls/day, AI containment, cost savings
```

**Agent Builder Wizard:**
```
Step 1: Name + Description
Step 2: AI Configuration
         - System prompt (textarea with examples)
         - LLM provider: OpenAI / Claude (dropdown)
         - LLM model: gpt-4o-mini / gpt-4o / claude-sonnet (dropdown)
Step 3: Voice Configuration
         - STT: Deepgram / Google / Azure
         - TTS: ElevenLabs / OpenAI / Azure
         - Voice: preview voices with audio samples
Step 4: Behavior
         - First message
         - Max duration
         - Interruption handling (on/off)
         - End-call phrases
Step 5: Escalation
         - When to escalate: anger, keyword, complexity
         - Transfer to: phone number / SIP / webhook
         - Context to include in transfer
Step 6: Integrations (optional)
         - Add function calls (API endpoints)
         - Connect knowledge base
Step 7: Phone Number
         - Assign existing or buy new
Step 8: Review & Deploy
```

**Deliverables:**
- [ ] Agent list page with status badges and quick stats
- [ ] Agent builder wizard (8 steps)
- [ ] Call logs page with transcript viewer
- [ ] Phone numbers management page
- [ ] Analytics dashboard with charts (Recharts)
- [ ] Update sidebar navigation

### Sprint 3 (Week 5-6): AI Pipeline Engine

**New package: `voxbridge/pipeline/`**
```
voxbridge/pipeline/
├── __init__.py
├── orchestrator.py       # STT→LLM→TTS streaming loop
├── turn_detector.py      # Endpointing (silence detection)
├── context.py            # Conversation context manager
└── escalation.py         # Escalation detection + handoff
```

**New package: `voxbridge/providers/`**
```
voxbridge/providers/
├── __init__.py
├── base.py               # BaseSTT, BaseLLM, BaseTTS interfaces
├── registry.py           # Provider factory
├── stt/
│   ├── deepgram.py       # Deepgram streaming (priority #1)
│   └── google.py         # Google STT (priority #2)
├── llm/
│   ├── openai.py         # OpenAI GPT (streaming)
│   ├── anthropic.py      # Claude (streaming)
│   └── custom.py         # Custom endpoint (BYOM)
└── tts/
    ├── elevenlabs.py     # ElevenLabs streaming (priority #1)
    ├── openai.py         # OpenAI TTS
    └── deepgram.py       # Deepgram Aura
```

**Pipeline Orchestrator Design:**
```python
class PipelineOrchestrator:
    """Real-time STT → LLM → TTS pipeline.

    Replaces the external bot WebSocket with a built-in AI pipeline.
    Receives audio from the VoxBridge bridge, processes it through
    the STT→LLM→TTS chain, and sends audio back.
    """

    async def run(self, session, agent_config):
        # 1. Start STT stream
        stt = provider_registry.create_stt(agent_config.stt_provider)
        llm = provider_registry.create_llm(agent_config.llm_provider)
        tts = provider_registry.create_tts(agent_config.tts_provider)

        # 2. Feed audio to STT
        # 3. On end-of-turn, send transcript to LLM
        # 4. Stream LLM tokens → accumulate sentences → TTS
        # 5. Stream TTS audio back to bridge
        # 6. Handle barge-in, escalation, function calls
```

**Integration with existing bridge.py:**
- Add `pipeline_mode` to bridge config
- When `pipeline_mode=True`, bridge creates PipelineOrchestrator
  instead of connecting to external bot WebSocket
- Pipeline receives audio directly from provider loop
- Pipeline sends audio directly back to provider

**Deliverables:**
- [ ] Provider base interfaces (BaseSTT, BaseLLM, BaseTTS)
- [ ] Deepgram streaming STT provider
- [ ] OpenAI GPT streaming LLM provider
- [ ] Anthropic Claude streaming LLM provider
- [ ] ElevenLabs streaming TTS provider
- [ ] PipelineOrchestrator (core loop)
- [ ] TurnDetector (silence-based endpointing)
- [ ] ConversationContext (message history management)
- [ ] EscalationDetector (anger/keyword/complexity detection)
- [ ] Integration with bridge.py
- [ ] Tests for each provider + orchestrator

### Sprint 4 (Week 7-8): Phone Numbers + Inbound/Outbound

**Phone number provisioning:**
```
POST /api/v1/phone-numbers/search   → Search available numbers
POST /api/v1/phone-numbers/buy      → Buy number (Twilio/Telnyx)
GET  /api/v1/phone-numbers          → List my numbers
DELETE /api/v1/phone-numbers/{id}   → Release number
PATCH /api/v1/phone-numbers/{id}    → Reassign to different agent
```

**Inbound call flow:**
```
1. Customer dials our number
2. Twilio/Telnyx webhook → POST /api/v1/webhooks/inbound
3. Look up: phone_number → agent mapping
4. Load agent config (prompt, LLM, TTS, tools)
5. Start pipeline: Twilio audio → STT → LLM → TTS → Twilio audio
6. Log call to database in real-time
7. On call end: store transcript, calculate cost, update usage
```

**Outbound call API:**
```
POST /api/v1/calls
{
    "agent_id": "uuid",
    "to": "+14155551234",
    "metadata": {"appointment_id": "apt-123"}
}

Response:
{
    "call_id": "uuid",
    "status": "initiated",
    "from": "+14155559876"
}
```

**Per-minute metering + billing:**
- Track call duration in real-time
- Calculate cost: duration × (STT + LLM + TTS + telephony + margin)
- Deduct from pre-paid credits or add to monthly invoice
- Stripe usage-based billing integration

**Deliverables:**
- [ ] Twilio number provisioning (search, buy, release)
- [ ] Inbound webhook handler + agent routing
- [ ] Outbound call API (POST /api/v1/calls)
- [ ] Call recording storage (S3/R2)
- [ ] Transcript storage (Supabase JSONB)
- [ ] Real-time cost calculation
- [ ] Stripe usage-based billing
- [ ] Dashboard: number management
- [ ] Dashboard: outbound call trigger

### Sprint 5 (Week 9-10): Function Calling + Knowledge Base

**Function calling:**
```json
// Agent tool configuration
{
  "tools": [{
    "name": "check_order_status",
    "description": "Look up order status by order ID",
    "parameters": {
      "type": "object",
      "properties": {
        "order_id": {"type": "string", "description": "The order ID"}
      },
      "required": ["order_id"]
    },
    "endpoint": "https://api.myshop.com/orders/status",
    "method": "GET"
  }]
}

// During a call, LLM decides to call this tool:
// 1. Pipeline pauses TTS
// 2. Calls customer's API endpoint
// 3. Feeds result back to LLM
// 4. LLM generates response with the data
// 5. Pipeline resumes TTS
```

**Knowledge Base (RAG):**
```
POST /api/v1/knowledge-bases              # Create KB
POST /api/v1/knowledge-bases/{id}/docs    # Upload document
DELETE /api/v1/knowledge-bases/{id}/docs/{doc_id}
GET  /api/v1/knowledge-bases              # List KBs
```

- Upload PDFs, DOCX, TXT, URLs
- Chunk + embed (OpenAI embeddings)
- Store vectors in pgvector (Supabase) or Pinecone
- During calls: LLM query → vector search → inject relevant context
- Dashboard: manage documents, see which docs get cited

**Deliverables:**
- [ ] Function calling in pipeline orchestrator
- [ ] Tool call logging (tool_calls table)
- [ ] Knowledge base API (CRUD)
- [ ] Document upload + chunking + embedding
- [ ] Vector search during calls
- [ ] Dashboard: tool configuration UI
- [ ] Dashboard: knowledge base management
- [ ] Pre-built integrations: Shopify, Calendly

### Sprint 6 (Week 11-12): Analytics, QA, Polish, Launch

**Analytics dashboard:**
- Total calls, AI containment rate, avg call duration
- Cost savings calculator ("You saved $X vs human agents")
- Per-agent performance comparison
- Sentiment distribution (positive/neutral/negative)
- Peak hours heatmap
- Escalation reasons breakdown

**Quality Assurance (automated):**
- Every call scored: accuracy, tone, resolution
- Flag risky calls (PII detected, angry callers)
- Weekly QA summary email to customer
- Compliance checks (did AI follow the script?)

**Playground (in-browser testing):**
- WebRTC connection from browser → VoxBridge
- Talk to your AI agent before deploying
- See real-time transcript + LLM reasoning

**Launch:**
- Product Hunt launch
- Hacker News Show HN
- Twitter/LinkedIn content
- Landing page with demo video
- Documentation site

---

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                    DASHBOARD (React)                          │
│                                                              │
│  Agent Builder │ Call Logs │ Phone Numbers │ Analytics │ QA   │
│  Knowledge Base │ Integrations │ Playground │ Billing         │
└──────────────────────────┬───────────────────────────────────┘
                           │ REST API
┌──────────────────────────▼───────────────────────────────────┐
│                   PLATFORM API (FastAPI)                       │
│                                                              │
│  Agents │ Calls │ Numbers │ Knowledge Base │ Tools │ Billing  │
│  Webhooks (Twilio/Telnyx) │ Usage Metering │ Auth             │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│                  AI PIPELINE ENGINE (new)                      │
│                                                              │
│  ┌─────────┐    ┌──────────┐    ┌─────────┐                 │
│  │   STT   │ →  │   LLM    │ →  │   TTS   │                 │
│  │Deepgram │    │ OpenAI   │    │11Labs   │                 │
│  │Google   │    │ Claude   │    │OpenAI   │                 │
│  │Azure    │    │ Custom   │    │Azure    │                 │
│  └────┬────┘    └────┬─────┘    └────┬────┘                 │
│       │              │               │                       │
│  Turn Detection │ Function Calling │ Barge-in               │
│  Escalation     │ Knowledge (RAG)  │ Context                │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│               VOXBRIDGE BRIDGE (existing)                     │
│                                                              │
│  Codec Engine │ VAD │ Session Manager │ Event System          │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│              TELEPHONY LAYER (existing)                       │
│                                                              │
│  Twilio │ Telnyx │ Genesys │ Avaya │ Cisco │ Amazon Connect  │
│  FreeSWITCH │ Asterisk │ Generic SIP                         │
└──────────────────────────────────────────────────────────────┘
```

---

## Competitive Position

| Feature | Genesys | Five9 | Vapi | Retell | **VoxBridge** |
|---------|---------|-------|------|--------|---------------|
| **Primary user** | Human agents | Human agents | Developers | Developers | **Businesses** |
| **Pricing** | $75-240/seat | $119-299/seat | $0.05+/min | $0.07+/min | **$0.05/min** |
| **AI agents** | Add-on | Add-on | Core | Core | **Core** |
| **Human escalation** | Core | Core | DIY | DIY | **Built-in** |
| **Phone numbers** | Separate | Included | Included | Included | **Included** |
| **Dashboard** | Enterprise-grade | Enterprise-grade | Developer | Developer | **Business-grade** |
| **Function calling** | Via bots | Via bots | Yes | Yes | **Yes** |
| **Knowledge base** | Separate | Separate | No | No | **Built-in** |
| **QA / Analytics** | Add-on ($$$) | Add-on | No | Basic | **Built-in** |
| **Genesys migration** | N/A | No | No | No | **Yes** |
| **Self-serve** | No (needs SI) | Demo-first | Yes | Yes | **Yes** |
| **Time to deploy** | Months | Weeks | Hours | Hours | **Minutes** |
| **Target company size** | 500+ agents | 100+ agents | Any | Any | **5-500 agents** |

### Our Moat (In Order of Defensibility)
1. **8 telephony serializers** — nobody else has native Genesys/Avaya/Cisco/Amazon Connect
2. **Business-grade UX** — not developer-focused like Vapi, not enterprise-complex like Genesys
3. **Usage-based pricing** — no per-seat costs, aligns with AI-first model
4. **Built-in escalation** — companies can't go full AI overnight, they need the safety net
5. **Open-source core** — trust + adoption + community contributions
6. **Enterprise migration path** — "start with 10% of calls, grow to 80%"

---

## Go-to-Market: Land and Expand

### Phase 1 (Month 1-3): Developer/Hacker Audience
- Launch on Product Hunt, HN, Twitter
- Free tier: 100 min/month
- Target: Indie hackers, SaaS founders, agencies building for clients
- Goal: 500 signups, 50 paying customers

### Phase 2 (Month 4-6): SMB Direct Sales
- Content marketing: "How Company X replaced their call center with AI"
- Case studies from Phase 1 customers
- SEO: "AI call center", "replace IVR with AI", "virtual receptionist"
- Partner with Shopify/Calendly for e-commerce + scheduling use cases
- Goal: 200 paying customers, $30K MRR

### Phase 3 (Month 7-12): Mid-Market
- Sales team (1-2 AEs)
- POC program: "Try VoxBridge on your FAQ calls for free for 30 days"
- Enterprise connectors (Genesys, Amazon Connect)
- SOC 2 certification
- Goal: 50 mid-market customers, $150K MRR

### Phase 4 (Year 2): Enterprise
- Dedicated sales team
- SI partnerships (Accenture, Deloitte)
- Industry-specific solutions (healthcare, insurance, banking)
- Goal: $1M+ MRR, Series A fundraise
