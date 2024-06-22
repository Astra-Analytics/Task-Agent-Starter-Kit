import json
import os
import re
import time
from collections import deque
from typing import Dict, List

import ollama
from dotenv import load_dotenv

from other.nexusdb import NexusDB

# Email data
email_data = [
    {
        "Body": '<html><head></head><body><p class="greeting"> Hello, </p> <p>Please write a haiku about golf. If you have any questions, please email me at <a aria-haspopup="menu" class="c-link c-link--underline" data-sk="tooltip_parent" data-stringify-link="mailto:john.doe@example.com" href="mailto:john.doe@example.com" rel="noopener noreferrer" target="_blank">john.doe@example.com</a>.</p> <p> Thank you,<br> John Doe </p>\r\n</body></html>\r\n',
        "From": "John Doe <john.doe@example.com>",
        "Message-ID": "01j0r9h83tfjyrjj8trk7zxe6v",
        "Subject": "Haiku about golf",
        "Timestamp": "Tue, 14 May 2024 19:14:56 +0000",
        "To": "test@gmail.com",
    }
]


# Task storage supporting only a single instance of BabyAGI
class SingleTaskListStorage:
    def __init__(self):
        self.tasks = deque([])
        self.task_id_counter = 0

    def append(self, task: Dict):
        self.tasks.append(task)

    def replace(self, tasks: List[Dict]):
        self.tasks = deque(tasks)

    def popleft(self):
        return self.tasks.popleft()

    def is_empty(self):
        return False if self.tasks else True

    def next_task_id(self):
        self.task_id_counter += 1
        return self.task_id_counter

    def get_task_names(self):
        return [t["task_name"] for t in self.tasks]


# Initialize tasks storage
tasks_storage = SingleTaskListStorage()


def get_ollama_embedding(text):
    text = text.replace("\n", " ")
    response = ollama.(model="mxbai-embed-large", prompt=text)
    return response["embedding"]


def task_creation_agent(
    objective: str, result: Dict, task_description: str, task_list: List[str]
):
    prompt = f"""
You are to use the result from an execution agent to create new tasks with the following objective: {objective}.
The last completed task has the result: \n{result["data"]}
This result was based on this task description: {task_description}.\n"""

    if task_list:
        prompt += f"These are incomplete tasks: {', '.join(task_list)}\n"
    prompt += "Based on the result, return a list of tasks to be completed in order to meet the objective. "
    if task_list:
        prompt += "These new tasks must not overlap with incomplete tasks. "

    prompt += """
Return one task per line in your response. The result must be a numbered list in the format:

#. First task
#. Second task

The number of each entry must be followed by a period. If your list is empty, write "There are no tasks to add at this time."
Unless your list is empty, do not include any headers before your numbered list or follow your numbered list with any other output."""

    print(f"\n*****TASK CREATION AGENT PROMPT****\n{prompt}\n")
    response = ollama.generate(
        model="llama3",
        prompt=prompt,
    )

    if isinstance(response, dict):
        if "response" in response:
            response_text = response["response"]
            print(f"\n****TASK CREATION AGENT RESPONSE****\n{response_text}\n")
            new_tasks = response_text.split("\n")
            new_tasks_list = []
            for task_string in new_tasks:
                task_parts = task_string.strip().split(".", 1)
                if len(task_parts) == 2:
                    task_id = "".join(s for s in task_parts[0] if s.isnumeric())
                    task_name = re.sub(r"[^\w\s_]+", "", task_parts[1]).strip()
                    if task_name.strip() and task_id.isnumeric():
                        new_tasks_list.append(task_name)
            out = [{"task_name": task_name} for task_name in new_tasks_list]
            return out
        else:
            raise Exception("No 'response' found in the API response")
    else:
        raise Exception("Response is not a dictionary")


def prioritization_agent():
    task_names = tasks_storage.get_task_names()
    bullet_string = "\n"

    prompt = f"""
You are tasked with prioritizing the following tasks: {bullet_string + bullet_string.join(task_names)}
Consider the ultimate objective of your team: {OBJECTIVE}.
Tasks should be sorted from highest to lowest priority, where higher-priority tasks are those that act as pre-requisites or are more essential for meeting the objective.
Do not remove any tasks. Return the ranked tasks as a numbered list in the format:

#. First task
#. Second task

The entries must be consecutively numbered, starting with 1. The number of each entry must be followed by a period.
Do not include any headers before your ranked list or follow your list with any other output."""

    print(f"\n****TASK PRIORITIZATION AGENT PROMPT****\n{prompt}\n")
    response = ollama.generate(
        model="llama3",
        prompt=prompt,
    )

    if isinstance(response, dict):
        if "response" in response:
            response_text = response["response"]
            new_tasks = response_text.strip().split("\n")
        else:
            raise Exception(f"Unexpected response structure: {response}")
    else:
        raise Exception("Response is not a dictionary")
    print(f"\n****TASK PRIORITIZATION AGENT RESPONSE****\n{response}\n")
    if not response:
        print(
            "Received empty response from prioritization agent. Keeping task list unchanged."
        )
        return
    new_tasks = response_text.split("\n") if "\n" in response_text else [response_text]
    new_tasks_list = []
    for task_string in new_tasks:
        task_parts = task_string.strip().split(".", 1)
        if len(task_parts) == 2:
            task_id = "".join(s for s in task_parts[0] if s.isnumeric())
            task_name = re.sub(r"[^\w\s_]+", "", task_parts[1]).strip()
            if task_name.strip():
                new_tasks_list.append({"task_id": task_id, "task_name": task_name})

    return new_tasks_list


