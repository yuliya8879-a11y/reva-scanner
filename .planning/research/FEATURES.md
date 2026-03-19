# Feature Landscape: Reva Scanner

**Domain:** AI-powered business diagnostic / coaching bot (Telegram, Russian market)
**Researched:** 2026-03-19
**Confidence note:** WebSearch and WebFetch were unavailable during this session. All findings are based on training knowledge of the Telegram bot ecosystem, Russian InfoBiz market (2023–2025), AI coaching product patterns, and payment UX. Confidence levels are assigned honestly per gap.

---

## Table Stakes

Features users expect. Missing = product feels broken, users leave or ask for refunds.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Onboarding message with clear value prop | First message must answer "what do I get?" in 2 sentences | Low | Users arrive from TG channel already warm; no long intros |
| Structured questionnaire flow (10–20 questions) | Without it the "scan" has no inputs; core mechanic | Medium | Button-based answers where possible, reduce friction |
| Payment gate before full report | Monetization requires it; users expect it after seeing mini-result | Medium | ЮKassa or Telegram Stars; must work without leaving Telegram |
| Payment confirmation + access unlock | Without instant unlock users panic and message support | Low | Webhook-driven; must be <5s latency |
| Full diagnostic report delivery in bot | Report delivered as formatted Telegram message(s) or PDF link | Medium | Long messages need splitting or web view |
| Free mini-scan (lead magnet) | Funnel from channel requires a taste before paying | Medium | 3–5 questions → teaser result → upsell to full scan |
| Session state persistence | If user closes bot mid-flow, must resume from same question | Medium | DB-backed session; critical for completion rate |
| Basic error handling + fallback messages | Payment failure, API timeout — must never go silent | Low | Dead silence = user thinks scam |
| /start command reset | Users re-enter the bot; must always work cleanly | Low | Idempotent start flow |
| Results saved per user | User wants to reference their report later | Low | Store report in DB linked to user_id |

**Confidence:** HIGH (these patterns are consistent across all Telegram bot products with payment gates)

---

## Differentiators

Features that set this product apart. Not expected by default, but become the reason users pay and refer others.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Numerology layer (birth date analysis) | Makes the report feel personally calibrated, not generic | Medium | Pythagorean or Chaldean numerology logic; owner archetypes map to business patterns |
| Social media / site analysis | Scans the public digital footprint — unique and high-perceived-value | High | URL input → scrape or use Jina/Firecrawl → summarize into prompt |
| Free-text situation analysis | AI extracts hidden patterns from owner's own words — feels like a therapist read their mind | Medium | Prompt engineering to surface cognitive distortions, avoidance patterns |
| Named diagnosis categories | "Money leaks", "Blind spots", "Energy blocks" — branded language creates emotional resonance | Low | Pure copy/prompt design, no extra code |
| Personalized report (not template) | Claude generates unique text per user, not fill-in-the-blank | Low | Claude API call with full context; cost ~10–20 RUB per report |
| Report PDF with branding | Professional artifact user can share; increases perceived value | Medium | pdf-lib or WeasyPrint; Telegram bot sends file |
| Subscription with history dashboard | Repeat users can track changes across scans | High | Requires web app; defer to v2 |
| Content generation for owner (Reels scripts, posts) | Rare in diagnostic bots; positions product as ongoing tool not one-shot | High | Separate flow; content plan generation |
| Referral mechanic | Word-of-mouth amplifier in InfoBiz community | Medium | /referral code → discount or free scan credit |
| "What changed" re-scan comparison | User re-scans 30 days later; bot shows delta | High | Requires storing first scan answers; diff logic |

**Confidence:** MEDIUM (differentiators inferred from InfoBiz market patterns and comparable products like Ясно-бот, астро-разборы in TG; no direct competitor URL was fetched)

---

## Anti-Features

