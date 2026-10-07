# The Self-Healing Pipeline: Companion Code

Code for **The Self-Healing Pipeline: How I Taught My CI/CD Pipeline to Fix Itself at 2 AM** by Dharmendra Ahuja.

## Layout

- `companion_code/` holds the reference implementations indexed in Appendix D of the book.
- `chapter-NN-.../` mirrors the book: one folder per chapter, with every code listing in reading order and a README mapping each file to its section.
- `.manuscript_changelog.md` tracks revisions, as described in Appendix I.

## Using the code

- Chapter files are excerpts that illustrate one idea. Where a Python file parses as complete code, its chapter README says so; the rest assume the surrounding pipeline (Lambda, Step Functions, Bedrock, Sentry).
- All account IDs, ARNs, tokens and endpoints are placeholders. Replace them before running anything.
- Review and test every example in a secure staging environment before using it in production.

## Chapters

| # | Chapter | Code files |
|---|---|---|
| 1 | [The Real Cost of Pipeline Failures](chapter-01-the-real-cost-of-pipeline-failures/) | 3 |
| 2 | [Beyond the Marketing Buzzword: A Working Definition](chapter-02-beyond-the-marketing-buzzword-a-working-definition/) | 4 |
| 3 | [Triage and the 3 AM Alarm: What Machine Learning Actually Does in DevOps](chapter-03-triage-and-the-3-am-alarm-what-machine/) | 14 |
| 4 | [The 47 Dashboards Nobody Looked At](chapter-04-the-47-dashboards-nobody-looked-at/) | 11 |
| 5 | [The Alert That Cried Wolf 200 Times](chapter-05-the-alert-that-cried-wolf-200-times/) | 9 |
| 6 | [Detecting the Slow-Motion Outage](chapter-06-detecting-the-slow-motion-outage/) | 8 |
| 7 | [Remediation: When to Pull the Plug Automatically](chapter-07-remediation-when-to-pull-the-plug-automatically/) | 14 |
| 8 | [What Happens When You Give an AI Write Access](chapter-08-what-happens-when-you-give-an-ai-write/) | 8 |
| 9 | [The Trust Problem: Junior Swagger vs. Senior Scars](chapter-09-the-trust-problem-junior-swagger-vs-senior-scars/) | 7 |
| 10 | [So I Killed a Pod: Validating the Healer with Chaos](chapter-10-so-i-killed-a-pod-validating-the-healer/) | 4 |
| 11 | [The New Attack Surface: Security Risks of Autonomous Pipelines](chapter-11-the-new-attack-surface-security-risks-of-autonomous/) | 13 |
| 12 | [Why Visibility Looks Like Failure](chapter-12-why-visibility-looks-like-failure/) | 3 |
| 13 | [The State of Autonomous Pipelines: An Honest Assessment](chapter-13-the-state-of-autonomous-pipelines-an-honest-assessment/) | 7 |
| 14 | [One Team Is Easy. Two Hundred Services Is Not.](chapter-14-one-team-is-easy-two-hundred-services-is/) | 2 |
| 15 | [The ROI of Self-Healing: The Economics of Firefighting](chapter-15-the-roi-of-self-healing-the-economics-of/) | — |
| 16 | [Four Incidents the Pipeline Changed](chapter-16-four-incidents-the-pipeline-changed/) | — |
| 17 | [Start Local, Stay Local Until You Can’t](chapter-17-start-local-stay-local-until-you-cant/) | 9 |
| 18 | [Where Autonomy Fails: The True Limitations](chapter-18-where-autonomy-fails-the-true-limitations/) | — |
| 19 | [Appendices](chapter-19-appendices/) | — |

## License and errata

Code is licensed under the Apache License 2.0 (see [LICENSE](LICENSE)). It is provided for illustrative and reference purposes only. Corrections and issues: use this repository's issue tracker. The book text is not part of this repository.
