# Domain Pitfalls: AI Business Scanner Telegram Bot

**Domain:** AI-powered paid Telegram bot with Russian payment processing and content automation
**Researched:** 2026-03-19
**Confidence note:** Web search and WebFetch were unavailable. All findings are based on training knowledge (cutoff August 2025). Confidence levels reflect this constraint honestly.

---

## Critical Pitfalls

Mistakes that cause rewrites, legal exposure, or unrecoverable trust damage.

---

### Pitfall 1: Telegram Stars vs ЮKassa — Wrong Payment Architecture from Day One

**What goes wrong:**
Team builds the entire payment flow around one provider, then discovers it cannot support a core use case. Telegram Stars cannot be withdrawn as RUB — they convert at a fixed rate and are paid out only as Stars to other Telegram services. ЮKassa requires a registered Russian legal entity (ИП or ООО) and a signed contract; onboarding takes 2-5 business days. If you launch without resolving this, you either cannot take money or cannot withdraw it.

**Why it happens:**
Telegram Stars look like the easy path (no external integration), but the economics only work if you are reinvesting inside the Telegram ecosystem. ЮKassa looks like the obvious RUB path, but developers underestimate the onboarding time and legal prerequisites.

**Consequences:**
- Launch blocked waiting for payment provider approval
- Revenue stuck in Stars with no RUB exit
- Emergency rewrite of payment flow mid-launch
- Lost early adopter trust if payment fails at checkout

**Prevention:**
- Decide on payment strategy in Phase 1, before any code
- If using ЮKassa: start the legal entity registration and ЮKassa onboarding in parallel with development, not after
- For MVP: use Telegram Stars only if Юлия accepts that revenue stays in Telegram ecosystem until critical mass
- For real RUB revenue from day one: ЮKassa is the only path; account for 2-5 week setup lead time

**Detection (warning signs):**
- "We'll figure out payments later" attitude during planning
- No ИП/ООО registered when development starts
- Assuming Telegram Stars can be withdrawn as cash

**Phase:** Address in Phase 1 (Foundation). Do not write payment code until provider is contractually confirmed.

**Confidence:** MEDIUM — ЮKassa onboarding requirements and Stars economics are well-documented in training data; specific timelines may vary.

---

### Pitfall 2: Claude API Costs Blowing Up on Uncontrolled Input

**What goes wrong:**
Each full scan sends large, multi-section prompts to Claude (questionnaire answers + free text + numerology context + system prompt). With claude-sonnet-class models, a single scan easily costs $0.05–$0.20+ in API fees. At 3500₽ per scan (~$40 at current rates), the margin looks fine. But uncontrolled prompt growth (adding more context, conversation history, longer system prompts) silently erodes margin. At scale or with subscription users running multiple scans, the unit economics invert.

**Why it happens:**
- Developers add context to improve quality without tracking token count
- Subscription model ("unlimited scans") has no natural cost ceiling
- System prompt grows over iterations without audit
- Appending full conversation history instead of summarizing it

**Consequences:**
- $0.50–$2.00 API cost per scan for complex cases
- Subscription model becomes loss-making
- Emergency prompt cuts degrade quality mid-product

**Prevention:**
- Set hard token budgets per scan: measure actual token count in staging before launch
- Log `input_tokens` and `output_tokens` from every Claude API response from day one
- For subscription tier: either cap scans per month (e.g. 5/month) or use a cheaper model (claude-haiku) for re-scans
- Keep system prompt under 2000 tokens; audit it at every sprint
- Use prompt compression: summarize previous context, don't append raw history

**Detection (warning signs):**
- Not logging Claude API usage costs per request
- System prompt exceeds 3000 tokens
- "Unlimited" subscription with no scan limits defined

**Phase:** Address in Phase 1 (AI core design). Implement cost logging before any production traffic.

**Confidence:** HIGH — Claude API pricing tiers and token cost structure are well-established.

---

### Pitfall 3: ЮKassa Digital Goods Fiscal Requirements (54-ФЗ)

**What goes wrong:**
Russian law (54-ФЗ) requires a fiscal receipt (чек) for every online payment, including digital services sold via Telegram bots. ЮKassa has built-in fiscal integration, but it must be configured correctly: you must specify the correct tax system (УСН, ОСНО), VAT rate, and payment subject type (service vs. digital goods). Getting this wrong means operating illegally, with fines starting at 10,000₽ per violation and potential account freezes.

**Why it happens:**
Developers treat payment integration as a technical task and hand off fiscal configuration to "accountant later." ЮKassa's test environment does not enforce fiscal receipt generation, so the problem is invisible until production.

**Consequences:**
- Tax authority fines
- ЮKassa account suspension
- Having to rebuild fiscal integration post-launch
- Stress and legal exposure for Юлия as ИП

