import logging

from Services.agents.specialist_agent import generate_response
from Services.tools.document_tools import build_document_tool
from Agents.prompts.ragAgent_prompt import SPECIALIST_PROMPT, build_user_prompt as build_specialist_prompt
from Agents.prompts.ragAgent_diagnostic_prompt import SYSTEM_PROMPT, build_user_prompt as build_diagnostic_prompt


def search_evidence(query: str, top_k: int = 5):
    from Services.orm.search import search_evidence as search
    return search(query, top_k=top_k)


def diagnose_rag(llm, query: str, evidence: list[dict] | None = None, *, history: list | None = None):
    if evidence is None:
        evidence = search_evidence(query, top_k=5)
    report = {"query": query, "evidence": evidence, "raw_response": None,
              "status": "pending", "response": None}
    response = generate_response(
        llm=llm,
        prompt=build_diagnostic_prompt(query, evidence),
        tools=[],
        system_prompt=SYSTEM_PROMPT,
        history=history,
    )
    report.update(raw_response=response, response=response,
                  status='answered' if response.strip() else 'empty_generation')
    return report


def build_graph_tools(current_url, on_result):
    from Services.tools.neo4j_tools import build_neo4j_tools
    return build_neo4j_tools(current_url, on_result=on_result)


def rag_agent(llm, query: str, *, history: list | None = None, current_url: str | None = None):

    observations = []
    documents = []

    search_documents = build_document_tool(documents, search=search_evidence,
        on_result=lambda operation, result: observations.append((operation, result)))

    graph_tools = build_graph_tools(current_url,
        on_result=lambda operation, result: observations.append((operation, result)))
    search_documents(query=query)
    prompt = build_specialist_prompt(query, current_url, documents=documents)
    logging.getLogger(__name__).info('Especialista: documentos iniciais=%s', len(documents))
    response = generate_response(llm, prompt=prompt,
        tools=[search_documents, *graph_tools], system_prompt=SPECIALIST_PROMPT,
        history=history, max_iterations=4)

    return response
