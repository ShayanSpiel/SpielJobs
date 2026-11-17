from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from .agent import search_jobs
from .tracing import flush_trace_client
mcp = FastMCP('SpielJobs', host='0.0.0.0', stateless_http=True, json_response=True)
@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True))
async def search_live_jobs(query: str, resume_text: str = '',session_id: str | None = None) -> dict:
    """Search Jobinja, Jobvision and configured company careers pages. Results include source links; review each source's coverage and status. Resume text is sent to a model if configured."""
    if not query.strip() or len(query)>2000 or len(resume_text)>30000:
        return {'error':'Query must be 1–2000 characters; resume text at most 30000 characters.'}
    if session_id is not None:
        import re
        if not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}',session_id):
            return {'error':'session_id must be an opaque identifier of at most 128 characters.'}
    return await search_jobs(query,resume_text,channel='mcp',session_id=session_id)
if __name__ == '__main__':
    try:
        mcp.run(transport='stdio')
    finally:
        flush_trace_client()
