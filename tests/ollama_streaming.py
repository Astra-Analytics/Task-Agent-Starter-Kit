import threading
from typing import List

from ollama import Message

from utils.ollama import ollama_chat

# Dummy Messages for Testing
messages: List[Message] = [
    Message(role="user", content="Hello, how are you?"),
    Message(role="user", content="What is the weather like today?"),
    Message(role="user", content="Tell me a joke."),
    Message(role="user", content="What's the capital of France?"),
    Message(role="user", content="What's the latest news?"),
]

# Dummy model name
model = "llama3"

# Define the number of threads
num_threads = len(messages)


# Test function to run in threads
def test_ollama_chat(thread_id: int, message: Message):
    print(f"Thread-{thread_id} starting with message: {message}")
    response = ollama_chat(model=model, messages=[message], stream=True)
    print(f"\nThread-{thread_id} received response:\n{response}\n")


# Create and start threads
threads = []
for i in range(num_threads):
    thread = threading.Thread(target=test_ollama_chat, args=(i, messages[i]))
    threads.append(thread)
    thread.start()

# Wait for all threads to complete
for thread in threads:
    thread.join()

print("All threads completed.")
