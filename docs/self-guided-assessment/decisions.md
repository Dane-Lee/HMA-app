c# Self-Guided Employee Assessment — Decision Doc

A future build attached to the existing HMA app. Workers receive a link, log in, complete the 5-movement assessment on their own time, and submit videos + scores for provider review.

The 8 questions below drive scope and architecture. Pick an answer for each, then we can size the work.

Format per question:
- **Question** — the decision to make.
- **Why it matters** — what it unlocks or constrains downstream.
- **Options** — the realistic choices.
- **Recommended default** — what I'd pick if you said nothing.
- **Your answer** — fill in here.

---

## 1. Auth model

**Question:** How does an employee prove they are the right person before submitting an assessment?

**Why it matters:** This is the single largest piece of unbuilt backend. It drives database tables, password/token storage, password reset flows, account lockout, session handling, and the entire UX of "getting in." Today the app has one shared PIN — that does not scale to per-employee submissions.

**Options:**
- **A. Magic link only** — Provider (or system) sends a one-time link. Click → logged in for one session. No password.
- **B. Per-employee account with password** — Employee sets a password, can come back later. Adds password reset, lockout, etc.
- **C. Pre-distributed access codes** — Employee gets a code on paper or by email; they enter it on the site. No real account, just code-as-credential.
- **D. SSO / employer identity** — Employee logs in with their Hendrickson (or whoever) corporate identity.

**Recommended default:** **A. Magic link only.** Lowest friction for one-and-done assessments, fewest moving parts to maintain, no password storage burden. Easiest to layer in expiration (link valid for 7 days). Re-issuable if needed.

**Your answer:** **A. Magic link only.**

---

## 2. Link delivery

**Question:** How does the link actually get to the employee?

**Why it matters:** Determines whether you need an outbound email/SMS provider, templates, bounce handling, etc. — or whether you just paste a URL into your existing communication channel.

**Options:**
- **A. Manual** — You generate the link in the provider UI, copy it, send it via your own email/text/whatever.
- **B. App-sent email** — App sends the link from a `noreply@` address on link creation.
- **C. App-sent SMS** — Same as B but text.
- **D. Both B and C, employee chooses.**

**Recommended default:** **A. Manual** for the pilot. You're the only provider, volume is low, and email infrastructure (SES/SendGrid/Postmark, DKIM/SPF setup, bounce handling) is a real project. Add B once you have more than ~10 employees per week using it.

**Your answer:** **A. Manual**


---

## 3. Tenancy

**Question:** Is this app designed for one provider org (you/ATI serving Hendrickson), or multiple provider orgs from day one?

**Why it matters:** Multi-tenancy retrofitted later is painful. Designing for it now adds modest schema complexity (an `organization_id` on most tables, role-scoping queries) but locks in nothing.

**Options:**
- **A. Single-tenant** — One ATI provider, one Hendrickson worker pool. Simplest schema.
- **B. Multi-tenant by employer** — Multiple worksite clients (Hendrickson + future), each isolated.
- **C. Multi-tenant by provider** — Multiple ATI providers reviewing different worker pools.
- **D. Both B and C.**

**Recommended default:** **A. Single-tenant** for now, but design the employee table with an `employer` field from day one so a future migration to B is mechanical, not a rewrite. Don't pay for C until you actually have multiple providers.

**Your answer:** **A. Single-tenant** for now, but design the employee table with an `employer` field from day one so a future migration to B is mechanical, not a rewrite.


---

## 4. Camera operator assumption

**Question:** What does the worker physically do with the phone during recording?

**Why it matters:** This is the biggest practical risk to whether you get usable video. A worker holding a phone cannot film their own forward lunge from the side. The flow must commit to a model and coach for it explicitly.

**Options:**
- **A. Prop and walk away** — Worker stands the phone on a table/shelf, walks to a marker, performs the movement. Needs long countdown (10–15s) or auto-start on full-body detection.
- **B. Partner-operated** — Worker recruits a coworker/family member to hold the phone. Short countdown is fine.
- **C. Both supported** — Worker picks per movement. Phone-mount instructions and partner instructions both shown.
- **D. Tripod / phone stand required** — Worker is told they need a stand. (Realistic? Probably not for at-home assessments.)

**Recommended default:** **A. Prop and walk away** as the primary model, with a short "no surface? recruit a partner" fallback note. A is the most reliable for the average employee on their own time. Build a long countdown (12–15s) and a "Are you fully in frame?" preview gate.

