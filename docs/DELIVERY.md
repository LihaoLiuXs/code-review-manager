# Deliverable directory structure

Generated outputs, installed dependencies and Git internals are omitted.

```text
human-review-learning/
├── .agents/
│   └── skills/
│       └── learn-reviews/
│           └── SKILL.md
├── .claude/
│   └── skills/
│       └── learn-reviews/
│           └── SKILL.md -> ../../../.agents/skills/learn-reviews/SKILL.md
├── docs/
│   ├── DIRECTORY_DEMO.md
│   ├── DEMO.md
│   ├── DELIVERY.md
│   ├── SDK.md
│   └── VALIDATION.md
├── examples/
│   ├── review_bundle/                 # Synthetic nested directory-demo input
│   └── review_knowledge.demo.md
├── hrl/
│   ├── __init__.py
│   ├── classification.py
│   ├── cli.py
│   ├── console.py
│   ├── demo_operations.py
│   ├── directory_demo.py
│   ├── github_reviews.py
│   ├── io.py
│   ├── knowledge.py
│   └── multicloud_store.py
├── output/
│   └── .gitkeep
├── scripts/
│   ├── demo.py
│   ├── fetch_reviews.py
│   ├── storage.py
│   └── workflow.py
├── tests/
│   ├── test_separate_demo_operations.py
│   ├── test_directory_demo.py
│   ├── test_demo_command.py
│   ├── test_interactive_demo.py
│   ├── test_cli.py
│   ├── test_confirmation.py
│   ├── test_storage_demo_logging.py
│   ├── test_provider_selection.py
│   ├── test_repo_input.py
│   └── test_workflow.py
├── .env.example
├── .gitignore
├── AGENTS.md
├── LICENSE
├── README.md
├── config.example.toml
├── demo                                  # Executable SDK demo launcher
├── pyproject.toml
├── requirements-dev.txt
└── requirements.txt
```

Local-only directories: `.venv/` (installed runtime), `.sdk/multicloud-py/`
(inspected source SDK), `output/` (repository-specific review artifacts).

See [README](../README.md) for component explanations, installation, skill and CLI
commands, and the complete demo walkthrough. See [SDK investigation](SDK.md) for
actual classes/methods and [validation](VALIDATION.md) for executed checks.