**Prevention:**
- Consult a Russian accountant before writing any payment code — determine tax system and correct item types
- Use ЮKassa's built-in fiscal receipt functionality (`receipt` object in payment creation) from day one
- Test fiscal receipts in staging using ЮKassa's test mode with receipt generation enabled
- Set `payment_subject: "service"` and correct VAT rate per accountant advice

**Detection (warning signs):**
- Payment integration built without `receipt` object in API calls
- No accountant consulted during development
- "We'll add fiscal receipts later"

**Phase:** Address in Phase 1. Fiscal configuration is a prerequisite for any live payment, not a nice-to-have.

**Confidence:** MEDIUM — 54-ФЗ requirements are stable law; specific ЮKassa API field names may have changed since training cutoff.

---

### Pitfall 4: Hallucination Presented as Expert Diagnosis

**What goes wrong:**
The product's core value proposition is "diagnosis as precise as a personal consultation." Claude will generate confident, specific-sounding text about money leaks, team problems, and owner psychology — regardless of whether the input actually supports those conclusions. Users who get a scan that describes their situation inaccurately lose trust permanently and publicly (Telegram communities are vocal).

**Why it happens:**
- Prompt does not constrain Claude to only draw conclusions supported by provided data
- System prompt encourages "specific, actionable" output, which Claude interprets as "be confident even with thin data"
- No validation layer between Claude output and user delivery
- Short questionnaire cannot produce enough signal for all scan dimensions

**Consequences:**
- Refund demands ("the AI made things up about me")
- Negative word-of-mouth in the exact Telegram communities that are the funnel
- Trust destruction for Юлия's personal brand

**Prevention:**
- Prompt engineering: explicitly instruct Claude to say "insufficient data to assess [X]" when the questionnaire doesn't cover a dimension
- Build a confidence/completeness check into the prompt: "if fewer than 3 signals support a conclusion, flag it as hypothesis not diagnosis"
- Include a disclosure in the scan output: "Разбор основан на предоставленных данных. Для точной диагностики рекомендуем личную консультацию"
- Start with a narrower scan scope (2-3 dimensions) where quality can be controlled, expand later
- Human review for first 20-30 scans: Юлия reads outputs and calibrates prompts before fully autonomous operation

**Detection (warning signs):**
- Prompt instructions say "be specific and actionable" without "only based on provided data"
- No disclaimer in output template
- No human review of early outputs

**Phase:** Address in Phase 1 (prompt design) and Phase 2 (quality review loop before scaling).

**Confidence:** HIGH — LLM hallucination behavior in structured-output tasks is well-understood.

---

### Pitfall 5: Telegram Channel Autoposting Bot Limitations

**What goes wrong:**
Telegram bots cannot post to channels they do not administer. To autopost to @Reva_mentor, the bot must be added as a channel admin. This works, but Telegram throttles bots posting to channels: maximum ~20 messages per minute, and channels with large audiences can trigger spam detection if messages arrive in bursts. Additionally, Telegram does not provide a native scheduling API — scheduling must be implemented entirely on the bot's infrastructure side, which means the scheduler must be always-on (no serverless).

**Why it happens:**
Developers assume Telegram has a scheduling endpoint or that posting is unconstrained. They also conflate "posting as bot" with "posting as user" — bots cannot post as a human user identity even if given admin rights.

**Consequences:**
- Autoposting silently fails when bot loses admin status (channel admin changes)
- Scheduler crashes and posts resume in a burst, triggering Telegram flood limits
- Content appears with bot username, not Юлия's name (visual mismatch)

**Prevention:**
- Bot must be a permanent channel admin — document this operational requirement
- Use a persistent scheduler (n8n self-hosted, or a cron on a VPS) not serverless functions for posting
- Rate-limit post dispatches to maximum 1 per minute for safety
- Implement a dead-letter queue: if post fails, retry after 10 minutes, not immediately
- For posts to appear "as Юлия": use a user bot (via Telethon/Pyrogram with a real phone number) — but this carries ban risk if Telegram detects automation; evaluate carefully

**Detection (warning signs):**
- Scheduler implemented as a serverless function (Lambda, Cloud Functions)
- No retry logic for failed posts
- No monitoring on bot admin status in channel

**Phase:** Address in Phase 2 (content automation). Do not build autoposting on serverless architecture.

**Confidence:** MEDIUM — Telegram Bot API posting constraints are stable; specific rate limits may change.

---

## Moderate Pitfalls

---

### Pitfall 6: Payment State Machine Not Handling Async Webhooks

**What goes wrong:**
ЮKassa payment status updates arrive asynchronously via webhook, often seconds after the user sees "payment successful" in their Telegram app. If the bot grants access (sends the scan or activates subscription) based on the payment initiation event rather than the confirmed webhook, users can exploit this window. If the bot waits for the webhook before responding, users see a frozen bot and assume it broke.

