# What the DisburseProof judge feedback changes for SahiAaya

**Evidence supplied by participant:** scorecard marked September 23, 2026; DisburseProof received **17/30**. Category breakdown: AWS Usage **7/10**, Idea and Impact **5/8**, Execution **2/4**, Demo Video **1/4**, Design & Usability **2/4**. The only written comment shown is **"Loved the idea."**

This is one judge scorecard. The screenshot does **not** explain why the video or execution lost points. It also does not predict this event's scoring. The practical lesson is to create inspectable, simple proof of a working workflow—not to assume a weak video was the only issue.

## What we've changed

1. **First-screen clarity**: the user sees 2 units owed for a shortage + 2 owed under an offer, followed by a delivery of 2. They immediately understand the ambiguity.
2. **One primary guided CTA**: "Start the guided walkthrough", then each subsequent action is named (show evidence → review settlement → test conflict).
3. **Visible outcome**: the app shows units reviewed as settled **and** units still owed, not just a green "success" badge.
4. **Negative control**: identical quantities with contradictory supplier statements must produce a blocked settlement.
5. **Proof boundaries**: Vercel is a public browser simulation; local Docker must show a real Cypher-backed workflow. The video must show *both*, or focus on local live graph mode.

## Submission video script — target 2 minutes 40 seconds

**0:00–0:12 — The human need.** 
"In a kirana store, finding a shortage on the day of delivery is only half the problem. What if a supplier promises to make it right next week? Who remembers what was actually fulfilled?"

**0:12–0:29 — The exact case.**
"Two soap units were missing before. The supplier also owes two promotional units. Today, two extra units arrive. The invoice looks fine. But did they settle the shortage or the promotion? Counting the two units against both would be wrong."

**0:29–0:52 — The wrong default.**
"Without attribution, SahiAaya does not guess. It follows the previous invoices, entitlement and promises and asks the supplier a precise question. Nothing is marked as recovered or settled."

**0:52–1:17 — Connected evidence changes the answer.**
"Here is the supplier's evidence linking this receipt to the promotion. SahiAaya now proposes settling the promotional entitlement. The original shortage remains open. A supplier message alone still cannot close the case."

**1:17–1:40 — The verified action.**
"The retailer confirms the goods and approves the proposed allocation. The system records the evidence trail and exact quantity. We can see two units reviewed as settled and two still owed."

**1:40–2:05 — Why an agent cannot be just a chatbot.**
"Let's use exactly the same invoice and quantities with two conflicting supplier statements. A hallucinating system might give an answer. SahiAaya blocks settlement and asks which statement is authoritative."

**2:05–2:26 — Why this is a FalkorDB hackathon entry.**
"FalkorDB stores the connected receipts, suppliers, products, promises, source documents and allocations. These Cypher traversals bring the applicable evidence to the agent. The actual graph write enforces the safety conditions. We also compare against a fair SQLite baseline—it can make the same decisions, so we don't claim graph-only mathematics."

**2:26–2:40 — Honest scope.**
"This demo uses synthetic retail data. No supplier was contacted and no money was recovered. What works is the evidence-grounded investigation, clarification and retailer-reviewed resolution."

### Recording rules

- Record the **local Docker application with LIVE FALKORDB** clearly visible for the technical core, not merely the browser-only Vercel simulation.
- Record the first 15 seconds so a viewer with audio muted can identify: **who has the problem, what went wrong, and why SahiAaya helps**.
- Don't open source-code windows until after the customer problem, next action and result are shown.
- Use one case. Do not cycle through all six preset buttons. Show **one positive case and one negative control**.
- Put subtitles on-screen; avoid background music that obscures the key words.
- Show the latest successful **integration** test and actual Cypher graph query. Don't claim that a GitHub unit test alone proves end-to-end use.
- Make the outcome read "2 settled / 2 still owed". Never call that ₹ savings or a real recovery.
- Do a clean-browser/mobile rehearsal. If the link requires a Vercel login, fails to load or controls don't work, do not submit it as a public demo.

## Go/no-go gate

A viewer unfamiliar with SahiAaya must be able to answer all three within the first 30 seconds:

1. **Who** needs this? — The kirana retailer.
2. **What happens?** — A delivery could match more than one supplier promise.
3. **What does the product do?** — Finds the missing attribution and prevents an unsupported settlement.

If viewers cannot answer, shorten the explanation before adding features. This is the most actionable lesson from the DisburseProof scorecard.
