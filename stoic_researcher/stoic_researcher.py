from agency_swarm import Agent, ModelSettings

from config import get_default_model, is_openai_provider
from shared_tools import WebSearch
from organizer.tools.SaveResearch import SaveResearch


def create_stoic_researcher() -> Agent:
    tools = [WebSearch, SaveResearch]

    try:
        from agency_swarm.tools import WebSearchTool
        if is_openai_provider():
            tools[0] = WebSearchTool()
    except ImportError:
        pass

    return Agent(
        name="Stoic Researcher Agent",
        description="Specialized researcher in Stoic philosophy and modern psychology, with deep knowledge of Marcus Aurelius, Seneca, Epictetus, and their connections to CBT and emotional regulation.",
        instructions="./instructions.md",
        tools=tools,
        model=get_default_model(),
        model_settings=ModelSettings(
            reasoning=None,
        ),
        conversation_starters=[
            "Investiga sobre el control emocional segun Marco Aurelio y la psicologia moderna.",
            "Busca las mejores citas de Seneca sobre la disciplina diaria.",
            "Que dice la psicologia moderna sobre el estoicismo terapeutico?",
            "Compara la premeditatio malorum con la terapia de exposicion cognitiva.",
        ],
    )