def execution_agent(db, objective: str, task: str) -> str:
    context = context_agent(db, query=objective, top_results_num=5)
    prompt = f"Perform one task based on the following objective: {objective}.\n"
    if context:
        prompt += "Take into account these previously completed tasks:" + "\n".join(
            context
        )
    prompt += f"\nYour task: {task}\nResponse:"
    response = ollama.generate(
        model="llama3",
        prompt=f"You are an AI who performs one task based on the following objective: {objective}. Your task: {task}\nResponse:",
        stream=False,
    )

    if isinstance(response, dict):
        if "response" in response:
            response_text = response["response"]
            new_tasks = response_text.strip().split("\n")
            return [{"task_name": task_name} for task_name in new_tasks]
        else:
            raise Exception(f"Unexpected response structure: {response}")
    else:
        raise Exception("Response is not a dictionary")


def context_agent(db, query: str, top_results_num: int):
    query_embedding = get_ollama_embedding(query)
    results = db.vector_search(
        query_vector=query_embedding, number_of_results=top_results_num
    )
    results = json.loads(results)
    print(f"\n\nContext search results:\n{results}\n\n")
    return [row[1].strip('"') for row in results.get("rows", [])]


def store_results(db, task: Dict, result: str, result_id: str):
    vector = get_ollama_embedding(result)
    db.insert_with_vector(
        relation_name="tasks",
        task_id=result_id,
        text=result,
        embeddings=vector,
        metadata={"task": task["task_name"], "result": result},
    )


def objective_agent(to, from_email, subject, timestamp, body, attachments):
    prompt = f"""
You are an AI assistant that processes emails. You have received an email with the following details: 
To: {to}, From: {from_email}, Subject: {subject}, Timestamp: {timestamp}, Body: {body}, Attachments: {attachments}. 
Based on this information, determine if the email contains any tasks for the recipient, if any, and return it as a string.
If you don't believe there are any tasks, return the string, "No tasks found." Do not include quotes. RETURN ONLY THIS STRING AND DO NOT INCLUDE ANY OTHER OUTPUT.
"""

    print(prompt)
    response = ollama.generate(
        model="llama3",
        prompt=prompt,
    )

    # Print the full response for debugging
    print(f"Full response: {response}")

    if isinstance(response, dict):
        if "response" in response:
            response_text = response["response"].strip()
            if response_text == "No tasks found." or not response_text:
                return {"tasks_found": False, "tasks": []}
            else:
                new_tasks = response_text.split("\n")
                return {
                    "tasks_found": True,
                    "tasks": [{"task_name": task_name} for task_name in new_tasks],
                }
        else:
            raise Exception(f"Unexpected response structure: {response}")
    else:
        raise Exception("Response is not a dictionary")


def main():
    # Load environment variables from .env file
    load_dotenv()

    # Extract email information
    email = email_data[0]
    to = email["To"]
    from_email = email["From"]
    subject = email["Subject"]
    timestamp = email["Timestamp"]
    body = email["Body"]
    attachments = ""  # Assuming no attachments for simplicity

    # Determine the objective dynamically
    objective_response = objective_agent(
        to, from_email, subject, timestamp, body, attachments
    )

    if not objective_response["tasks_found"]:
        print("No tasks identified in the email. Exiting.")
        return

    # Set the first task as the objective
    OBJECTIVE = objective_response["tasks"][0]["task_name"]
    print("\033[96m\033[1m" + "\n*****OBJECTIVE*****\n" + "\033[0m\033[0m")
    print(OBJECTIVE)

    # Initialize NexusDB
    db = NexusDB()

    JOIN_EXISTING_OBJECTIVE = False

    # Add the initial task if starting new objective
    if not JOIN_EXISTING_OBJECTIVE:
        initial_task = {
            "task_id": tasks_storage.next_task_id(),
            "task_name": "Develop a task list.",
        }
        tasks_storage.append(initial_task)

    # Main loop
    loop = True
    while loop:
        if not tasks_storage.is_empty():
            print("\033[95m\033[1m" + "\n*****TASK LIST*****\n" + "\033[0m\033[0m")
            for t in tasks_storage.get_task_names():
                print(" • " + str(t))

            task = tasks_storage.popleft()
            print("\033[92m\033[1m" + "\n*****NEXT TASK*****\n" + "\033[0m\033[0m")
            print(str(task["task_name"]))

            result = execution_agent(db, OBJECTIVE, str(task["task_name"]))
            print("\033[93m\033[1m" + "\n*****TASK RESULT*****\n" + "\033[0m\033[0m")
            print(result)

            enriched_result = {"data": result}
            result_id = f"result_{task['task_id']}"

            store_results(db, task, result, result_id)

            new_tasks = task_creation_agent(
                OBJECTIVE,
                enriched_result,
                task["task_name"],
                tasks_storage.get_task_names(),
            )

            print("Adding new tasks to task_storage")
            for new_task in new_tasks:
                new_task.update({"task_id": tasks_storage.next_task_id()})
                print(str(new_task))
                tasks_storage.append(new_task)

            if not JOIN_EXISTING_OBJECTIVE:
                prioritized_tasks = prioritization_agent()
                if prioritized_tasks:
                    tasks_storage.replace(prioritized_tasks)

            time.sleep(5)
        else:
            print("Done.")
            loop = False


if __name__ == "__main__":
    main()
