"""TD runner — исполняет td-gen или standalone SKILL.md для генерации output'ов."""
import os, re, yaml
from pathlib import Path

ARCH = Path(__file__).resolve().parent.parent
TD_GEN = ARCH / "profiles" / "architect" / "skills" / "td-gen"
STANDALONE_SKILLS = ARCH / "profiles" / "architect" / "skills"
MAPPING_PATH = ARCH / "outputs" / "07.007" / "D" / "labor-function-to-skill-mapping.yaml"

def _find_skill_via_mapping(tf_code: str) -> Path | None:
    """Прочитать labor-function-to-skill-mapping.yaml и найти skill_path для ТФ."""
    if not MAPPING_PATH.exists():
        print(f"    [WARN] mapping not found: {MAPPING_PATH}")
        return None
    try:
        with open(MAPPING_PATH) as f:
            mapping = yaml.safe_load(f) or {}
    except Exception as e:
        print(f"    [WARN] mapping read error: {e}")
        return None

    for entry in mapping.get("mappings", []):
        if entry.get("tf_code") == tf_code:
            skill_rel = entry.get("skill_path", "")
            if skill_rel:
                candidate = STANDALONE_SKILLS / skill_rel
                if candidate.exists():
                    return candidate
                print(f"    [WARN] skill_path from mapping not found: {candidate}")
            return None
    return None


def generate(tf_code: str, la_id: str, input_files: list[str],
             output_dir: str, output_files: list[str], body: dict):
    """Найти skill для данной ТФ/ТД и выполнить генерацию.

    Порядок поиска:
      1. td-gen/{tf_dir}-{la_id}/SKILL.md
      2. labor-function-to-skill-mapping.yaml → skill_path
      3. generic fallback (минимальный YAML)
    """
    # ── 1. Поиск в td-gen ─────────────────────────────────────────
    tf_dir = tf_code.replace("/", "-")
    skill_md = TD_GEN / f"{tf_dir}-{la_id}" / "SKILL.md"
    found_from = "td-gen"

    if not skill_md.exists():
        # ── 2. Поиск через mapping ─────────────────────────────
        skill_md = _find_skill_via_mapping(tf_code)
        found_from = "mapping"

    if not skill_md or not skill_md.exists():
        print(f"    [WARN] no skill found for {tf_code} {la_id}")
        os.makedirs(output_dir, exist_ok=True)
        for fpath in output_files:
            oid = os.path.basename(fpath).replace(".yaml", "")
            with open(fpath, "w") as f:
                yaml.dump({"id": oid, "status": "generated", "error": "no skill"}, f)
        return

    with open(skill_md) as f:
        content = f.read()

    # Извлечь Python-код из секции ## Process
    match = re.search(r'## Process\n+```python\n(.+?)\n```', content, re.DOTALL)
    if not match:
        print(f"    [WARN] no python code in {skill_md}")
        return

    code = match.group(1)

    # Выполнить в контексте с доступом к переменным
    exec_scope = {
        "__builtins__": __builtins__,
        "input_files": input_files,
        "output_dir": output_dir,
        "output_files": output_files,
        "body": body,
        "yaml": yaml,
        "os": os,
        "re": re,
        "subprocess": __import__("subprocess"),
        "json": __import__("json"),
        "pathlib": __import__("pathlib"),
        "print": print,
    }

    try:
        exec(code, exec_scope)
        print(f"    ✅ Generated via {found_from}: {skill_md.name}")
    except Exception as e:
        print(f"    [ERROR] generation failed: {e}")
        import traceback
        traceback.print_exc()
