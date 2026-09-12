# Visitor Retention & Engagement Friction Playbook

This reference provides actionable engineering standards to maximize retention for traffic referred by AI search engines (ChatGPT Search, Claude, Perplexity).

## 1. Above-the-Fold Content Density
*   **The AI Referral Mindset:** Visitors arriving from conversational AI citations seek immediate confirmation of the answer or product cited.
*   **Best Practices:**
    *   Place primary `<h1>` and summary conclusions within the initial 500px viewport height.
    *   Avoid oversized, slow-loading hero carousels that push factual content below the fold.
    *   Ensure critical specifications (pricing, ingredients, compatibility) are rendered in HTML text rather than embedded within banner images.

---

## 2. Interstitial & Modal Timing
*   **The Penalty:** AI search engines track post-click dwell time and referral bounce rates. Immediate aggressive popups (newsletter signups, discount wheels, cookie walls covering 80%+ screen real estate) cause instant abandonment.
*   **Recommended Implementation:**
    *   Delay promotional interstitials until the visitor scrolls at least 50% of the page depth or demonstrates 45+ seconds of active engagement.
    *   Provide immediate, frictionless close buttons (`ESC` key listener, prominent `×` tap targets).

---

## 3. Deep-Link Navigation Architecture
*   **Path Routing vs Hash Routing:** Modern AI assistants cite direct deep links (`https://example.com/products/item-a`).
*   **The Flaw of Hash Routing:** SPA frameworks using hash fragments (`/#/products/item-a`) strip fragments during HTTP server requests, often resetting visitors to the generic homepage when direct-linked.
*   **Solution:** Migrate to clean HTML5 History API path routing (`BrowserRouter` with server-side URL rewrite fallbacks to `index.html`).

---

## 4. Email Retention & Inbox AI Summarizers (Appendix F)
*   **The Paradigm Shift:** Modern operating systems (Apple Intelligence Mail in iOS 18+, Gmail Gemini) summarize incoming confirmation and marketing emails automatically.
*   **Key Optimizations:**
    *   **First 100 Characters:** Front-load the exact confirmation status, order number, or core value proposition within the very first 3 lines of email text.
    *   **Multipart/Alternative:** Always emit a clean, well-formatted `text/plain` MIME part alongside `text/html`. AI summarizers frequently read the plain text version first.
    *   **Plain Text Links:** Ensure action links and confirmation URLs are explicit text anchors, not exclusively embedded inside image buttons.
