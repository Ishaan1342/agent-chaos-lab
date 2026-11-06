# Contributing to agent-chaos-lab

This project is an early MVP. Small, reproducible improvements are welcome.
Discuss substantial API or architecture changes in an issue before implementing
them. Check existing issues and pull requests to avoid duplicate work.

## Local setup

Use Python 3.11+ in a virtual environment. Install with `python -m pip install -e '.[mcp]'`, then run
`python -m unittest discover -s tests -v`. The README describes demo commands and
optional integrations. Do not call paid services from tests.

## Pull requests

- Describe the actual problem, reproduction, scope and before/after result.
- Add a regression test for behavior changes. Run relevant tests and packaging checks.
- Keep fixtures synthetic or explicitly licensed; never include credentials,
  private logs, customer data, local environments or personal build records.
- Preserve the documented MVP limitations. Do not present an oracle harness
  result as model accuracy or a content hash as signed provenance.
- Review your changes and be prepared to explain them. You are responsible
  for their correctness.
- Be respectful and discuss technical disagreements constructively.

Contributions are made under the project's MIT license. No copyright transfer
or separate contributor agreement is required by this project.
