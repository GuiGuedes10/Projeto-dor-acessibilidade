from Services.agents.specialist_agent import generate_response
from Services.tools.agent_tools import build_rag_tool
import re
from Agents.prompts.coordinatorAgent_prompt import SYSTEM_PROMPT, get_system_prompt


def coordinator_agent(llm, query: str, *, extra_tools: list | None = None,
                      max_iterations: int = 3, history: list | None = None,
                      current_url: str | None = None):
    if not isinstance(query, str) or not query.strip():
        raise ValueError('A pergunta não pode estar vazia.')
    if re.fullmatch(r'(oi|olá|ola|bom dia|boa tarde|boa noite|obrigado|obrigada)[!.,\s]*', query.strip(), re.I):
        return 'Olá! Posso ajudar com informações e serviços da PUC-Campinas. O que você precisa saber?'
    context = {}
    if history:
        context['history'] = history
    if current_url:
        context['current_url'] = current_url
    rag_tool = build_rag_tool(llm, original_query=query.strip(), **context)
    tools = [rag_tool, *(extra_tools or [])]
    return generate_response(
        llm=llm, prompt=query.strip(), tools=tools,
        system_prompt=get_system_prompt(has_current_url=bool(current_url)), max_iterations=max_iterations,
        history=history,
    )
