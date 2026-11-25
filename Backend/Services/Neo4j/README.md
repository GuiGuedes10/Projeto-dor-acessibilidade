# Mapa do site parceiro

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

O coordenador passa a localização ao especialista. Com as credenciais `NEO4J_*`
configuradas, o especialista recebe as ferramentas `search_site_pages`,
`read_site_page`, `get_page_links` e `find_site_path`, além de `consult_documents`
para os PDFs. Sem configuração Neo4j, o RAG de documentos continua funcionando.
Existe consulta de reserva ao grafo se o modelo ignorar chamadas de ferramentas.

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
