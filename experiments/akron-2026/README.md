# Akron 2026 transfer experiment

This experiment tests whether Proofline's evidence architecture transfers to a second municipal public-record corpus with a different publisher stack.

Source: Akron City Council's official **OnBase Agenda Online** portal.

## T1 — source-contract probe

Before adding production discovery code, the probe records how the publisher actually exposes:

- meeting index/search pages;
- individual meeting pages;
- agenda download anchors;
- stable meeting/document identifiers;
- PDF transport behavior;
- substantive server-rendered agenda text, if present;
- forms/links needed for bounded discovery.

The probe is read-only and bounded to a small set of publisher-linked 2026 meeting pages already visible through the official portal/search surface. It does not sweep or guess numeric meeting IDs.

## Promotion rule

An OnBase production adapter will be added only if the publisher exposes a reproducible official chain from an index/search page to stable meeting/document identities.

Transient session/cookie/transport state must not become source identity.

## Transfer questions

If acquisition is promotable, subsequent stages will measure separately:

1. Bronze/source acquisition reuse;
2. Silver extraction quality;
3. segmentation portability;
4. retrieval benchmark portability;
5. matter-key policy portability;
6. financial-role policy portability;
7. detector behavior, including valid zero-result outcomes.

Canton-specific segmentation, matter-key, and financial-role rules are not presumed to apply to Akron.
