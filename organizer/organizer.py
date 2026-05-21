from agency_swarm import Agent, ModelSettings

from config import get_default_model, is_openai_provider


def create_organizer() -> Agent:
    return Agent(
        name="Organizer Agent",
        description="Manages video project folders, saves research to disk, and maintains a project index.",
        instructions="./instructions.md",
        tools_folder="./tools",
        model=get_default_model(),
        model_settings=ModelSettings(
            reasoning=None,
        ),
        conversation_starters=[
            "Crea un nuevo proyecto de video sobre el control emocional.",
            "Guarda esta investigacion en el proyecto 'disciplina-estoica'.",
            "Muestra el indice de todos los videos.",
            "Actualiza el estado del proyecto 'control-emocional' a 'guion listo'.",
        ],
    )
