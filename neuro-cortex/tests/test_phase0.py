"""Phase 0: Minimum viable test to verify project structure."""
import pytest


def test_project_structure():
    """Verify all required directories exist."""
    import os
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    required = [
        "src/neurocortex",
        "src/neurocortex/perception",
        "src/neurocortex/representation",
        "src/neurocortex/attention",
        "src/neurocortex/state",
        "src/neurocortex/memory",
        "src/neurocortex/prediction",
        "src/neurocortex/decision",
        "src/neurocortex/action",
        "src/neurocortex/feedback",
        "src/neurocortex/learning",
        "tests",
        "config",
        "scripts",
    ]
    for d in required:
        path = os.path.join(base, d)
        assert os.path.isdir(path), f"Missing directory: {d}"


def test_pyproject_exists():
    """Verify pyproject.toml exists at project root."""
    import os
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assert os.path.isfile(os.path.join(base, "pyproject.toml"))


def test_readme_exists():
    """Verify README.md exists at project root."""
    import os
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assert os.path.isfile(os.path.join(base, "README.md"))


def test_gitignore_exists():
    """Verify .gitignore exists at project root."""
    import os
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assert os.path.isfile(os.path.join(base, ".gitignore"))
