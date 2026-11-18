from Services.agents.specialist_agent import generate_response
from Services.tools.search_tools import search_chroma


def rag_agent(llm, query: str):

    system_prompt = """
Você é um agente especializado em responder perguntas
utilizando uma base de conhecimento.

Você possui a ferramenta search_chroma para pesquisar
informações nos documentos.

Sempre pesquise na base antes de responder.

Utilize as informações encontradas para construir sua resposta.

Se não encontrar informações suficientes, informe isso
ao usuário. Nunca invente informações.
"""

    prompt = f"""
{system_prompt}

Pergunta do usuário:
{query}
"""

    return generate_response(
        llm=llm,
        prompt=prompt,
        tools=[search_chroma]
    )