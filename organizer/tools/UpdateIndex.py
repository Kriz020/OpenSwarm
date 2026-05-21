from agency_swarm.tools import BaseTool
from pathlib import Path
import json


VIDEOS_ROOT = Path("/Users/kriz/videos")
INDEX_PATH = VIDEOS_ROOT / "index.json"


class UpdateIndex(BaseTool):
    """Scans all video project folders and updates the central index at /Users/kriz/videos/index.json."""

    def run(self) -> str:
        VIDEOS_ROOT.mkdir(parents=True, exist_ok=True)

        projects = []
        for project_dir in sorted(VIDEOS_ROOT.iterdir()):
            if not project_dir.is_dir():
                continue
            metadata_path = project_dir / "metadata.json"
            if not metadata_path.exists():
                continue

            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

            file_count = sum(1 for f in project_dir.rglob("*") if f.is_file() and f.name != "metadata.json")
            metadata["file_count"] = file_count
            projects.append(metadata)

        index = {
            "total_projects": len(projects),
            "projects": projects,
        }

        INDEX_PATH.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")

        summary_lines = [f"Indice actualizado: {len(projects)} proyecto(s)"]
        for p in projects:
            summary_lines.append(f"  - [{p.get('status', '?')}] {p.get('title', p.get('slug', '?'))} ({p.get('file_count', 0)} archivos)")

        return "\n".join(summary_lines)
