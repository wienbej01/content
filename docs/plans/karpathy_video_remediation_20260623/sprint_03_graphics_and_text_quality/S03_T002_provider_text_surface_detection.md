# S03_T002 Provider Text Surface Detection

## Purpose

Detect screens/documents/readable text risk in provider-generated b-roll.

## Failure classes addressed

```text
F-TEXT-001
```

## Allowed files

```text
scripts/media_service.py
scripts/media_contract.py
scripts/evals/**
tests/**
```

## Required behavior

If `text_policy=NO_VISIBLE_TEXT`, eval must attempt text/screen-surface detection. OCR may be optional but missing OCR cannot become fake green in strict mode.

## Pass gates

PASS if a b-roll clip with obvious screen/text risk is flagged or marked inconclusive requiring human review.