Features to deliberately NOT build in v1. They add complexity without proportional value at launch.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| In-bot live chat / Q&A after report | Requires human time or complex AI context management; blurs product boundaries | Redirect to Юлия's consultation booking for follow-up questions |
| Multi-language support (EN, etc.) | Russian InfoBiz market is the target; translation adds copy and prompt complexity | Stay RU-only until clear demand |
| Full web app (v1) | Extra surface, extra auth, extra infra; most users live in Telegram | Build web only after bot proves product-market fit |
| Payment on website (outside Telegram) | Breaks the native Telegram flow; conversion drops | Keep payment inside bot via inline keyboard |
| User onboarding wizard with 30+ questions | Drop-off rate increases sharply after ~15 questions | Cap questionnaire at 12–15 questions max; use smart branching |
| Automated social media posting to client's account | Requires OAuth to their accounts; complex trust/auth problem | Auto-post only to Юлия's channel (@Reva_mentor), not to clients |
| AI chat "talk to your report" feature | Impressive in demos, adds LLM cost and session complexity without proven user need | Defer; v2 candidate if retention data supports it |
| Gamification (scores, badges, leaderboards) | Mismatches the serious "business diagnosis" tone | Use progress indicators only (question X of Y) |
| Team member sub-accounts | Users are solo owners or small teams; complexity not justified | Single user = single account in v1 |
| Stripe / international payments | Russian market uses ЮKassa; Stripe not usable for RU residents | ЮKassa + Telegram Stars only |

**Confidence:** HIGH (anti-features are based on known Telegram bot product failure modes and Russian payment infrastructure constraints)

---

## Feature Dependencies

```
Free mini-scan (lead magnet)
  → Questionnaire flow (shared engine)
  → Teaser report generation (Claude API, short prompt)
  → Upsell message with payment CTA

Payment gate
  → ЮKassa webhook integration
  → Session state update (paid = true)
  → Full scan unlock

Full diagnostic report
  → Questionnaire answers (all 12–15 questions)
  → Birth date / numerology computation
  → Free-text analysis (Claude)
  → Social media URL analysis (scrape → Claude)
  → Report generation (Claude, structured prompt)
  → Report delivery (Telegram message split or PDF)

Content generation (TG channel)
  → Separate admin command or bot flow
  → Claude generates post / Reels script / content plan
  → Auto-posting requires Telegram Bot API scheduled sends or n8n

Subscription
  → Payment gate (recurring billing via ЮKassa)
  → User state: subscription_active, expires_at
  → Gate check on each scan start
```

---

## MVP Feature Priority

**Build in v1 (core loop must work):**

1. Onboarding flow with value prop and mini-scan offer
2. Mini-scan (5 questions → teaser report → upsell)
3. Payment gate (ЮKassa, one-time 3500₽)
4. Full questionnaire (12–15 questions, button-driven)
5. Numerology computation from birth date
6. Free-text situation field
7. Social media URL input (basic: paste URL, Claude summarizes)
8. Full report generation via Claude API
9. Report delivery as formatted Telegram messages
10. Session persistence (resume on return)
11. Results stored in DB per user

**Build in v1 (content side, Юлии нужно):**

12. Content generation command (admin-only or separate bot)
13. Auto-posting to @Reva_mentor via scheduler

**Defer to v2:**

- PDF report with branding
- Web app personal cabinet
- Subscription model (monthly recurring)
- "What changed" re-scan comparison
- Referral mechanic
- Report sharing / screenshot card

---

## What Makes Users Pay 3500₽

This is the key question. Based on InfoBiz market patterns (HIGH confidence for the market, MEDIUM for the specific price point):

**1. Perceived expert behind the product.** Users pay for "Юлия Рева's analysis", not "a bot." The bot must feel like it channels a specific expert's methodology. Every output line must sound like something Юлия would say. Generic AI outputs kill conversion.

**2. Specificity of diagnosis.** The output must name concrete things: "your Instagram bio signals price apologetics — you're undercharging." Generic outputs ("focus on your marketing") feel like a chatbot and justify refund demands.

**3. The aha-moment in mini-scan.** If the free teaser report says something true and slightly uncomfortable, users believe the full report will reveal more. The mini-scan is the sales engine.

**4. Friction is low enough to complete.** If the questionnaire drops users at question 7, no payment happens. Button-driven UX, no long text fields (except one optional free-text), no email required, no registration.

**5. Instant delivery.** Report appears within 60 seconds of payment. Waiting 10 minutes destroys trust.

