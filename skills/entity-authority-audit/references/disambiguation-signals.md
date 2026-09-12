# Brand Entity Disambiguation & Authority Signals

This reference establishes the authoritative criteria and registers used to evaluate brand trust and entity disambiguation for Generative Engine Optimization (GEO).

## 1. Primary Knowledge Graph Disambiguation (`sameAs`)

Large Language Models build entity representations by clustering claims around canonical knowledge graph nodes (Wikidata QIDs, Wikipedia articles, verified enterprise registries).

### Recommended High-Authority `sameAs` Registries:

| Registry | Domain Pattern | Purpose |
|---|---|---|
| **Wikidata** | `https://www.wikidata.org/wiki/Q...` | Definitive global open knowledge base node used by Google Knowledge Graph, Claude, ChatGPT. |
| **Wikipedia** | `https://en.wikipedia.org/wiki/...` | Primary descriptive corpus for LLM pre-training and entity extraction. |
| **LinkedIn** | `https://www.linkedin.com/company/...` | Verified corporate identity, operational jurisdiction, and headcount. |
| **Crunchbase** | `https://www.crunchbase.com/organization/...` | Venture financing, corporate leadership, and investment status. |
| **Official Registers** | `https://find-and-update.company-information.service.gov.uk/...`, SEC EDGAR | Government entity registrations validating legal standing. |

---

## 2. On-Page Brand Name Harmony

To avoid contradictory entity classifications in AI answer generation:
- **`<title>` Tag:** Must begin or conclude with the exact canonical brand name.
- **`<h1>` Document Heading:** Located in the body slice (top 128KB), must share significant tokens with the `<title>`.
- **`<meta property="og:title">`:** Must harmoniously reflect the primary entity without completely divergent marketing slogans.

---

## 3. Qualitative About-Page Standard (The 2-Sentence Test)

The introductory summary of a brand's About page must explicitly answer:
1. **Who is the entity:** Company name and structure.
2. **What does it provide:** Core products, technology, or services.
3. **Target market/category:** Target customer segment or industry classification.

If the description relies exclusively on abstract marketing jargon (e.g., *"We pioneer tomorrow's synergy"* without stating products), conversational assistants fail to categorize the brand properly.
