# Mapa do site parceiro

## Organização do código

- `neo4j_service.py`: interface das operações de páginas, links e caminhos.
- `config.py`: leitura do `.env`, credenciais, limites e validação do esquema.
- `connection.py`: criação e encerramento do driver e execução das consultas.
- `queries.py`: construção das consultas Cypher e projeção dos campos.
- `pages.py`: formatação dos resultados e tratamento de páginas restritas.
- `urls.py`: política do domínio parceiro e variantes de URL do crawler.

Os utilitários reutilizáveis ficam em `Backend/Utils`: `url_utils.py` valida e
normaliza URLs com filtro opcional de domínio; `html_utils.py` extrai texto do
HTML; `text_utils.py` prepara palavras-chave com filtros fornecidos pelo chamador.
Esses utilitários não acessam o `.env` nem dependem do Neo4j. Os imports de
`Neo4jService` e `get_service` continuam em `neo4j_service.py`.

O service usa o driver oficial do Neo4j e consultas Cypher fixas e parametrizadas.
Não executa Cypher fornecido pela LLM e não altera o grafo. Os caminhos respeitam
o sentido das relações e têm até 15 saltos por padrão (`NEO4J_MAX_HOPS`, máximo 30).
As consultas têm timeout e os resultados e conteúdos retornados são limitados.

## Configuração

Copie o bloco `NEO4J_*` de `.env.exemple` para `.env`. O URI é o endpoint do
driver, como `neo4j+s://seu-banco.databases.neo4j.io` ou `bolt://localhost:7687`.
Não use o endereço HTTP do Neo4j Browser. Configure banco, usuário e senha.
Prefira uma credencial com permissão de leitura.
Use `NEO4J_USER`, como no crawler. `NEO4J_USERNAME` é aceito como alternativa;
se ambos estiverem preenchidos, `NEO4J_USER` tem prioridade.

O esquema padrão corresponde ao crawler fornecido:

```cypher
(:Pagina {url: 'https://www.puc-campinas.edu.br/', descricao: 'Início', html: '...', restrita: false})
  -[:LINKA_PARA]->
(:Pagina {url: 'https://www.puc-campinas.edu.br/exemplo/'})
```

Cada label e propriedade pode ser alterado por `NEO4J_PAGE_LABEL`,
`NEO4J_URL_PROPERTY`, `NEO4J_TITLE_PROPERTY`, `NEO4J_HTML_PROPERTY`,
`NEO4J_RESTRICTED_PROPERTY`, `NEO4J_TEXT_PROPERTY`, `NEO4J_LINK_RELATION` e
`NEO4J_LINK_TEXT_PROPERTY`. `descricao` é exposta como `title` para apresentação
dos resultados, sem afirmar que seja o título HTML da página.
O crawler não grava `text` nem textos de âncora. Deixe os dois campos opcionais
vazios para não consultar propriedades inexistentes. O conteúdo vem do HTML.
Se já copiou o bloco antigo do exemplo para `.env`, atualize seus nomes de
label, relação e propriedades também nesse arquivo; valores explícitos têm
prioridade sobre os padrões do código.

Páginas com `restrita=true` não fornecem conteúdo para o agente, mesmo se um
HTML antigo continuar no nó. URLs descobertas sem `restrita`, descrição ou HTML
são identificadas como `url_only`; não são automaticamente consideradas restritas.
O service preserva o endereço original da semente com `#/` e também tenta o
endereço sem fragmento, usado nos links do crawler. Quando só o documento-base
é encontrado, retorna `location_match=document_only`, não uma confirmação da
tela interna atual. Caminhos têm `scope=mapped_documents`.

`NEO4J_ALLOWED_DOMAINS` aceita domínios separados por vírgula e
inclui seus subdomínios; o padrão é `puc-campinas.edu.br`.

Para descobrir o esquema, após preencher as credenciais, execute em `Backend`:

