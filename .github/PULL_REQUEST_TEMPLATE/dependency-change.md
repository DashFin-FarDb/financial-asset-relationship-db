## Dependency change summary

<!-- State the single primary dependency decision in this PR. -->

## Source of truth

- [ ] This PR treats `requirements.txt` as the authoritative runtime dependency file.
- [ ] I updated `pyproject.toml` to mirror the intended runtime policy where needed.
- [ ] I updated `requirements-dev.txt` only for dev/test/tooling intent.
- [ ] If validators/workflows/docs disagreed with the intended model, I fixed them rather than changing the model to satisfy stale assumptions.

## Scope

This PR does:
- 
- 

This PR does **not** do:
- 
- 

## Files changed and why they belong together

- `requirements.txt`:
- `pyproject.toml`:
- `requirements-dev.txt`:
- workflows/tests/docs:

## Compatibility / risk notes

<!-- Call out framework upgrades, security changes, exact pins, or any platform-sensitive behavior. -->

## Validation run locally

- [ ] `pip install -r requirements.txt`
- [ ] `pip check`
- [ ] `pip install -e .`
- [ ] `python -c "from app import FinancialAssetApp; assert callable(getattr(FinancialAssetApp, 'create_interface', None))"`
- [ ] `python -c "from api.main import app"`
- [ ] `pip install -r requirements.txt -r requirements-dev.txt`
- [ ] `pip install -e ".[dev]"`

### Commands / outputs

```bash
# Paste the exact commands you ran
```

## Guardrail checklist

- [ ] This PR makes one primary dependency decision only.
- [ ] I did not mix dependency alignment with an unrelated framework/security upgrade.
- [ ] I did not broaden scope just to satisfy nearby failing validators.
- [ ] The PR description does not claim more than the code and validation actually prove.
- [ ] Relevant docs were updated if the supported install path or dependency policy changed.
