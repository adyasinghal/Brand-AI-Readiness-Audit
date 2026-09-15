# Adobe University Hackathon
**Date:** 03/09/26

## Live Session Details
* **HR Lead:** Anandi B.
* **Engineering Team (Problem Statements):**
  * Samarth Arya
  * Nikaash Puri
  * Satya Deep Maheshwari

---

**Core Objective: Map brand visibility expertise to a reusable AI agent.**

* **Reference:** agentskills.io
* **Workflow:** Go through website -> do an audit (problems, areas of improvement) -> suggest additions (additional features & fixes)

---

## Tips & Important Points
* **Generalization:** It should work well across different industry vertical websites. There are certain common denominators (how well you implement common denominators is also a key differentiator).
* Don't tailor your solution to specific websites.
* **Avoid Overfitting:** Take care of overfitting.
* Avoid over-reliance on a single API/server which might go down.
* **Prioritization (Imp):** Assigning the right priority to problems/suggestions your agent generates will create differentiation (Most impactful = priority/severity).
* **Originality:** AI tends to add bloatware (things which aren't needed, take care of that).
* **SEO Hygiene & Ethics:** 
  * Follow typical SEO hygiene: check `robots.txt`, respect meta tags, etc.
  * Don't bombard the site with requests.
* **Submission Structure:** Structure your submission (`.md` files) in a way that is optimized for reading/processing by the agent.

---

## Technical Aspects
* **File Size:** File should be below 50MB.
* **Sandbox Environment:** Python, Node.js (better the more you stick to Python).
* **Dependencies:** Don't go for fancy packages; the lightweight the better. (As long as tools are part of standard Python packages, it's fine).
* **Execution Limit:** 5 minutes runtime:
  * Includes everything within your skill to generate the report.
  * External bottlenecks will be taken care of by the evaluation harness.
* **Interface:** Frontend is not needed (CLI report is fine).
* **Data Fetching:** Try to stick to standard fetch (bash & curl commands).
* **Hardware Requirements:** Agent should work on a standard system. Solution should not require extensive hardware/GPUs.
* **Submission Format:** Submit via Skills marketplace (packaging structure).
* **Scripts:** Including scripts is not mandatory, but if you feel including them improves the solution, do so.

---

## Evaluation & Judging
* **Agent Integration:** Your agent will be attached to an evaluation AI agent which already has plugins built in.
* **Bot Access:** Test sites will be configured to explicitly allow bots.
* **Relative Scoring:** Every submission gets the exact same set of sites & questions (Evaluation is relative across participants).
* **Network Access:** Environment where solution is evaluated will have active web access.
  * Note: Keep in mind that your agent shouldn't rely on third-party external tools/hosted servers. It must be self-contained and legitimate.
* **Brand Search Scope:** You can reach out to public community platforms like Reddit, Quora, etc., to check brand visibility.
