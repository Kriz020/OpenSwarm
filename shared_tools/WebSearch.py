from agency_swarm.tools import BaseTool
from pydantic import Field


class WebSearch(BaseTool):
    """Search the web for current information using DuckDuckGo."""

    query: str = Field(..., description="Search query to look up on the web.")
    max_results: int = Field(default=5, description="Max number of results to return (1-10).")

    def run(self) -> str:
        from ddgs import DDGS

        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(self.query, max_results=self.max_results):
                results.append(
                    f"**{r.get('title', '')}**\n"
                    f"URL: {r.get('href', '')}\n"
                    f"{r.get('body', '')}\n"
                )

        if not results:
            return "No results found."

        return "\n---\n".join(results)