**6. The "numerology hook."** In the Russian InfoBiz/spiritual-business niche, numerology legitimizes the "this is about YOU specifically" feeling. It makes the report feel non-replicable — even if two users have similar businesses, their reports will differ because their birth dates differ.

---

## Report Quality Requirements

The report is the product. Quality is determined by:

| Dimension | Requirement | Failure Mode |
|-----------|-------------|--------------|
| Specificity | References user's actual answers verbatim | "Your business may have issues" — refund demanded |
| Structure | Clear sections with bold headers (Telegram markdown) | Wall of text — user stops reading |
| Actionability | Each section ends with 1–2 concrete next steps | Pure diagnosis without direction — feels useless |
| Tone | Direct, slightly confrontational — like a mentor, not a therapist | Too soft = "this could have been a horoscope" |
| Length | 800–1500 words per full report (7–12 Telegram messages) | Too short = feels cheap; too long = not read |
| Personalization signal | Must use owner's name, business niche, specific numbers they gave | Generic = "this is just ChatGPT" |

**Confidence:** MEDIUM (based on comparable products in the niche; no A/B test data available)

---

## Content Automation Features (TG Channel)

| Feature | Description | Complexity | Priority |
|---------|-------------|------------|---------|
| Post generation | Prompt → Claude → formatted TG post (700–1200 chars) | Low | High |
| Reels script | Prompt with hook/body/CTA structure → Claude | Low | High |
| Monthly content plan | Topic list with publish dates and angles | Medium | Medium |
| Auto-posting scheduler | Bot sends posts to channel at scheduled time | Medium | Medium |
| Content calendar view | Admin sees what's scheduled | Medium | Low |
| Image prompt suggestions | Claude suggests image concept for each post | Low | Low |

**Auto-posting technical note:** Telegram Bot API supports `sendMessage` with `chat_id` of a channel where bot is admin. Scheduling requires a cron job or n8n. No external service needed for basic scheduling.

---

## Onboarding Flow Design

The flow that converts a channel subscriber into a paying user:

```
[User clicks /start or link from channel]
  ↓
Welcome message: 1 screen, bold value prop, Юлия's face/name prominent
  ↓
"Start free mini-scan" button
  ↓
5 questions (button answers, <2 min)
  Q1: Your niche / type of business
  Q2: Monthly revenue range
  Q3: Biggest current pain (multiple choice)
  Q4: Team size
  Q5: How long in business
  ↓
"Analyzing..." (2-3 sec typing indicator)
  ↓
Mini-report: 3–4 sentences, name 1 specific problem pattern
  ↓
"Your full scan reveals [X more issues]. Get it now for 3500₽"
  ↓
[Pay button → ЮKassa invoice]
  ↓
Payment confirmed → "Starting full scan..."
  ↓
Birth date question
  ↓
10 business questions (button-driven)
  ↓
Free-text: "Describe your situation in 3–5 sentences"
  ↓
Social media URL (optional but strongly encouraged)
  ↓
"Scanning..." (30–60 sec, typing indicator active)
  ↓
Full report delivered in sections
  ↓
Closing CTA: subscription offer or "share your result"
```

**Completion rate risk:** Drop-off happens most at: (1) between mini-scan and payment, (2) at free-text question. Keep free-text optional with a fallback default.

---

## Sources

- Training knowledge: Telegram Bot API behavior, ЮKassa integration patterns (HIGH confidence)
- Training knowledge: Russian InfoBiz/coaching market product patterns 2023–2025 (MEDIUM confidence)
- Training knowledge: AI report quality patterns from comparable products (MEDIUM confidence)
- Training knowledge: Numerology-in-coaching niche positioning (MEDIUM confidence)
- No external URLs fetched (WebSearch and WebFetch unavailable in this session)

**Gaps requiring validation:**
- Competitor analysis: direct Telegram bots in the "business diagnostic" niche (search manually: @aicoach_bot, similar)
- Actual conversion rates for 3500₽ price point in this niche
- Whether Telegram Stars (vs ЮKassa) converts better for the target audience
- Legal requirements for "numerology" framing in a commercial context (disclaimer needed)
