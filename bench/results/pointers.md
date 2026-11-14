# Benchmark: pointers

Generated 2026-11-14T09:37:18+00:00 by `python -m seehere.bench`. Evidence labels: OBSERVED = the system ran on this item; SIMULATED = computed under the stated assumption; UNAVAILABLE = not run (no numbers reported).

| System | Evidence | Descriptions | Visual recall | Fact recall | Over speech (s) | Paused (s) | Unsupported numbers | Note |
|---|---|---|---|---|---|---|---|---|
| microsoft-ai-audio-descriptions | UNAVAILABLE | – | – | – | – | – | – | not run: GenerateAD needs an Azure Foundry resource (Speech + GPT), which is chargeable and was not provisioned. See bench/microsoft/README.md. |
| seehere-greedy | OBSERVED | 1 | 20% | 14% | 0.00 | 0.00 | none | stored greedy schedule |
| seehere-cp-sat | OBSERVED | 1 | 20% | 29% | 0.00 | 0.00 | none | status optimal |
| seehere-extended | OBSERVED | 1 | 20% | 29% | 0.00 | 0.00 | none | built on cp_sat |
| seehere-reviewed | SIMULATED | 1 | 20% | 29% | 0.00 | 0.00 | none | no description was held for review, so an approving reviewer changes nothing |

Metric definitions: see `bench/README.md`. Unsupported numbers are a proxy for invented values, not a complete hallucination measure. One short synthetic item is a smoke test, not evidence of general quality.
