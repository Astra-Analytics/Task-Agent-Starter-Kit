import logging
import threading
from typing import Any, Dict, Iterator, List, Mapping, Union

import ollama
from ollama import Message

logger = logging.getLogger(__name__)

# Initialize a lock
print_lock = threading.Lock()


def get_ollama_embedding(text):
    text = text.replace("\n", " ")
    response = ollama.embeddings(model="mxbai-embed-large", prompt=text)
    return response["embedding"]


def handle_response(
    response: Union[Dict[str, Any], Iterator[Mapping[str, Any]]], stream: bool = False
) -> str:
    if isinstance(response, dict) and "response" in response:
        return response["response"].strip()
    elif stream:
        ai_response = ""
        try:
            with print_lock:  # Acquire the lock
                for chunk in response:
                    if isinstance(chunk, Mapping) and "message" in chunk:
                        message = chunk["message"]
                        if isinstance(message, Mapping) and "content" in message:
                            print(message["content"], end="", flush=True)
                            ai_response += message["content"]
                        elif isinstance(message, str):
                            print(message, end="", flush=True)
                            ai_response += message
                        else:
                            raise Exception("Invalid chunk structure")
                    elif isinstance(chunk, Mapping) and "response" in chunk:
                        print(chunk["response"], end="", flush=True)
                        ai_response += chunk["response"]
                    else:
                        raise Exception("Invalid chunk structure")
            return ai_response
        except Exception as e:
            raise Exception(f"No 'response' found in the API response: {e}")
    else:
        raise Exception(f"Unexpected response structure: {response}")


def ollama_generate(model: str, prompt: str, stream: bool = False) -> str:
    response = ollama.generate(model=model, prompt=prompt, stream=stream)
    if isinstance(response, (dict, Iterator)):
        return handle_response(response, stream=stream)
    else:
        raise TypeError("Invalid response type")


def ollama_chat(model: str, messages: List[Message], stream: bool = False) -> str:
    response = ollama.chat(model=model, messages=messages, stream=stream)
    if isinstance(response, (dict, Iterator)):
        return handle_response(response, stream=stream)
    else:
        raise TypeError("Invalid response type")
