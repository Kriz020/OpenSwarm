from agency_swarm.tools import BaseTool
from pydantic import Field
from pathlib import Path
from datetime import date
import json


VIDEOS_ROOT = Path("/Users/kriz/videos")


class SaveResearch(BaseTool):
    """Saves research content to a specific video project folder on disk."""

    slug: str = Field(..., description="Project slug (folder name under /Users/kriz/videos/)")
    filename: str = Field(..., description="Filename to save (e.g. 'investigacion.md', 'citas.md', 'guion.md')")
    content: str = Field(..., description="Content to save (markdown format)")
    subfolder: str = Field(default="research", description="Subfolder within the project: 'research', 'script', or 'assets'")

    def run(self) -> str:
        project_dir = VIDEOS_ROOT / self.slug

        if not project_dir.exists():
            return f"Error: El proyecto '{self.slug}' no existe. Usa CreateVideoProject primero."

        target_dir = project_dir / self.subfolder
        target_dir.mkdir(parents=True, exist_ok=True)

        filepath = target_dir / self.filename
        filepath.write_text(self.content, encoding="utf-8")

        metadata_path = project_dir / "metadata.json"
        if metadata_path.exists():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["updated"] = date.today().isoformat()
            metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

        return f"Guardado: {filepath} ({len(self.content)} caracteres)"
