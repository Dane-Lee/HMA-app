# Self-Guided Assessment — Consent Text Draft

> **This is a developer-drafted starting point, not legal text.** Send to counsel for review and rewriting before the consent screen ships in Phase 2. The goal of this draft is to give legal a concrete artifact to react to, rather than an open-ended ask.

## Context for legal counsel

ATI Worksite Solutions currently delivers the Human Movement Assessment (HMA) in person at the worksite, with the provider physically present and clinically supervising. The five-movement HMA evaluates basic mobility (forward lunge, single leg dip, shoulder reach behind back, trunk rotation, cervical rotation) and produces a 0–3 score per movement plus an overall band.

We are building a **self-administered** version where the employer (initially Hendrickson) distributes a one-time link to each employee. The employee opens the link on their phone at home or during off-hours, records the five movements at their own pace, and submits the videos for provider review.

The existing in-clinic flow already has a consent scope with four flags:

- `voluntary_wellness` — participation is voluntary
- `purpose_limited` — data is used only for the wellness purpose stated
- `no_employment_decision` — results will not drive hiring, firing, promotion, or discipline
- `video_retention_acknowledged` — the employee acknowledges short-term video retention for provider review

For the self-administered flow we propose adding a fifth flag:

- `employer_distribution_acknowledged` — the employee understands that even though their employer sent the link, participation is their own choice and declining has no consequences

The privacy posture string stored in the database (`voluntary_ergonomic_wellness`) may need to be relabeled for the self-administered path; legal to advise.

## Open questions for legal counsel

1. **HIPAA scope.** Does the self-administered + employer-distributed model create a provider-patient relationship that brings the data under HIPAA, or does it remain in the workplace-wellness category? Today the in-clinic flow is treated as voluntary wellness. The self-administered context — employer distribution, video collection, scoring by a clinician — may or may not change that.
2. **ADA / EEOC.** The ADA restricts employer-required medical examinations. We need clear language and structural protections to demonstrate this is a voluntary wellness screen and not a fitness-for-duty exam. Suggested protections built into the app already: no employment decision flag, results never shared with the employer, employee can decline without follow-up. Anything else?
3. **State-specific issues.** Is there state-by-state variation we need to handle (biometric data laws in IL, TX, etc.; mandatory wellness-program disclosures in CA; etc.)?
4. **Minors.** Hendrickson's workforce is presumably 18+. Should we add an age attestation anyway?
5. **Union workforces.** If a future client has a unionized workforce, do collective-bargaining notice requirements apply? Worth flagging now even if not immediately relevant.
6. **Video retention.** Today the app stores videos for a configurable retention window (default 365 days for the assessment record; review videos auto-purge after 7 days). Are those durations defensible? Should we offer the employee a right-to-delete button?
7. **Subpoena / litigation hold.** Should the consent text mention that data could theoretically be subpoenaed? Or is that overreach for a wellness screen?
8. **Withdrawal of consent after submission.** If an employee withdraws consent after submitting, what's our obligation — delete everything, or delete videos but retain anonymized aggregate?
9. **Provider identity disclosure.** Should the consent name the specific provider (or provider organization) who will review the videos, or is "your ATI provider" sufficient?

## Proposed consent screen — plain-English draft

The text below is what the employee would read before recording. The numbered items at the end are the explicit acknowledgments tied to the five scope flags.

---

### Before you begin

You're about to complete a short movement screen called the Human Movement Assessment (HMA). Your employer has invited you to participate, but **this is your choice**. You can stop at any time, and you can decline without consequences.

### What this is

The HMA is a five-movement check that looks at basic mobility — your lunge, single-leg balance, shoulder reach, trunk rotation, and neck rotation. It is used by ATI Worksite Solutions to identify ergonomic and mobility opportunities that could be addressed with exercise, coaching, or workplace adjustments.

This is **not** a fitness-for-duty exam, a return-to-work clearance, or a medical diagnosis. It is a wellness screen.

### What we'll collect

For each of the five movements, you'll record a short video on your phone (typically 10–20 seconds per side). When you submit, the videos and your movement scores are sent to your ATI provider for review.

### How the data is used

