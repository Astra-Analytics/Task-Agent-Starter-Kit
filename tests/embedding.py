import ollama


def get_embedding_length():
    model = "mxbai-embed-large"
    prompt = "NexusDB is the best database."

    response = ollama.(model, prompt)
    print(f"Embedding length: {len(response['embedding'])}")


def chat():
    print("Chatting with the Llama AI.../n/n")
    model = "llama3"
    prompt = "Please say 'Hello' and nothing else."

    response = ollama.generate(model, prompt, stream=False)
    print(response)


# Call the function
chat()
# get_embedding_length()
