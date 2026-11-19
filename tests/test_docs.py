"""Offline consistency checks for the documentation.

- Every relative Markdown link points at a file that exists in the repo.
- Every Mermaid flowchart avoids node IDs that GitHub's Mermaid renderer
  rejects as reserved words (this broke rendering once, in April 2026).
- Every doc in docs/ is reachable from the README.
- (Opt-in, network) every linked GitHub repo is publicly reachable:
  CHECK_EXTERNAL_LINKS=1 pytest

Standard library + pytest only; the default run needs no network.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MARKDOWN = sorted([ROOT / "README.md", *(ROOT / "docs").glob("*.md")])

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
FENCE_RE = re.compile(r"```mermaid\n(.*?)```", re.S)

# Words Mermaid's flowchart grammar treats specially; using one as a node ID
# makes GitHub refuse to render the diagram.
RESERVED_IDS = {
    "graph", "flowchart", "subgraph", "end", "in", "out", "style", "class",
    "classDef", "click", "linkStyle", "direction", "call", "href", "default",
}
DIRECTIVE_RE = re.compile(
    r"^(?:(?:flowchart|graph)\s+(?:TB|TD|BT|RL|LR)\b"
    r"|(?:classDef|class|style|linkStyle|click|direction)\s"
    r"|subgraph\b|end$|%%)"
)


def _ids_in_flowchart_line(line: str) -> list[str]:
    """Return node IDs referenced on one flowchart edge/node line."""
    s = line.strip()
    if not s or DIRECTIVE_RE.match(s):
        return []
    s = re.sub(r":::[\w-]+", "", s)                       # class shorthand
    s = re.sub(r'"[^"]*"', "", s)                         # quoted labels
    s = re.sub(r"\|[^|]*\|", " ", s)                      # |edge labels|
    # Node shapes: [..], (..), ([..]), [(..)], {..}, ((..)) - strip contents.
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r"\[[^\[\]]*\]|\([^()]*\)|\{[^{}]*\}", "", s)
    s = re.sub(r"--\s[^-]*?\s-->", " --> ", s)            # -- text -->
    s = re.sub(r"-\.[^.\->]+\.-", " --- ", s)             # -.text.-
    tokens = re.split(r"\s*(?:<?[-=.]+>?|&)\s*|\s+", s)
    return [t for t in tokens if re.fullmatch(r"[A-Za-z_][\w]*", t)]


def _flowcharts():
    for md in MARKDOWN:
        for block in FENCE_RE.findall(md.read_text(encoding="utf-8")):
            first = block.strip().splitlines()[0].strip()
            if first.startswith(("flowchart", "graph")):
                yield md, block


@pytest.mark.parametrize("md", MARKDOWN, ids=lambda p: p.name)
def test_relative_links_resolve(md: Path):
    text = md.read_text(encoding="utf-8")
    broken = []
    for target in LINK_RE.findall(text):
        if re.match(r"^[a-z]+:", target) or target.startswith("#"):
            continue  # external URL or same-page anchor
        path = target.split("#", 1)[0]
        if not (md.parent / path).exists():
            broken.append(target)
    assert not broken, f"{md.name}: broken relative links {broken}"


def test_flowchart_node_ids_are_not_reserved():
    offenders = []
    for md, block in _flowcharts():
        for line in block.splitlines()[1:]:
            for node_id in _ids_in_flowchart_line(line):
                if node_id in RESERVED_IDS:
                    offenders.append((md.name, node_id, line.strip()))
    assert not offenders, f"reserved Mermaid node IDs: {offenders}"


def test_id_extractor_catches_reserved_words():
    # Guards the guard: the regression this test exists for.
    assert "graph" in _ids_in_flowchart_line("graph[(Store)] --> retrieval")
    assert "out" in _ids_in_flowchart_line("reason --> out")
    assert "end" in _ids_in_flowchart_line("  start -.-> end")
    assert _ids_in_flowchart_line("kgraph -.gated.- daydream") == ["kgraph", "daydream"]


def test_every_doc_is_linked_from_readme():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    missing = [p.name for p in (ROOT / "docs").glob("*.md") if f"docs/{p.name}" not in readme]
    assert not missing, f"docs not linked from README: {missing}"


GITHUB_REPO_RE = re.compile(r"https://github\.com/([\w.-]+/[\w.-]+?)(?:\.git)?(?=[)/#\s]|$)")


def _linked_github_repos() -> list[str]:
    repos = set()
    for md in MARKDOWN:
        for target in LINK_RE.findall(md.read_text(encoding="utf-8")):
            m = GITHUB_REPO_RE.match(target)
            if m:
                repos.add(m.group(1))
    return sorted(repos)


@pytest.mark.skipif(
    os.environ.get("CHECK_EXTERNAL_LINKS") != "1",
    reason="network check; set CHECK_EXTERNAL_LINKS=1 to run",
)
@pytest.mark.parametrize("repo", _linked_github_repos())
def test_linked_github_repos_are_public(repo: str):
    """Every linked GitHub repo answers an anonymous `git ls-remote`.

    Run this before publishing: the sibling repos must be public first.
    """
    result = subprocess.run(
        ["git", "ls-remote", f"https://github.com/{repo}", "HEAD"],
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    assert result.returncode == 0, f"{repo} is not publicly reachable: {result.stderr.strip()}"
