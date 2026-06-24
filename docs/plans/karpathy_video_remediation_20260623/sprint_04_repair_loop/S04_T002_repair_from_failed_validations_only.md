# S04_T002 Repair from Failed Validations Only

## Purpose

Repair must be driven by validations/evidence, not vague user complaints or filenames.

## Required behavior

```text
- repair stage reads failed validations
- creates change_requests with failure_class and evidence links
- refuses repair when evidence is missing
```

## Pass gates

PASS if a synthetic failed validation creates the correct change_request and no evidence creates BLOCKED.
