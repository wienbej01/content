## 13. Global Regression Suite

After each sprint from Sprint 5 onward, run:

```bash
pytest tests/unit/test_media_contract.py -q
pytest tests/unit/test_provider_boundary.py -q
pytest tests/unit/test_paid_adapters_contract.py -q
pytest tests/unit/test_compile_media_prompt_split.py -q
pytest tests/unit/test_local_graphics_db.py -q
pytest tests/unit/test_media_qa_contract.py -q
pytest tests/unit/test_hero_lipsync_qa.py -q
pytest tests/unit/test_repair_classifier.py -q
pytest tests/unit/test_assembly_preflight.py -q
pytest tests/unit/test_assembly_timeline_heuristics.py -q
pytest tests/unit/test_final_qa_contract.py -q
pytest tests/regression -q
```

Before merge, run:

```bash
pytest tests/unit tests/integration tests/regression -q
```

If the full suite is too slow, Auditor must approve a documented subset, but the regression tests for the failed production are mandatory.

---
