import json
import logging
from typing import List

from ollama import Message
from typeid import TypeID

from utils.ollama import ollama_chat, ollama_generate

from .storage import SingleTaskListStorage

logger = logging.getLogger(__name__)

storage = SingleTaskListStorage()


def objective_agent(to, from_email, subject, timestamp, body, attachments):
    prompt = f"""
You are an AI assistant that processes emails. You have received an email with the following details:
To: {to}
From: {from_email}
Subject: {subject}
Timestamp: {timestamp}
Body: {body}
Attachments: {attachments}
Your task is to determine if the email contains any actionable tasks for the recipient. An actionable task should be a specific request or instruction that requires the recipient to take some action. If there are actionable tasks, list each one as a separate item. If there are no actionable tasks, respond with "No tasks found."
RETURN ONLY THIS STRING AND DO NOT INCLUDE ANY OTHER OUTPUT.
"""
    response_text = ollama_generate(model="llama3", prompt=prompt, stream=True)
    if response_text == "No tasks found." or not response_text:
        return {"tasks_found": False, "tasks": []}
    else:
        tasks = response_text.split("\n")
        task_list = [{"name": task.strip()} for task in tasks if task.strip()]
        return {
            "tasks_found": True,
            "tasks": task_list,
        }


def task_creation_agent(task_name, previous_results):
    prompt = f"""You are a task creation AI tasked with creating a list of tasks as a JSON array, considering the ultimate objective of your team: {task_name}.
The result of the previous task(s) are as follows: {previous_results}
If the sub-tasks are dependent, dependencies should be lower on the list (i.e., execution should be bottom-up).
Be sure to specify if the sub-task can be completed by an AI assistant or requires human intervention by specifying agent = 'AI' or 'Human'.
Return the sub-tasks as a structured list of dictionaries with the following format:
[{{"task": str, "agent": str}}, {{"task": str, "agent": str}}, ...]
SHARE ONLY THIS LIST - DO NOT INCLUDE ANYTHING ELSE IN THE RESPONSE.
"""
    response_text = ollama_generate(model="llama3", prompt=prompt, stream=True)
    logger.debug(f"Task creation agent response: {response_text}")
    try:
        new_tasks_list = eval(response_text.strip())
    except (SyntaxError, ValueError):
        logger.error(f"Failed to parse task creation agent response: {response_text}")
        new_tasks_list = None

    return new_tasks_list


def entity_extraction_agent(text_input):
    prompt = [
        Message(
            role="system",
            content="""You are an AI expert specializing in entity identification and list creation, with the goal of capturing relationships based on a given input or request.
You are given input in various forms such as paragraph, email, text files, and more.
Your task is to create a entities list based on the input.
Only use organizations, people, and projects as entities and do not include concepts or products.
Organization entities can have attributes: name, type, description, member, memberOf.
Person entities can have attributes: name, type, description, memberOf, parent, sibling, spouse, children, colleague, relatedTo, worksFor.
Project entities can have attributes: name, type, description, department, member, memberOf.
Only add nodes that have a relationship with at least one other node.
Make sure that the node type (people, org, event) matches the to_type or for_type when the entity is part of a relationship.
Return the entities list as a valid JSON object. NEVER INCLUDE COMMENTS THEY ARE NOT VALID JSON. DO NOT INCLUDE ANYTHING ELSE IN THE RESPONSE.""",
        ),
        Message(
            role="user",
            content="Can you please help John Smith from IT get access to the system? He needs it as part of the IT Modernization effort.",
        ),
        Message(
            role="assistant",
            content="""{
    "entities": [
        {
            "name": "Modernization of the IT infrastructure",
            "type": "Project",
            "description": "A project to modernize the IT infrastructure of the company.",
            "department": "IT",
        },
        {
            "name": "John Smith",
            "type": "Person",
            "description": "Employee in the IT department."
            "memberOf": "IT",
        },
        {
            "name": "IT",
            "type": "Organization",
            "description": "The IT department of the company.",
            "member": "John Smith",
        },
    ]
}
""",
        ),
        Message(role="user", content=text_input),
    ]
    response_text = ollama_chat(model="llama3", messages=prompt, stream=True)
    return response_text


def conditional_entity_addition(data):
    entities = data.get("entities", [])
    updated_entities = []

    for entity in entities:
        entity_type = entity.get("type")
        entity_name = entity.get("name")

        if not entity_type or not entity_name:
            logger.warning(f"Entity is missing type or name: {entity}")
            continue

        # Look up existing entities by name
        condition_str = f"str_includes('name', '{entity_name}')"
        search_results = storage.lookup(
            entity_type,
            ["uuid", "name", "description"],
            condition=condition_str,
        )
        search_results = json.loads(search_results)

        # Check if the entity exists
        if search_results["rows"]:
            combined_results = {
                result[0]: {
                    "uuid": result[0],
                    "name": result[1],
                    "description": result[2],
                }
                for result in search_results["rows"]
            }
            combined_results_str = ", ".join(
                json.dumps(result) for result in combined_results.values()
            )

            prompt: List[Message] = [
                Message(
                    role="system",
                    content="You are a helpful assistant who's specialty is to decide if new input data matches data already in our database. Review the search results provided, compare against the input data, and if there's a match respond with the ID number of the match, and only the ID number. If there are no matches, respond with 'No Matches'. Your response is ALWAYS an ID number alone, or 'No Matches'. When reviewing whether a match existings in our search results to our new input, take into account that the name may not match perfectly (for example, one might have just a first name, or a nick name, while the other has a full name), in which case look at the additional information about the user to determine if there's a strong likelihood they are the same person. For companies, you should consider different names of the same company as the same, such as EA and Electronic Arts (make your best guess). If the likelihood is strong, respond with and only with the ID number. If likelihood is low, respond with 'No Matches'.",
                ),
                Message(
                    role="user",
                    content=f"Here are the search results: {combined_results_str}. Does any entry match the input data: {data}?",
                ),
            ]

            response_text = ollama_chat(model="llama3", messages=prompt, stream=True)
            if response_text.lower() == "no matches":
                entity_id = str(TypeID(prefix=entity_type.lower()))
                logger.info(f"Creating new entity: {entity_name}, ID: {entity_id}")
            else:
                entity_id = response_text.strip()
                logger.info(f"Found existing entity: {entity_name}, ID: {entity_id}")

        else:
            entity_id = str(TypeID(prefix=entity_type.lower()))
            logger.info(f"Creating new entity: {entity_name}, ID: {entity_id}")

        entity["uuid"] = entity_id
        updated_entities.append(entity)

    # Replace references in entities with the appropriate UUIDs
    uuid_map = {entity["name"]: entity["uuid"] for entity in updated_entities}

    for entity in updated_entities:
        for key, value in entity.items():
            if isinstance(value, str) and value in uuid_map:
                entity[key] = uuid_map[value]

    return {"entities": updated_entities}, 200
