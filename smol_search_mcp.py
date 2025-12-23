from mcp.server.fastmcp import FastMCP
from smolagents import DuckDuckGoSearchTool, VisitWebpageTool, Tool
import wikipedia

# Initialize the FastMCP server
mcp = FastMCP("SmolAgents Tools")

# --- Initialize SmolAgents Tools ---

# 1. DuckDuckGo Search
ddg_tool = DuckDuckGoSearchTool()

# 2. Webpage Visitor (Fetches and converts to markdown)
visit_tool = VisitWebpageTool()

# 3. Wikipedia Tool (Custom implementation using smolagents Tool base)
class WikipediaSearchTool(Tool):
    name = "wikipedia_search"
    description = "Searches Wikipedia for a query and returns the summary of the top result."
    inputs = {
        "query": {
            "type": "string", 
            "description": "The search query to look up on Wikipedia."
        }
    }
    output_type = "string"

    def forward(self, query: str) -> str:
        try:
            # Search for the page
            search_results = wikipedia.search(query)
            if not search_results:
                return "No Wikipedia results found."
            
            # Get the summary of the first result
            summary = wikipedia.summary(search_results[0], sentences=3)
            return f"Title: {search_results[0]}\nSummary: {summary}"
        except wikipedia.exceptions.DisambiguationError as e:
            return f"Ambiguous query. Options: {e.options[:5]}"
        except Exception as e:
            return f"Error fetching Wikipedia data: {str(e)}"

wiki_tool = WikipediaSearchTool()

# --- Expose Tools via MCP ---

@mcp.tool()
def web_search(query: str) -> str:
    """
    Performs a web search using DuckDuckGo via smolagents.
    
    Use this tool to find current events, general knowledge, or verify facts
    that are not in your internal knowledge base.

    Args:
        query: The search terms to look for.
    """
    # smolagents tools are callable via .forward() or __call__()
    return ddg_tool.forward(query)

@mcp.tool()
def visit_webpage(url: str) -> str:
    """
    Visits a specific URL and returns the content in Markdown format.
    
    Use this to read the full content of a webpage after finding a URL 
    via web_search. Useful for documentation, articles, or news.

    Args:
        url: The direct URL to visit (must start with http/https).
    """
    return visit_tool.forward(url)

@mcp.tool()
def search_wikipedia(query: str) -> str:
    """
    Searches Wikipedia for a specific topic and returns a summary.
    
    Use this for encyclopedic knowledge, historical events, or definitions
    where a high-quality, curated source is preferred over general web search.

    Args:
        query: The topic to search for (e.g., 'Quantum Computing', 'Albert Einstein').
    """
    return wiki_tool.forward(query)

if __name__ == "__main__":
    # fastmcp runs the stdio server automatically when run
    mcp.run()
