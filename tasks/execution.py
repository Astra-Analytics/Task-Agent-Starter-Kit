import logging

from utils.ollama import ollama_generate

logger = logging.getLogger(__name__)


def execution_agent(task_name: str, previous_results: list, context: list) -> str:
    try:
        prompt = f"""
Perform the following task: {task_name}.
Take into account these previously completed tasks and their results: {previous_results}.
Additionally, consider these similar tasks and their contexts: {context}.
If you can complete the task based on the context provided, execute it and respond with the result. 
If more context is needed, respond with "More context needed" - DO NOT SAY ANYTHING ELSE.
Response:
"""
        response_text = ollama_generate(model="llama3", prompt=prompt, stream=True)
        return response_text
    except Exception as e:
        logger.error(f"Error in execution_agent: {e}")
        raise
