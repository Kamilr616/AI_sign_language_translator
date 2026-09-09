<!-- See CONTRIBUTING.md for the full workflow. Target `develop`, or the relevant `variant/*` branch — never `main`. -->

## Summary

<!-- What does this change do, and why? -->

## Related issue

<!-- e.g. Closes #12 — or "none" for a self-contained fix. -->

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Documentation
- [ ] Tests or CI
- [ ] Build or packaging
- [ ] Change to a product variant (`variant/*`)

## Checklist

- [ ] `python -m pytest` passes locally on Python 3.10 or 3.12
- [ ] Targets `develop` (or the relevant `variant/*` branch), not `main`
- [ ] Every commit is self-contained and passes on its own (branch rebased onto the target, not merged)
- [ ] Commit subjects are English, imperative, capitalized, without a trailing period
- [ ] `README.md` and `README.pl.md` kept equivalent; technical documentation EN/PL kept equivalent if touched
- [ ] Local links in changed documentation verified
- [ ] `src/gui.py` regenerated with `pyside6-uic`, not hand-edited
- [ ] No `.task` model replaced without documented provenance and updated `models/SHA256SUMS.txt`
- [ ] `THIRD_PARTY_NOTICES.md` updated if a dependency, version constraint, bundled wheel or model changed
- [ ] No credentials, datasets or personal forms committed
