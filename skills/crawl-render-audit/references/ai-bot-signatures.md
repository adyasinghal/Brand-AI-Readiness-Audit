# AI Search Crawler & Retrieval Bot Signatures

This reference documents the primary AI search crawler user-agents tracked by `check_access.py` to evaluate domain access and Generative Engine Optimization (GEO) discoverability.

## Monitored AI Bot User-Agents

| User-Agent | Operator | Primary Function | Retrieval Impact if Blocked |
|---|---|---|---|
| `GPTBot` | OpenAI | Web crawler for OpenAI LLM training and data indexing | Complete exclusion from future OpenAI foundation training sets. |
| `ChatGPT-User` | OpenAI | Direct user-initiated web browsing in ChatGPT Search | Live search answers cannot fetch or cite the page in real time. |
| `ClaudeBot` | Anthropic | Web crawler for Anthropic AI systems and Claude | Complete exclusion from Claude foundation models and retrieval. |
| `anthropic-ai` | Anthropic | Anthropic data collection crawler | Secondary exclusion from Anthropic training corpora. |
| `PerplexityBot` | Perplexity | Real-time indexing for Perplexity AI conversational answers | Pages cannot be indexed or cited in Perplexity search results. |
| `Google-Extended` | Google | Token collector for Gemini and Vertex AI training | Controls whether Google foundation models train on domain content. |
| `Applebot-Extended` | Apple | Web indexing for Apple Intelligence & Siri | Pages excluded from Apple Intelligence generative summaries. |
| `Amazonbot` | Amazon | Web crawler for Alexa and Bedrock foundation models | Excluded from Amazon Q and Alexa conversational search. |
| `Bytespider` | ByteDance | Indexing for TikTok and ByteDance LLM systems | Excluded from ByteDance generative search answers. |
| `CCBot` | Common Crawl | Open web scrape corpus used by almost all open-weights LLMs | Excluded from future open-weights model pre-training datasets. |
| `cohere-ai` | Cohere | Web crawler for Cohere enterprise models | Excluded from Cohere RAG and search pipelines. |
| `Meta-ExternalAgent` | Meta | Web search crawler for Meta AI (Llama, WhatsApp, IG) | Excluded from real-time citation in Meta AI assistants. |

## Recommended `robots.txt` Configuration for AI Visibility

To maximize brand presence across AI conversational engines without opening unrestricted scraping to malicious bots:

```text
User-agent: GPTBot
Allow: /

User-agent: ChatGPT-User
Allow: /

User-agent: ClaudeBot
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: Applebot-Extended
Allow: /

User-agent: Google-Extended
Allow: /

Sitemap: https://example.com/sitemap.xml
```
