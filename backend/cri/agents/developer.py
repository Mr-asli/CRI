"""Deterministic code-draft generator. It never executes or promotes generated code."""
from dataclasses import dataclass
import hashlib

@dataclass(frozen=True)
class CodeDraft:
    filename: str
    content: str
    sha256: str
    status: str = "draft_only"

class Developer:
    def generate(self, specification: str, filename: str = "generated_module.py") -> CodeDraft:
        if not isinstance(specification, str) or not specification.strip() or len(specification) > 4000:
            raise ValueError("specification must contain 1 to 4000 characters")
        if not filename.endswith(".py") or "/" in filename or "\\" in filename or filename in {".", ".."}:
            raise ValueError("filename must be a plain Python filename")
        safe = specification.strip().replace('"', "'")
        content = (
            '"""CRI generated draft. Review and test before use."""\n\n'
            f"SPECIFICATION = {safe!r}\n\n"
            "def run(context: dict) -> dict:\n"
            '    """Return a reviewable draft result; no filesystem or network access."""\n'
            "    if not isinstance(context, dict):\n"
            "        raise TypeError('context must be a dict')\n"
            "    return {'specification': SPECIFICATION, 'input_keys': sorted(context.keys())}\n"
        )
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return CodeDraft(filename, content, digest)
