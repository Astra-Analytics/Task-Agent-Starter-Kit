import ollama


def entity_extraction_agent(text_input):
    prompt = [
        {
            "role": "system",
            "content": """You are an AI expert specializing in knowledge graph creation with the goal of capturing relationships based on a given input or request.
You are given input in various forms such as paragraph, email, text files, and more.
Your task is to create a knowledge graph based on the input.
Only use organizations, people, and events as nodes and do not include concepts or products.
Only add nodes that have a relationship with at least one other node.
Make sure that the node type (people, org, event) matches the to_type or for_type when the entity is part of a relationship.
Return the knowledge graph as a JSON object. DO NOT INCLUDE ANYTHING ELSE IN THE RESPONSE.""",
        },
        {
            "role": "user",
            "content": "Can you please help John Smith from IT get access to the system? He needs it as part of the IT Modernization effort.",
        },
        {
            "role": "assistant",
            "content": '{"entities": [{"name": "Modernization of the IT infrastructure", "type": "Project", "description": "A project to modernize the IT infrastructure of the company.", "department": "IT",},{"name": "Person A", "type": "Person", "memberOf": "IT",},{"name": "IT", "type": "Organization", "description": "The IT department of the company.", "member": "Person A",},]}',
        },
        {"role": "user", "content": text_input},
    ]

    response = ollama.chat(
        model="llama3",
        messages=prompt,
        stream=True,
    )

    if isinstance(response, dict) and "response" in response:
        response_text = response["response"]
        return response_text
    else:
        try:
            for chunk in response:
                if isinstance(chunk, dict):
                    if (
                        "message" in chunk
                        and isinstance(chunk["message"], dict)
                        and "content" in chunk["message"]
                    ):
                        print(chunk["message"]["content"], end="", flush=True)
                    else:
                        raise Exception("Invalid chunk structure")
            return "done"
        except Exception as e:
            raise Exception(f"No 'response' found in the API response: {e}")


response = entity_extraction_agent(
    "Adam from team A will be able to help answer any questions."
)
print(response)
