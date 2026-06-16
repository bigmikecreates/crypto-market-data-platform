"""PR drift checker: detect source changes without corresponding doc changes.

Run in CI on pull requests. Uses `git diff` against the base branch to find
changed files, then checks whether each changed source file has a matching
doc change. Prints warnings for missing doc updates.
"""

import os
import subprocess
import sys
from typing import Dict, List

# Mapping: source glob prefix -> expected doc file(s)
# A source change should trigger a warning if none of the listed docs changed.
SOURCE_DOC_MAP: Dict[str, List[str]] = {
    "src/crmd_platform/cli/":           ["docs/reference/cli.md"],
    "src/crmd_platform/server/":        ["docs/reference/http-api.md"],
    "src/crmd_platform/models/":        ["docs/data-model.md", "docs/reference/parquet-schema.md"],
    "src/crmd_platform/providers/":     ["docs/providers.md"],
    "src/crmd_platform/validation/":    ["docs/validation-strategy.md", "docs/reference/validation-rules.md"],
    "src/crmd_platform/storage/":       ["docs/storage-e2e.md", "docs/reference/parquet-schema.md"],
    "src/crmd_platform/query/":         ["docs/reference/python-api.md"],
    "src/crmd_platform/ingestion/":     ["docs/storage-e2e.md"],
    "src/crmd_platform/benchmark/":     ["docs/benchmark-design.md"],
    "src/crmd_platform/client.py":      ["docs/reference/python-api.md", "docs/getting-started.md"],
    "frontend/lib/api.ts":              ["docs/reference/http-api.md"],
    "frontend/app/explorer/":           ["docs/reference/http-api.md"],
    "infra/":                           ["docs/deploy/cloud.md"],
    "docker-compose.yml":               ["docs/deploy/self-hosted.md"],
    "docker-compose.dev.yml":           ["docs/deploy/self-hosted.md"],
    "Dockerfile":                       ["docs/deploy/self-hosted.md"],
}

EXEMPT_PATTERNS = [
    "__pycache__",
    ".pyc",
    ".bench_tmp",
    "requirements.*.txt",
]


def get_changed_files(base_ref: str) -> List[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", base_ref, "--"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        print(f"::warning::Could not diff against {base_ref}: {result.stderr.strip()}")
        return get_head_changed_files()
    files = [f.strip() for f in result.stdout.splitlines() if f.strip()]
    if not files and result.stdout.strip():
        return get_head_changed_files()
    return files


def get_head_changed_files() -> List[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD~1", "--"],
        capture_output=True, text=True, check=False,
    )
    return [f.strip() for f in result.stdout.splitlines() if f.strip()]


def match_source(source: str) -> List[str]:
    for pattern, docs in SOURCE_DOC_MAP.items():
        if source.startswith(pattern) or source == pattern:
            return docs
    return []


def is_exempt(path: str) -> bool:
    return any(p in path for p in EXEMPT_PATTERNS)


def main() -> None:
    base_ref = os.environ.get("DRIFT_BASE_REF", "origin/main")
    changed = get_changed_files(base_ref)

    if not changed:
        print("No changed files detected — skipping drift check.")
        sys.exit(0)

    source_changes = [f for f in changed if not is_exempt(f)]
    doc_changes = [f for f in changed if f.startswith("docs/")]

    print(f"Changed source files: {len(source_changes)}")
    print(f"Changed doc files:    {len(doc_changes)}")
    print()

    warnings: List[str] = []

    for src in sorted(source_changes):
        required_docs = match_source(src)
        if not required_docs:
            continue
        missing = [d for d in required_docs if d not in doc_changes]
        if missing:
            msg = f"  {src} → missing: {', '.join(missing)}"
            warnings.append(msg)

    if warnings:
        print("::warning::Drift detected — source changes without matching doc updates:")
        for w in warnings:
            print(f"::warning::{w}")
        print()
        print("If this is intentional, check the 'Documentation drift check' section")
        print("in the PR template to confirm no doc updates are needed.")
        sys.exit(0)
    else:
        print("No drift detected — all source changes have matching doc updates.")


if __name__ == "__main__":
    main()
