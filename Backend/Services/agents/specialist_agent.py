import json
import re
import torch


def generate_response(llm, prompt: str, tools: list, max_iterations: int = 3):

    model = llm["model"]
    tokenizer = llm["tokenizer"]

    tool_map = {
        tool.__name__: tool
        for tool in tools
    }

    messages = [
        {"role": "user", "content": prompt}
    ]

    for _ in range(max_iterations + 1):

        text = tokenizer.apply_chat_template(
            messages,
            tools=tools,
            tokenize=False,
            add_generation_prompt=True
        )

        inputs = tokenizer(
            text,
            return_tensors="pt"
        ).to(model.device)

        with torch.inference_mode():
            outputs = model.generate(
                **inputs,
                max_new_tokens=512,
                do_sample=False
            )

        generated = outputs[0][inputs["input_ids"].shape[-1]:]

        response = tokenizer.decode(
            generated,
            skip_special_tokens=False
        )

        matches = re.findall(
            r"<tool_call>\s*(.*?)\s*</tool_call>",
            response,
            re.DOTALL
        )

        if not matches:
            return re.sub(r"<\|im_end\|>$", "", response).strip()

        tool_calls = []

        for match in matches:
            function = json.loads(match)

            tool_calls.append({
                "type": "function",
                "function": function
            })

        messages.append({
            "role": "assistant",
            "content": "",
            "tool_calls": tool_calls
        })

        for tool_call in tool_calls:

            function = tool_call["function"]
            name = function["name"]
            arguments = function["arguments"]

            if name not in tool_map:
                result = "Ferramenta não disponível para este agente."
            else:
                try:
                    result = tool_map[name](**arguments)
                except Exception as error:
                    result = f"Erro ao executar ferramenta: {error}"

            messages.append({
                "role": "tool",
                "name": name,
                "content": str(result)
            })

    return "Limite de chamadas de ferramentas atingido."