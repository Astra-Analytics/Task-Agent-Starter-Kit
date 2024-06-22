import ollama


def entity_extraction_agent(text_input):
    response = ollama.generate(
        model="llama3",
        prompt=text_input,
        # raw=True,
        stream=True,
    )

    if isinstance(response, dict) and "response" in response:
        response_text = response["response"]
        return response_text
    else:
        try:
            for chunk in response:
                if isinstance(chunk, dict):
                    print(chunk["response"], end="", flush=True)
            return "done"
        except Exception as e:
            raise Exception(f"No 'response' found in the API response: {e}")


response = entity_extraction_agent(".")
print(response)
