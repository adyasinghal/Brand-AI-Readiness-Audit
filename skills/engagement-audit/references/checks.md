# On-site engagement checks (EN-01 to EN-16)

Framing: most AI-referred and search visitors land mid-site with zero context. The audit asks four questions in order: can they orient, can they scan, can they act, can they continue.

## Orientation (EN-01 to EN-04)

- EN-01 (high) no viewport meta. Mechanism: phones render the desktop layout zoomed out; the majority-mobile first visit is unreadable and bounces instantly. Cheapest high-impact fix on the list.
- EN-02 (medium) homepage has no H1. Mechanism: no one-line answer to "what is this site", for humans or extractors.
- EN-03 (low) more than 3 H1s on the homepage. Mechanism: competing headlines dilute the one-line answer.
- EN-04 (medium) no <nav> landmark on any sampled page. Mechanism: mid-site landers have no persistent way to orient or move laterally.

## Scannability (EN-05, EN-06)

- EN-05 (medium) wall of text: over 40% of a page's paragraphs exceed 600 characters and the page carries 2000+ characters of paragraph text. Mechanism: visitors skim; unbroken prose gets abandoned, and facts buried mid-paragraph extract poorly. Thresholds chosen so ordinary article prose (mixed paragraph lengths) never fires.
- EN-06 (medium) 800+ words with zero H2/H3 subheadings. Mechanism: no jump targets for readers, no anchors or section signals for machines. Question-style subheadings double as the exact strings assistants match against user questions.

## Action paths (EN-07, EN-08)

- EN-07 (medium) no verb-led call to action on the homepage (matched against a fixed list: get started, contact, buy, book, sign up, demo, quote, etc.). Mechanism: convinced visitors with no obvious next step take none.
- EN-08 (high) no contact channel anywhere in the sample: no email, phone, mailto:, tel:, or contact link. Mechanism: intent cannot convert, and unreachability also reads as an entity-trust problem to machines.

## Help and continuity (EN-09 to EN-13)

- EN-09 (medium) no FAQ or self-serve help signal (link, "frequently asked" text, or FAQPage markup). Mechanism: repeat questions burn support on-site; off-site, Q&A-shaped content is what assistants most readily lift into answers, so its absence costs both halves of the problem.
- EN-10 (low) no search input on a 5+ page sample. Mechanism: on larger sites, visitors who cannot find leave rather than browse.
- EN-11 (medium) dead-end pages: any non-homepage sample page with fewer than 3 internal links. Mechanism: AI-referred visitors land exactly on such pages; no path onward means one page view and gone. Crawlers likewise read weak internal linking as unimportance.
- EN-12 (medium) duplicate titles across distinct pages. Mechanism: indistinguishable in search results, citations, and tabs; users cannot pick the right page.
- EN-13 (low) 2+ sampled pages sit 2+ path levels deep with no breadcrumb navigation or BreadcrumbList markup. Mechanism: mid-site landers cannot see where they are in the structure.

## Cross-linking depth (EN-14, EN-15)

- EN-14 (medium) hub-and-spoke linking. On samples of 4+ pages, fires when at least 2 interior pages, and at least half of them, receive zero links from any other interior page (every path to them runs through the homepage). Resolution is by normalized path, so relative and absolute internal links both count. Mechanism: a visitor reading one product or article is never guided to a related one, so sessions end after a single page; crawlers likewise read the lateral link graph as a relevance signal.
- EN-15 (low) generic anchor text. Fires when the sample contains 10+ internal text anchors and over 30% of them are generic (click here, here, read more, learn more, more, link, this, details, view). Mechanism: anchors are how visitors choose where to go next and how machines infer what the target page is about; generic ones convey nothing to either.

## Interactivity (EN-16)

- EN-16 (medium) purely static text. Fires when a sample of 3+ pages totalling 1500+ words contains zero forms, inputs, buttons, media embeds (video/audio/canvas/iframe), and details widgets. Mechanism: static walls of text give visitors nothing to do; dwell time and return visits track what a page lets people do, not just read. The suggested action deliberately proposes content-appropriate interactivity (contact form, calculator, product filter, expandable FAQ, demo video) rather than interactivity for its own sake.
