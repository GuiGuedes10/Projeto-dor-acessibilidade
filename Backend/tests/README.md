# Memória de conversa

A rota `POST /llm/chat` usa Redis. Configure `SECRET_KEY`, `HOST` (ou
`REDIS_HOST`), `REDIS_PORT` e `REDIS_DB` no `Backend/.env`.
`REDIS_URL` pode substituir os parâmetros de conexão. `REDIS_PASSWORD`
é opcional quando não se usa URL. Mantenha `SECRET_KEY` estável e fora do Git.

## Iniciar uma conversa

```json
{"search": "A SBI possui livros em Braille?"}
```

Exemplo de resposta (o texto depende do modelo):

```json
{
  "chat_id": "59e2b4b1-89ec-4fb6-b897-24cd93276613",
  "query": "A SBI possui livros em Braille?",
  "response": "Resposta do assistente"
}
```

## Continuar a mesma conversa

Envie o `chat_id` recebido, sem gerar outro no frontend:

```json
{
  "chat_id": "59e2b4b1-89ec-4fb6-b897-24cd93276613",
  "search": "E quais outros recursos estão disponíveis?"
}
```

Sem `chat_id`, cada requisição inicia uma conversa nova. O identificador é UUID;
não exige contador global. Um chat desconhecido ou de outro identificador de
usuário retorna 404. Requisições concorrentes com histórico desatualizado recebem
409 e devem ser reenviadas. Redis indisponível retorna 503, sem afirmar que a
interação foi salva.

## Armazenamento e contexto

### Listagem para o frontend

`GET /llm/chats` não precisa de corpo, `user_id` ou `chat_id`. O servidor calcula
o mesmo HMAC do IP e retorna apenas os chats desse identificador:

```json
[
  {
    "chat_id": "59e2b4b1-89ec-4fb6-b897-24cd93276613",
    "last_question": "E quais outros recursos estão disponíveis?"
  }
]
```

Sem conversas, retorna `[]`. Conversas vazias (sem interação salva) não aparecem.
A rota não chama a LLM nem cria conversas. A busca usa SCAN, inclui as conversas
anteriores à criação da rota e lê somente o último turno de cada chat do usuário.

### Recuperar uma conversa completa

`GET /llm/chats/{chat_id}` retorna as mensagens em ordem de gravação:

```json
{
  "chat_id": "59e2b4b1-89ec-4fb6-b897-24cd93276613",
  "messages": [
    {"role": "user", "content": "A SBI possui livros em Braille?"},
    {"role": "assistant", "content": "Resposta do assistente"}
  ]
}
```

O hash do IP é recalculado no servidor. Um ID inválido recebe 422; conversa
inexistente ou de outro identificador recebe 404. Uma conversa existente sem
mensagens retorna `messages: []`. A URL da mensagem é incluída quando foi salva.
A leitura retorna todo o histórico, sem o limite de 20 mensagens usado no prompt,
e não chama a LLM nem grava dados.

### Formato das mensagens armazenadas

- `chat:{UUID}:user_id`: HMAC-SHA256 do IP, usando o service de hash.
- `chat:{UUID}:messages`: lista de JSONs com `role` e `content`.
- Cada turno adiciona `user` e `assistant` juntos em uma transação.
- O Redis conserva o histórico completo. O prompt usa no máximo as últimas
  20 mensagens (10 turnos), limitadas a 2.000 caracteres por mensagem.
- Histórico não é prova factual para o RAG; ele continua usando os documentos.
- Não foi definido TTL. A sobrevivência a reinícios depende da persistência
  configurada no servidor Redis (RDB/AOF).

O HMAC é um hash, não uma criptografia reversível. IP não equivale a uma conta:
pessoas que compartilham IP compartilham esse identificador; mudar de IP ou de
`SECRET_KEY` impede retomar chats anteriores. O frontend precisa conhecer o UUID
para retomar o chat. Não confie em cabeçalhos de proxy enviados livremente pelo
cliente; configure apenas proxies conhecidos na implantação.

## Testes (a partir de Backend)

```powershell
python -m unittest discover -s tests -v
python tests/test_redisBd.py
python tests/test_redisBd.py --exercise
```

O primeiro comando usa simulações para Redis e geração. O segundo envia PING.
O terceiro cria uma conversa temporária no Redis real, verifica gravação,
retomada, isolamento e conflito, e apaga somente as chaves que criou.

## Diagnóstico do especialista

```powershell
python tests/diagnose_specialist.py --query "Como funciona a area logada da puc-campinas?" --fixture tests/fixtures/area_logada.json --output tests/area_logada_diagnostic_result.json
```

Esse comando usa a LLM real e os trechos fornecidos no teste, sem iniciar a API
nem escrever no Redis. O relatório mostra a pergunta, as gerações e as chamadas
de ferramentas. Sem `--fixture`, usa a busca real da ORM e o Neo4j configurado.
A recuperação inicial dos PDFs ocorre antes da geração. A resposta é preservada
conforme gerada, inclusive recusas, links e citações. Não há substituição automática
por trechos literais nem filtros de conteúdo após a geração.