```powershell
python tests/inspect_neo4j.py --schema
python tests/inspect_neo4j.py --search "sistemas de informação"
python tests/inspect_neo4j.py --url "https://www.puc-campinas.edu.br/"
python tests/inspect_neo4j.py --url "https://arealogada.sis.puc-campinas.edu.br/#/"
python tests/inspect_neo4j.py --from-url "https://www.puc-campinas.edu.br/" --to-url "URL_REAL_DO_DESTINO"
```

O comando `--schema` retorna nomes de propriedades e relações, sem despejar HTML.
Nenhum desses comandos inicia FastAPI, Redis ou LLM.

## Chat e especialista

```json
{
  "search": "O que tem no curso de Sistemas de Informação e como chego até a página?",
  "url": "https://www.puc-campinas.edu.br/"
}
```

Envie a URL atualizada a cada chamada `POST /llm/chat`. `url` é opcional para
manter clientes anteriores compatíveis. `chat_id` continua opcional para iniciar
ou retomar conversas. A resposta mantém `chat_id`, `query` e `response`.
A URL também é armazenada na mensagem do usuário no Redis.

O coordenador passa a pergunta, a localização e o histórico ao único especialista
institucional (`rag_agent`), sem substituir a pergunta original pelos argumentos
reformulados pela LLM. Ele faz a recuperação inicial dos PDFs e coloca os
trechos no prompt da pergunta atual. `search_documents` permite refinar a busca;
`search_site_pages`, `read_site_page`, `get_page_links` e `find_site_path` consultam
o grafo quando o especialista decidir que precisa delas. As consultas adicionais
continuam sob decisão do especialista, sem delegar a outro agente.

As credenciais não selecionam um agente diferente. Se o especialista escolher
Neo4j sem configuração ou conexão válida, a ferramenta informa a falha. Perguntas
sobre PDFs podem ser respondidas sem nenhuma consulta ao grafo. A URL atual é
contexto, não uma ordem para usar Neo4j. Não há consulta automática de reserva ao
grafo. A resposta final gerada pela LLM é devolvida sem filtros de conteúdo,
checagem de URLs, exigência de consulta, limpeza de citações ou substituição por
trechos dos documentos. O executor mantém a interpretação de chamadas de
ferramentas, a validação de seus argumentos e o limite de execuções.
O coordenador também produz sua resposta final após consultar o especialista,
sem atalhos de retorno direto ou substituição automática de sua resposta.

`diagnose_rag` permanece como diagnóstico isolado do processamento de PDFs; não
é chamado por outro agente no fluxo principal do chat.

A ferramenta `search_documents` é criada por
`Services/tools/document_tools.py`, com fontes e resultados isolados por execução.
Os prompts ficam em `Backend/Agents/prompts`, nos arquivos `coordinatorAgent_prompt.py`,
`ragAgent_prompt.py` e `ragAgent_diagnostic_prompt.py`. As instruções compartilhadas
do executor de ferramentas ficam em `specialist_agent_prompt.py`.

Os prompts orientam a produzir linguagem adequada para leitura em voz alta,
sem referências bibliográficas. Essa orientação não é imposta por filtros após
a geração: se a LLM produzir citações ou links, o texto não é alterado pelo backend.

O especialista distingue um link direto de um caminho confirmado no grafo. Não
encontrar um caminho limitado não prova que não exista outro caminho no site.
O conteúdo é uma captura salva no grafo, não o DOM atual da extensão: telas após
login, formulários, estados dinâmicos e alterações posteriores podem divergir.
Scripts, estilos e templates são removidos na extração de texto do HTML.
O backend não abre páginas nem executa JavaScript do site.

## Verificação

```powershell
python -m unittest discover -s tests -v
```

Os testes usam driver e LLM simulados. Para validar conexão, esquema e resultados
do banco real, use `inspect_neo4j.py` com as credenciais e o esquema corretos.
