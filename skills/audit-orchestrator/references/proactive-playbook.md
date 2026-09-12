# Proactive Recommendations Playbook

This reference catalogs forward-looking, high-value AI readiness recommendations that position a brand ahead of baseline compliance for Generative Engine Optimization (GEO) and autonomous agent discovery.

## 1. Machine Manifest (`/llms.txt`)
*   **Standard:** [llmstxt.org](https://llmstxt.org/)
*   **Rationale:** Modern AI assistants (ChatGPT, Claude, Perplexity) prioritize clean, low-token Markdown manifest files located at `/llms.txt` to discover authoritative documentation, pricing tables, and core product summaries without executing expensive HTML scraping.
*   **Actionable Template:**
    ```markdown
    # Brand Name
    > Concise 1-sentence value proposition.

    ## Authoritative Documentation & Catalogs
    - [Products](https://example.com/products): Complete product specifications.
    - [Pricing](https://example.com/pricing): Transparent tier pricing and seat costs.
    - [API Reference](https://example.com/docs/api): Machine-readable endpoints.
    ```

## 2. Navigational Hierarchy (`BreadcrumbList` Schema)
*   **Standard:** [schema.org/BreadcrumbList](https://schema.org/BreadcrumbList)
*   **Rationale:** LLM search crawlers reconstruct site taxonomy and category depth using structured breadcrumbs, preventing topic ambiguity in direct answers.
*   **Actionable Template:**
    ```json
    {
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      "itemListElement": [
        { "@type": "ListItem", "position": 1, "name": "Home", "item": "https://example.com" },
        { "@type": "ListItem", "position": 2, "name": "Catalog", "item": "https://example.com/catalog" }
      ]
    }
    ```

## 3. Gated Vertical Schema Enrichment
*   **Trigger:** On-page signals indicate specific commerce, local business, or article content.
*   **Recommendations:**
    *   **E-Commerce:** Structure offerings with `schema.org/Product` including `offers`, `priceCurrency`, and `availability`.
    *   **Local Services:** Deploy `schema.org/LocalBusiness` with `geoCoordinates`, `openingHoursSpecification`, and `telephone`.
    *   **Editorial/Technical:** Add `schema.org/Article` or `TechArticle` with `author`, `publisher`, and `datePublished`.

## 4. AI Inbox Digest Optimization (Appendix F)
*   **Standard:** Apple Intelligence Mail Categorization & Gmail Gemini Summarization
*   **Rationale:** When referred visitors subscribe to brand newsletters or updates, client-side AI models summarize confirmation emails. Cluttered promotional banners degrade digest clarity.
*   **Best Practices:**
    *   Ensure the first 100 characters of email communications contain unambiguous confirmation copy.
    *   Place primary action links above header image assets.
    *   Support one-click unsubscribe headers (`List-Unsubscribe`) to maintain sender reputation across AI filters.