**Your answer:** **A. Prop and walk away** as the primary model, with a short "no surface? recruit a partner" fallback note. A is the most reliable for the average employee on their own time. Build a long countdown (12–15s) and a "Are you fully in frame?" preview gate.


---

## 5. Score visibility to employee

**Question:** Does the employee ever see their own scores or assessment results?

**Why it matters:** Drives whether you build an employee-facing results screen, a PDF report, an email summary, or none of the above. Has legal/cultural implications: showing raw automated scores can be misleading; not showing anything can feel dismissive.

**Options:**
- **A. Never** — Employee submits and that's it. All results stay with the provider.
- **B. After provider review only** — Provider-confirmed scores shown to employee in plain English.
- **C. Plain-English summary, no numbers** — "Your shoulder mobility looks good; we'd like to follow up on your trunk rotation." No 0–3 scores.
- **D. Full report including raw automated scores** — Everything visible.

**Recommended default:** **C. Plain-English summary, no numbers**, after provider review. Keeps you out of the "the app gave me a 1, am I getting fired?" trap. Sets the stage for Phase 5 corrective exercises (which need the worker to see *something* about their results).

**Your answer:** **C. Plain-English summary, no numbers**, after provider review. Keeps you out of the "the app gave me a 1, am I getting fired?" trap. Sets the stage for Phase 5 corrective exercises (which need the worker to see *something* about their results).


---

## 6. Retake-after-review pathway

**Question:** What happens when a provider reviews videos and one is unscoreable?

**Why it matters:** Without this, unusable submissions are just dead. With it, you need a "send back for retake" flow, employee notification, and partial-resume logic.

**Options:**
- **A. No retake** — Provider scores what's available or marks the assessment incomplete. Done.
- **B. Per-movement retake request** — Provider flags specific movements; employee gets notified and re-enters the flow for just those movements.
- **C. Full re-do only** — If anything is unscoreable, the whole assessment is restarted.

**Recommended default:** **B. Per-movement retake request.** Worth the modest extra build because self-captured video failure rate will be non-trivial. Reuses the same assessment record; existing `client_capture_id` idempotency means partial resume is mostly free.

**Your answer:** **B. Per-movement retake request.** Worth the modest extra build because self-captured video failure rate will be non-trivial. Reuses the same assessment record; existing `client_capture_id` idempotency means partial resume is mostly free.


---

## 7. Pain-stop handling

**Question:** When an employee skips a movement because of pain, what happens to the submission?

**Why it matters:** Pain during a self-administered movement screen has both a safety dimension (you want them to stop) and a clinical dimension (the report of pain itself is a finding worth documenting).

**Options:**
- **A. Skip and submit anyway** — Movement marked "skipped — pain"; assessment finalizes with that movement blank.
- **B. Skip and flag for outreach** — Same as A, plus the submission lands in a higher-priority provider queue and you get notified to follow up.
- **C. Skip ends assessment** — Pain on any movement halts the flow; nothing is submitted automatically.

**Recommended default:** **B. Skip and flag for outreach.** Pain is a finding. You probably want to call that worker before scoring the rest. Costs you one extra status field and a queue filter.

**Your answer:** **B. Skip and flag for outreach** — Same as A, plus the submission lands in a higher-priority provider queue and you get notified to follow up.


---

## 8. Demo asset strategy

**Question:** How do the looping movement demos get produced?

**Why it matters:** Longest lead-time item in the project. Five movements, each with a demo. Quality of demos directly affects quality of self-captured videos (if workers can't see what to do, they won't do it right).

**Options:**
- **A. Real-person video** — Hire/use a model, record on a clean background, edit into clean loops. Most relatable.
- **B. Animated silhouette / line-art** — Commission an animator or use mocap data. Most polished.
- **C. License stock** — Buy from a movement-screening or PT content library if one exists with these specific movements. Unknown if available.
- **D. Text + diagrams only for v1** — Ship without video demos initially; add later.

**Recommended default:** **A. Real-person video.** Production cost is moderate (one day of recording + editing), legal cost is one model release form, and workers copy real bodies more reliably than animations. Start scouting a model and a recording day in parallel with Phase 1 development.

**Your answer:** **A. Real-person video** — Hire/use a model, record on a clean background, edit into clean loops. Most relatable.


---

## Anything else you want to capture

Open notes, constraints I missed, things you've already decided that I didn't ask about: Not at this time.

