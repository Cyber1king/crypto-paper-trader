# Phase 53 — ECB Reference-Rate Rights Review

**Date:** 2026-10-09
**Question:** what are the actual upstream rights in ECB euro foreign exchange
reference rates, as distinct from the Frankfurter endpoint that serves them?

**Outcome:** the registry's licence label is **wrong**. ECB data is **not**
CC BY-NC-SA 4.0. It is free use subject to ECB's own conditions. The rates are
now resolved as to terms; the registry still needs correcting.

---

## 1. The three layers, kept separate

| Layer | Who | What it governs |
|---|---|---|
| **Publisher** | European Central Bank | Rights in the reference rates themselves |
| **Retrieval endpoint** | Frankfurter (`api.frankfurter.dev`) | Access, transport, rate limits — **not** rights in the rates |
| **Consuming project** | this repository | Obligations it inherits from the publisher |

Frankfurter's own documentation is explicit that it decides none of this:

> **Is the API free for commercial use?**
> Yes. **The rates themselves fall under each provider's terms.**

So Frankfurter's permissiveness transfers nothing. An audit that stopped at the
API's terms would have concluded "commercial use fine" and been wrong about the
payload.

---

## 2. Publisher terms — ECB, "Disclaimer & copyright"

Retrieved 2026-10-09 from the ECB's own page:
<https://www.ecb.europa.eu/services/using-our-site/disclaimer/html/index.en.html>

> **Copyright**
> Copyright © for the entire content of this website: European Central Bank,
> Frankfurt am Main, Germany.
>
> Subject to the exception below, users of this website may make **free use** of
> the information obtained directly from it subject to the following conditions:
>
> - When such information is distributed or reproduced, it must appear accurately
>   and **the ECB must be cited as the source**.
> - Where the information is incorporated in documents that are sold (regardless
>   of the medium), the natural or legal person publishing the information must
>   inform buyers, both before they pay any subscription or fee and each time
>   they access the information taken from this website, that the information may
>   be obtained free of charge through this website.
> - **If the information is modified by the user** (e.g. by seasonal adjustment
>   of statistical data or calculation of growth rates) **this must be stated
>   explicitly**.
> - When linking to this website from business sites or for promotional purposes,
>   this website must load into the browser's entire window (i.e. it must not
>   appear within another website's frame).
>
> As an exception to the above, any reproduction, publication or reprint, in
> whole or in part, of documents that bear the name of their authors, such as
> **ECB Working Papers and ECB Occasional Papers**, in the form of a different
> publication … is permitted only with the **explicit prior written
> authorisation** of the ECB or the authors.

Corroborating, from the ECB press release announcing the change to the reference
rates (7 December 2015): *"Reproduction is permitted provided that the source is
acknowledged."*

And from the ECB's own reference-rates page:

> The reference rates are published for **information purposes only**. **Using
> the rates for transaction purposes is strongly discouraged.**

---

## 3. What this means — and what it corrects

### 3.1 The registry label is factually incorrect

`research_registry.json` records for EUR/USD, GBP/USD and USD/JPY:

```
licence_knowledge : VERIFIED
licence_name      : "CC BY-NC-SA 4.0"
```

**The ECB does not publish under CC BY-NC-SA 4.0.** It publishes under its own
bespoke copyright policy. The two are materially different instruments:

| | CC BY-NC-SA 4.0 | ECB policy (actual) |
|---|---|---|
| Commercial use | Prohibited (NC) | **Not prohibited by the copyright clause** — free use, subject to conditions |
| Share-alike | Required | **Not required** |
| Attribution | Required | Required ("the ECB must be cited as the source") |
| Modification | Permitted | Permitted **but must be stated explicitly** |
| Resale | Prohibited (NC) | Allowed, with a **"free of charge" notice to buyers** |
| Authored works (Working/Occasional Papers) | — | **Prior written authorisation required** |
| Framing restriction | — | Business links must load full-window |