- **Your provider reviews the videos and confirms your scores.** If something needs follow-up, your provider will reach out to you directly.
- **Your videos and scores are not shared with your employer.** Your employer is not given access to your individual results.
- **The data is used only for this wellness screen.** It will not be used to make decisions about your job, your pay, your assignment, your discipline, or your continued employment.

### How long we keep the data

- **Movement videos** are kept for up to 7 days while your provider completes the review, then automatically deleted.
- **Your movement scores and provider notes** are kept for up to one year so your provider can track changes over time.
- **You can ask us to delete your data** at any time. Contact your ATI provider to make that request.

### What happens if you stop

If a movement causes pain, stop. If you want to quit before finishing, just close the page. Nothing partial is submitted to your provider unless you complete a movement and reach the "Submit" screen.

### Before you continue, please confirm

To start the assessment, please confirm each of the following. Each checkbox is required.

1. **I'm choosing to do this.** I understand that participating in this assessment is voluntary, and I can stop at any time. _(scope flag: `voluntary_wellness`)_
2. **I know the link came from my employer, and I'm still choosing to do this.** My employer sent me this link, but my participation is my own decision. I understand that declining will not affect my job, my pay, my assignment, or any other condition of my employment. _(scope flag: `employer_distribution_acknowledged`)_
3. **I understand how my data will be used.** The videos and scores I submit will be used by my ATI provider for this wellness screen only. They will not be used for any other purpose. _(scope flag: `purpose_limited`)_
4. **I understand this will not be used for employment decisions.** My results will not be shared with my employer to make decisions about hiring, firing, promotion, discipline, or job assignment. _(scope flag: `no_employment_decision`)_
5. **I understand my videos are kept short-term.** I understand that my movement videos will be retained for up to 7 days for provider review and then automatically deleted, and that my scores and provider notes may be retained for up to one year. _(scope flag: `video_retention_acknowledged`)_

[ Continue ]    [ I don't want to participate ]

---

## Auxiliary copy

### "I don't want to participate" confirmation

If the employee clicks the decline button:

> Thanks for letting us know. No data has been collected. You can close this page.
>
> If you change your mind later, your assessment link is still valid for the next 7 days, or you can request a new link from your provider.

### Pain-stop confirmation (shown when an employee skips a movement because of pain)

> Got it. We'll let your provider know you stopped this movement because of pain. They'll reach out to follow up.
>
> You can continue with the rest of the assessment or stop here — both are fine.

### Submission success

> Your assessment has been submitted to your ATI provider for review.
>
> Your provider will contact you if they want to follow up. You won't see scores in this app until your provider has reviewed them.

### Retake request notification (when provider asks for a retake)

> Your provider has asked you to redo {movement name}. The recording wasn't clear enough to score, and they'd like another try.
>
> When you're ready, open your assessment link again to record just that movement. You don't have to redo anything else.

---

## Notes on what changed vs. in-clinic consent

| Item | In-clinic flow today | Self-administered flow |
|---|---|---|
| Privacy posture string | `voluntary_ergonomic_wellness` | TBD by legal — possibly `voluntary_ergonomic_wellness_self` or unchanged |
| Scope flag count | 4 | 5 (added `employer_distribution_acknowledged`) |
| Distribution model | Provider present at worksite | Employer-distributed link, employee at home |
| Provider in room? | Yes | No |
| Pain-stop logging | Implicit (clinician observes) | Explicit flag on the assessment |
| Right to delete | Verbal request to provider | Same — surface in the consent text |

## Implementation notes (for the dev side, not legal)

When Phase 2 ships, the changes needed in the existing code are:

- Add `employer_distribution_acknowledged: Literal[True]` to `ConsentRequest` in [api/app/schemas.py](../../api/app/schemas.py).
- Add the same flag to the `consent_scope` dict in [api/app/routes/assessments.py](../../api/app/routes/assessments.py).
- Update [api/app/repository.py](../../api/app/repository.py) `PRIVACY_POSTURE` constant if legal recommends a new string.
- Update the in-app consent screen text per whatever legal returns.
- Bump `notice_version` to a new string (e.g., `"privacy-notice-self-v1"`) so historical consents remain auditable under their original version.

These changes are purely additive — the in-clinic flow continues to use the existing four-flag consent unchanged.
