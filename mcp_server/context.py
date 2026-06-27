"""
Authoring-context loader for the RTEC synthesis agent.

Single source of truth lives in `resources/authoring/`:
  rtec_core.md          domain-agnostic language + mandatory declarations + gotchas
  task_wrapper.md       the standing synth->compile->run->refine procedure (with slots)
  domains/<app>.md      per-domain signature (events / input fluents / background)

The agent's full context for synthesizing one fluent is composed as:
    load_core()  +  load_domain(app)  +  rendered task_wrapper

This module is MCP-agnostic (same convention as discovery.py / rtec_runner.py): a harness
can call build_synthesis_prompt(app, nl) to get a system prompt; the MCP server exposes the
same content as resources + a prompt.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AUTHORING_DIR = REPO_ROOT / "resources" / "authoring"
CORE_FILE = AUTHORING_DIR / "rtec_core.md"
WRAPPER_FILE = AUTHORING_DIR / "task_wrapper.md"
DOMAINS_DIR = AUTHORING_DIR / "domains"


def _read(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"authoring file not found: {path}")
    return path.read_text()


def available_domains() -> list[str]:
    """Domain names that have an authoring file (matches the app/use-case names)."""
    if not DOMAINS_DIR.exists():
        return []
    return sorted(p.stem for p in DOMAINS_DIR.glob("*.md"))


def load_core() -> str:
    """The domain-agnostic RTEC authoring guide."""
    return _read(CORE_FILE)


def load_domain(app: str) -> str:
    """The per-domain signature file for `app` (e.g. 'maritime')."""
    path = DOMAINS_DIR / f"{app}.md"
    if not path.exists():
        raise ValueError(
            f"no authoring domain file for '{app}'. available: {available_domains()}"
        )
    return path.read_text()


def load_guide(app: str) -> str:
    """Core + domain — the reference material, without the task wrapper."""
    return load_core() + "\n\n" + load_domain(app)


def _wrapper_template() -> str:
    """The body of task_wrapper.md after its meta-header (the part with the slots)."""
    text = _read(WRAPPER_FILE)
    # the file starts with a title/description then a '---' separator; the real template
    # is everything after the first separator.
    _, sep, body = text.partition("\n---\n")
    return (body if sep else text).strip()


def build_synthesis_prompt(app: str, nl_description: str) -> str:
    """
    Compose the full agent context for synthesizing one fluent in `app`:
      core guide + domain signature + the task wrapper with {{APP}}/{{NL_DESCRIPTION}}
      filled in. Single-shot / bundled: suitable as one user message (MCP prompt) or as
      a whole-context system prompt.
    """
    wrapper = (
        _wrapper_template()
        .replace("{{APP}}", app)
        .replace("{{NL_DESCRIPTION}}", nl_description.strip())
    )
    return (
        load_core()
        + "\n\n"
        + load_domain(app)
        + "\n\n---\n\n"
        + wrapper
    )


def _wrapper_procedure() -> str:
    """The standing procedure, WITHOUT the 'TARGET COMPOSITE ACTIVITY' / {{NL}} tail."""
    tmpl = _wrapper_template()
    head, sep, _tail = tmpl.partition("TARGET COMPOSITE ACTIVITY:")
    return (head if sep else tmpl).rstrip()


def build_system_prompt(app: str) -> str:
    """
    The DURABLE context for `app`, with NO specific task: core guide + domain signature +
    the procedure (minus the target line). For multi-turn / harness use — inject this
    ONCE as the system prompt (it is identical across fluents, so it prompt-caches), then
    send each fluent's natural-language description as a separate user turn.
    """
    proc = _wrapper_procedure().replace("{{APP}}", app)
    return load_core() + "\n\n" + load_domain(app) + "\n\n---\n\n" + proc


if __name__ == "__main__":
    print("available domains:", available_domains())
    demo = ('"lowSpeed": The activity starts when the vessel starts moving at a low speed. '
            "The activity ends when the vessel stops moving at a low speed. When there is "
            "a gap in signal transmissions, we can no longer assume that the vessel "
            "continues moving at a low speed.")
    prompt = build_synthesis_prompt("maritime", demo)
    print(f"\nsynthesis prompt for maritime/lowSpeed: {len(prompt):,} chars")
    print(prompt[-800:])