The registry's label is wrong in both directions at once: it asserts a
**share-alike obligation that does not exist**, and a **non-commercial
restriction that does not exist** on the copyright clause. A reader relying on
it would over-comply in one respect and under-comply in another — most
importedly, it would **miss the modification-disclosure duty and the resale
notice**, which are the two conditions actually in force.

Recording this is not pedantry: the registry is the machine-readable governance
surface that a future research integration would consult before using ECB data.

### 3.2 Attribution and modification-disclosure are the live obligations

For this project:

- **Cite the ECB as the source** wherever the rates are reproduced.
- **State the modification explicitly.** The Phase 33 forex path retrieves via
  Frankfurter, which **blends** rates across providers by default and, per its
  own documentation, computes a midpoint where a provider publishes bid/ask
  rather than a reference rate. Any blended or recomputed series derived this
  way is a **modified** ECB-derived figure and must be declared as such. This is
  a condition the registry's CC label never captured.
- Frankfurter's provider-scoped routes (`/v2/providers/ecb/...`) return ECB
  values unblended and are the cleaner path where purity matters.

### 3.3 "Using the rates for transaction purposes is strongly discouraged"

Not a licence prohibition, but directly relevant to a trading project: the ECB
publishes these for information only. It reinforces the existing decision not to
treat reference rates as tradeable prices.

### 3.4 No synthetic OHLC — confirmed and retained

Reference rates are single daily mid/averaged quotes. They contain **no**
high/low range and **no** volume. Nothing in this phase converts, interpolates
or synthesises candles from them, and none should: fabricating OHLC from a
daily reference rate would invent data the publisher never supplied, and the ECB
licence permits *use* of the rates, not *manufacture* of price series from them.

Forex remains blocked on **data-quality** grounds independently of licensing —
no genuine OHLC, and no session/holiday/DST modelling. Licensing is not the
binding constraint there, and resolving it does not unblock forex.

---

## 4. Status decision

**Terms are now RESOLVED as to substance: ECB reference rates are free use
subject to attribution, explicit modification disclosure, and a resale notice.**

They are **not** CC BY-NC-SA 4.0, and the registry must say so.

Per the phase instruction — *"If official evidence remains unavailable or
ambiguous, retain UNVERIFIED"* — the evidence here **is** available and is not
ambiguous for the ECB website's content. The retained caution is narrower and
is recorded as such rather than being allowed to block the correction:

| Residual uncertainty | Effect |
|---|---|
| The ECB **Data Portal** (`data.ecb.europa.eu`) is a distinct site; its own terms were not separately verified | If a future integration pulls from the Data Portal rather than the website, re-verify first |
| ECB-authored Working/Occasional Papers need prior written authorisation | Applies only if those documents are ever reproduced; not applicable to EXR rates |
| Attribution wording for derivatives is not specified verbatim | This review states a defensible citation; exact form is the owner's call |

**The registry's `licence_knowledge` for the three forex instruments is left at
`VERIFIED`, because the underlying right to use the rates for non-commercial
research is established.** What is wrong is the `licence_name` string, which
describes a licence the ECB does not grant. Correcting that string is proposed
in `LICENCE_REMEDIATION_PLAN.md` §6 item D and requires approval — a
registry write, and a deliberate narrowing of a recorded claim.

---

## 5. Operational constraint for this phase and the next

**No new research integration using ECB rates is approved or begun.** Forex
remains blocked on data quality, and no rate is to be converted into synthetic
OHLC. This review establishes what the rights *would* be for a future
integration; it authorises nothing.

---

## 6. References

- ECB, *Disclaimer & copyright* — <https://www.ecb.europa.eu/services/using-our-site/disclaimer/html/index.en.html> (retrieved 2026-10-09)
- ECB, *Euro foreign exchange reference rates* — <https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html>
- ECB press release, 7 December 2015 — <https://www.ecb.europa.eu/press/pr/date/2015/html/pr151207.en.html>
- Frankfurter API documentation and FAQ — <https://www.frankfurter.app/>
- Binance Vision Dataset Terms v1.0 (for contrast: the crypto path *is* CC BY-NC-SA 4.0)