**Prevention:**
- Implement a proper payment state machine: `pending → awaiting_confirmation → confirmed → fulfilled`
- On payment initiation: show "Ждем подтверждения оплаты... обычно 10-30 секунд"
- Grant access only after receiving confirmed webhook with `status: succeeded`
- Set a timeout (5 minutes): if no confirmation, show "Что-то пошло не так, напиши нам"
- Log all state transitions with timestamps for debugging

**Phase:** Phase 1 (payment integration). Non-negotiable for correctness.

**Confidence:** HIGH — async webhook handling is a universal payment integration requirement.

---

### Pitfall 7: Claude API Rate Limit Errors Under Burst Load

**What goes wrong:**
If multiple users complete questionnaires simultaneously (e.g., after a post in @Reva_mentor goes viral), Claude API receives simultaneous requests. On starter tiers, rate limits are low (e.g., 50 requests/minute on Tier 1). API returns 429 errors. The bot shows an error or hangs.

**Prevention:**
- Implement a request queue with concurrency limit (max 3-5 simultaneous Claude calls)
- On queue overflow: "Разбор поставлен в очередь, придет в течение 5 минут"
- Monitor rate limit response headers and implement exponential backoff
- Upgrade Claude API tier proactively when subscriber count exceeds 50

**Phase:** Phase 1 (AI integration). Queue from the start; upgrading tier is operational.

**Confidence:** MEDIUM — rate limit specifics vary by tier and change; queue pattern is universally correct.

---

### Pitfall 8: Inconsistent Report Quality Across Users

**What goes wrong:**
Two users with similar businesses get noticeably different quality scans — one gets specific, useful insights; another gets generic boilerplate. This happens when the questionnaire has optional fields that vary completion rates, when Claude's non-deterministic output varies significantly at high temperature, or when different Claude model versions are deployed without versioning.

**Prevention:**
- Pin the Claude model version explicitly (e.g., `claude-sonnet-4-5` not `claude-sonnet-latest`) — update deliberately, not automatically
- Set temperature to 0.3-0.5 for diagnostic output (enough creativity, not chaos)
- Require minimum completeness on questionnaire before allowing scan generation: if fewer than 70% of questions answered, prompt user to complete
- Store prompt version alongside each scan result in DB — allows debugging quality issues

**Phase:** Phase 1 (prompt engineering). Version pinning is a one-line change with high impact.

**Confidence:** HIGH — Claude versioning and temperature effects are well-documented.

---

### Pitfall 9: Refund Policy Not Defined Before Launch

**What goes wrong:**
A user pays 3500₽, gets a scan they consider useless, and demands a refund. Without a stated policy, Юлия faces a social media dispute in her own community. With a stated policy but no technical refund flow, refunds require manual ЮKassa dashboard actions and manual DB updates.

**Prevention:**
- Define refund policy before launch: recommended "нет возврата на цифровые услуги" + "один бесплатный пересчет если не устроил результат" as a goodwill gesture
- Publish policy in bot (visible before payment, not after)
- Build a simple admin command (`/refund <user_id>`) that triggers ЮKassa refund API and revokes access in one action
- Per Russian law (Закон о защите прав потребителей): digital services delivered are generally non-refundable, but document delivery confirmation

**Phase:** Phase 1 (before launch). Policy is business decision; technical refund flow is Phase 1 requirement.

**Confidence:** MEDIUM — Russian consumer law basics are stable; consult a lawyer for definitive guidance.

---

### Pitfall 10: Subscription Expiry Not Enforced Reliably

**What goes wrong:**
Subscription is stored as a DB record with `expires_at`. If the check runs on every message, it's fine. If the bot crashes and restarts, or if the check is lazy (only at scan start, not at questionnaire step 1), users whose subscription expired mid-questionnaire complete their scan for free.

**Prevention:**
- Check subscription status at every scan initiation, not just at payment
- Use DB-level expiry check with UTC timestamps (avoid timezone bugs)
- Run a daily cron job that marks expired subscriptions and notifies users 3 days before expiry
- Do not rely on in-memory state for subscription status — always query DB

**Phase:** Phase 1 (data model) and Phase 2 (subscription management).

**Confidence:** HIGH — standard subscription management pattern.

---

## Minor Pitfalls

---

### Pitfall 11: Bot Blocked by User = Silent Failure on Notifications

**What goes wrong:**
When a user blocks the bot, any attempt to send them a message (subscription expiry notice, scan ready notification) throws a `403 Forbidden` error. If unhandled, this floods logs and can cause retry loops.

**Prevention:**
- Catch `BotBlocked` / `UserDeactivated` exceptions on all send operations
- Mark user as `bot_blocked = true` in DB; stop sending to them
- Do not retry blocked users

**Phase:** Phase 2.

**Confidence:** HIGH.

