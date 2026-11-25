def build_rag_tool(llm, *, history: list | None = None, current_url: str | None = None):
    # O modelo é uma dependência local; nunca é um argumento enviado pela LLM.
    def consult_knowledge_base(query: str) -> str:
        """Consulta o agente RAG sobre informações institucionais nos documentos.

        Use para perguntas sobre a PUC-Campinas, SBI, bibliotecas, inclusão,
        matrícula, bolsas, cursos, normas e procedimentos institucionais.
        Também localiza páginas, interpreta conteúdo e orienta a navegação no site.

        Args:
            query: Pergunta completa do usuário, preservando o assunto e detalhes.
        """
        if not isinstance(query, str) or not query.strip():
            raise ValueError('A consulta ao RAG deve ser uma pergunta não vazia.')
        from Agents.ragAgent import rag_agent
        context = {}
        if history:
            context['history'] = history
        if current_url:
            context['current_url'] = current_url
        return rag_agent(llm, query.strip(), **context)

    return consult_knowledge_base
