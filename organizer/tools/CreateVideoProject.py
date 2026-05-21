from agency_swarm.tools import BaseTool
from pydantic import Field
from pathlib import Path
from datetime import date
import json


VIDEOS_ROOT = Path("/Users/kriz/videos")


class CreateVideoProject(BaseTool):
    """Creates a new video project folder with the standard directory structure and metadata."""

    title: str = Field(..., description="Title of the video (in Spanish)")
    slug: str = Field(..., description="URL-friendly slug for the folder name (lowercase, hyphens, no accents, e.g. 'control-emocional')")
    tags: list[str] = Field(default_factory=list, description="List of topic tags (e.g. ['estoicismo', 'marco-aurelio'])")
    stoic_source: str = Field(default="", description="Primary Stoic source (e.g. 'Meditaciones, Libro V')")
    psychology_angle: str = Field(default="", description="Psychology angle (e.g. 'Regulacion emocional, CBT')")
    hook: str = Field(default="", description="Hook phrase for the video")

    def run(self) -> str:
        project_dir = VIDEOS_ROOT / self.slug

        if project_dir.exists():
            return f"Error: El proyecto '{self.slug}' ya existe en {project_dir}. Usa otro slug o confirma si quieres sobrescribir."

        for subdir in ["research", "script", "assets/images", "assets/audio", "output"]:
            (project_dir / subdir).mkdir(parents=True, exist_ok=True)

        metadata = {
            "title": self.title,
            "slug": self.slug,
            "status": "research",
            "created": date.today().isoformat(),
            "updated": date.today().isoformat(),
            "tags": self.tags,
            "stoic_source": self.stoic_source,
            "psychology_angle": self.psychology_angle,
            "hook": self.hook,
        }
        metadata_path = project_dir / "metadata.json"
        metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

        return (
            f"Proyecto creado exitosamente:\n"
            f"  Carpeta: {project_dir}\n"
            f"  Subcarpetas: research/, script/, assets/images/, assets/audio/, output/\n"
            f"  Metadata: {metadata_path}\n"
            f"  Estado: research"
        )