---

### Pitfall 12: Telegram Message Length Limits

**What goes wrong:**
Claude generates a detailed business scan report — easily 2000-4000 characters. Telegram's message limit is 4096 characters. Reports that exceed this limit either fail to send or get cut off mid-sentence.

**Prevention:**
- Post-process Claude output: split at logical section boundaries (not mid-word)
- Send as 2-3 sequential messages with section headers
- Alternatively, render as a PDF or image (more complex, better UX for longer reports)
- Test with maximum-length Claude output in staging

**Phase:** Phase 1.

**Confidence:** HIGH — 4096 character limit is a stable Telegram API constraint.

---

### Pitfall 13: Social Media Analysis Scope Creep and Failure Modes

**What goes wrong:**
The project scope includes scanning "соцсети / сайт бизнеса." Web scraping social media is legally and technically fragile: Instagram blocks automated access, VKontakte has API rate limits, websites block bots via Cloudflare. If the scan depends on this data and it fails silently, Claude receives no input and generates generic output — delivered as if real analysis occurred.

**Prevention:**
- Treat social media analysis as optional enrichment, not required input
- If URL fetch fails: explicitly tell the user "не удалось получить данные сайта" and proceed without it
- Do not present Claude's output as "analysis of your website" if the fetch failed
- Start with URL-optional scanning; add robust scraping only after core product is stable

**Phase:** Phase 2 or later. Do not build social scanning as MVP dependency.

**Confidence:** MEDIUM — social media scraping fragility is well-known; specific platform policies change frequently.

---

### Pitfall 14: Numerology/Astrology Content and Platform Risk

**What goes wrong:**
The scan includes numerology-based "цифровой архетип." Anthropic's usage policies restrict generating content that could be considered deceptive or that makes false factual claims. If prompts instruct Claude to present numerological analysis as factual psychological diagnosis, this risks content filtering or future policy violations.

**Prevention:**
- Frame numerology output explicitly as "архетипический подход" or "символический разбор," not "научный анализ"
- Include a disclaimer in the system prompt and in output: "Нумерологический компонент носит метафорический характер"
- Test prompts against Anthropic's content policy — if Claude refuses or hedges, adjust framing
- Separate the numerology section visually from the "concrete business analysis" sections

**Phase:** Phase 1 (prompt design).

**Confidence:** MEDIUM — Anthropic policy direction is clear; specific enforcement thresholds are not precisely documented.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Payment provider selection | Choosing Stars without RUB exit plan | Decide provider before any code; start ЮKassa legal onboarding early |
| Fiscal receipt setup | Missing 54-ФЗ compliance | Consult accountant; implement `receipt` object from first payment |
| Claude prompt design | Hallucination in diagnostic output | Constrain to evidence-based conclusions; require "insufficient data" acknowledgment |
| Claude prompt design | Numerology framing as fact | Frame as symbolic/archetypal, include disclaimer |
| Claude integration | Cost blowup on complex scans | Log tokens per request; audit system prompt size; cap subscription scans |
| Claude integration | Rate limit burst errors | Implement request queue from day one |
| Report delivery | Message length overflow | Split at section boundaries; test with max-length output |
| Subscription model | Expiry not enforced | DB-level check on every scan; UTC timestamps; expiry cron |
| Payment flow | Async webhook race condition | Full state machine; grant access only on confirmed webhook |
| Refund handling | No policy or no technical flow | Define policy pre-launch; build admin refund command |
| Content autoposting | Serverless scheduler failure | Use persistent VPS cron or n8n; implement dead-letter queue |
| Social media scraping | Silent failure on blocked URLs | Make optional; surface failure explicitly to user |
| User management | Blocked user notification loops | Catch BotBlocked; mark in DB; stop retrying |

---

## Sources

**Confidence assessment:**
- Telegram Bot API payment and posting constraints: MEDIUM (stable API but web access unavailable to verify current docs)
- Claude API cost structure and rate limits: HIGH (pricing tiers well-established in training data; verify current tier limits at docs.anthropic.com)
- ЮKassa and 54-ФЗ requirements: MEDIUM (stable law and well-documented provider; verify specific API field names against current ЮKassa docs)
- LLM hallucination patterns and mitigation: HIGH (extensively documented in ML literature)
- Subscription/payment state machine patterns: HIGH (universal software engineering patterns)

**Recommended verification before Phase 1:**
- [docs.anthropic.com/en/api/rate-limits](https://docs.anthropic.com/en/api/rate-limits) — current tier limits and pricing
- [yookassa.ru/developers](https://yookassa.ru/developers) — current receipt API fields and digital goods requirements
- [core.telegram.org/bots/payments](https://core.telegram.org/bots/payments) — current Stars and provider payment rules
- Consult a Russian accountant on 54-ФЗ specifics for ИП selling digital services via Telegram
