"""Ferramentas que delegam tarefas aos agentes especializados."""


def build_rag_tool(llm):
    # O modelo é uma dependência local; nunca é um argumento enviado pela LLM.
    def consult_knowledge_base(query: str) -> str:
        """Consulta o agente RAG sobre informações institucionais nos documentos.

        Use para perguntas sobre a PUC-Campinas, SBI, bibliotecas, inclusão,
        matrícula, bolsas, cursos, normas e procedimentos institucionais.

        Args:
            query: Pergunta completa do usuário, preservando o assunto e detalhes.
        """
        if not isinstance(query, str) or not query.strip():
            raise ValueError('A consulta ao RAG deve ser uma pergunta não vazia.')
        from Agents.ragAgent import rag_agent
        return rag_agent(llm, query.strip())

    return consult_knowledge_base
