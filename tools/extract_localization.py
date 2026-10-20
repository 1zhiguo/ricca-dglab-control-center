"""Inventory shipped Chinese UI strings (never reads user configuration)."""
import ast
import json
from pathlib import Path
import re


def sources(root):
    found = set()
    for path in (root / "src/ricca_dglab").glob("*.py"):
        if path.name == "localization.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        found.update(node.value for node in ast.walk(tree) if isinstance(node, ast.Constant)
                     and isinstance(node.value, str) and re.search(r"[\u3400-\u9fff]", node.value))
    tokens = re.compile(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'')
    for path in (root / "src/ricca_dglab/qml").glob("*.qml"):
        for match in tokens.finditer(path.read_text(encoding="utf-8-sig")):
            token = match.group()
            if token.startswith(("//", "/*")):
                continue
            if re.search(r"[\u3400-\u9fff]", token):
                try:
                    found.add(ast.literal_eval(token))
                except (ValueError, SyntaxError):
                    pass
    return sorted(found, key=lambda value: (len(value), value))


if __name__ == "__main__":
    print(json.dumps(sources(Path(__file__).resolve().parents[1]), ensure_ascii=False))
