import os, json, pathlib, subprocess
from typing import List, Dict
from openai import OpenAI

PROJECT_ROOT = pathlib.Path(".").resolve()
IGNORE_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", "static/assets"}
MAX_FILE_BYTES = 120_000
MAX_TOTAL_BYTES = 800_000
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")  # set to gpt-5 later

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

SYSTEM = """You are a careful code editor for a small Flask/Jinja game project.
Return ONLY JSON with this schema:
{
  "changes": [
    {"path": "relative/path.ext", "content": "<entire new file content>"}
  ],
  "commit_message": "short imperative",
  "notes": "optional short reasoning"
}
Rules:
- Provide FULL file contents for any file you change (no diffs).
- Keep code runnable; preserve imports and style.
- Prefer minimal, safe edits.
- Output must be valid JSON. No backticks or extra text.
"""

def _list_candidate_files() -> List[pathlib.Path]:
    files = []
    for p in PROJECT_ROOT.rglob("*"):
        if p.is_file() and not any(part in IGNORE_DIRS for part in p.parts):
            if p.suffix.lower() in {".py",".html",".css",".js",".json",".md",".txt",".toml",".yaml",".yml",".ini"}:
                files.append(p)
    return files

def _repo_snapshot() -> str:
    total = 0
    chunks = []
    for p in _list_candidate_files():
        try:
            b = p.read_bytes()
        except Exception:
            continue
        if len(b) > MAX_FILE_BYTES:
            b = b[:MAX_FILE_BYTES]
        if total + len(b) > MAX_TOTAL_BYTES:
            break
        total += len(b)
        chunks.append(f"\n=== FILE: {p.as_posix()} ===\n{b.decode('utf-8','replace')}")
    return "".join(chunks)

def plan_changes(instruction: str) -> Dict:
    prompt = f"""User request:
{instruction}

Repository snapshot (truncated):
{_repo_snapshot()}
"""
    resp = client.responses.create(
        model=MODEL,
        input=[{"role":"system","content":SYSTEM},{"role":"user","content":prompt}]
    )
    text = resp.output_text.strip()
    start = text.find("{"); end = text.rfind("}")
    if start == -1 or end == -1:
        raise RuntimeError(f"Model did not return JSON:\n{text}")
    return json.loads(text[start:end+1])

def apply_changes(payload: Dict) -> Dict:
    changes = payload.get("changes", [])
    written = []
    for ch in changes:
        path = PROJECT_ROOT / ch["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(ch["content"])
        written.append(path.as_posix())
    return {"written": written, "commit_message": payload.get("commit_message","AI edit")}

def try_git_commit(message: str) -> int:
    def run(cmd):
        try:
            return subprocess.call(cmd)
        except FileNotFoundError:
            return 127
    if not (PROJECT_ROOT/".git").exists():
        run(["git","init"])
        run(["git","add","."])
        return run(["git","commit","-m","Initial commit"])
    run(["git","add","."])
    return run(["git","commit","-m",message])
