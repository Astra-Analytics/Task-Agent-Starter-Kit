import ast
import json
import logging
from re import S
from typing import Dict, List

from nexus_python.nexusdb import NexusDB
from typeid import TypeID

from utils.ollama import get_ollama_embedding

logger = logging.getLogger(__name__)


class SingleTaskListStorage(NexusDB):
    def __init__(self):
        super().__init__()

    def append(self, task: Dict):
        logger.debug(f"Appending task: {task}")
        if "uuid" not in task or not task["uuid"]:
            task_id = str(TypeID(prefix="action"))
            task["uuid"] = task_id
        task["actionStatus"] = "Active"
        if "potentialAction" not in task:
            task["potentialAction"] = None
        fields = list(task.keys())
        values = [list(task.values())]
        self.insert("Action", fields, values)

    def next_task_id(self):
        return str(TypeID(prefix="action"))

    def get_tasks(self, object=None, condition=None):
        conditions = self.prepare_conditions(object, condition)
        return self.fetch_tasks(conditions)

    def prepare_conditions(self, object, condition):
        conditions = [condition] if condition else []

        if object:
            conditions.extend(self.get_conditions_for_object(object))

        return " , ".join(conditions) if conditions else ""

    def get_conditions_for_object(self, object):
        objective_ids = self.get_objective_ids(object)
        logger.debug(f"Objective IDs: {objective_ids}\n\n\n")
        if objective_ids == [] or not objective_ids:
            return [f"object = '{object}'"]

        try:
            related_uuids = self.get_related_uuids(objective_ids[0])
            if related_uuids:
                uuid_list = ", ".join([f"'{uuid}'" for uuid in related_uuids])
                return [f"is_in('uuid', [{uuid_list}])"]
            else:
                return [f"uuid = '{objective_ids[0]}'"]
        except Exception as e:
            logger.error(f"Error executing recursive query: {e}")
            return []

    def get_objective_ids(self, object=None):
        if object:
            objective = self.lookup(
                "Action", condition=f"object = '{object}', identifier = 0"
            )
            logger.debug(f"Objective: {objective}\n\n\n")
        else:
            objective = self.lookup("Action", condition="identifier = 0")
            logger.debug(f"Objective: {objective}")
        return [row[0] for row in json.loads(objective)["rows"]]

    def get_related_uuids(self, objective_id):
        result = self.recursive_query(
            relation_name="Graph",
            source_field="sourceId",
            target_field="targetId",
            starting_condition=f"targetId = '{objective_id}'",
        )
        return [row[0] for row in json.loads(result)["rows"]]

    def fetch_tasks(self, condition_str):
        fields = [
            "name",
            "uuid",
            "object",
            "identifier",
            "actionStatus",
            "agent",
            "potentialAction",
        ]
        if condition_str:
            tasks = self.lookup("Action", fields, condition=condition_str)
        else:
            tasks = self.lookup("Action", fields)

        return self.process_tasks(json.loads(tasks))

    def process_tasks(self, tasks):

        logger.debug(f"Processing Tasks from lookup: {tasks}\n\n")

        # Create a dictionary to map UUIDs to task names
        uuid_to_name = {}

        # First pass: Collect UUIDs and their corresponding task names
        for task in tasks["rows"]:
            uuid = task[1]
            name = task[0]
            uuid_to_name[uuid] = name

        # Second pass: Construct task data with potentialAction names
        task_data = {}
        for task in tasks["rows"]:
            uuid = task[1]

            potential_actions = None
            if task[6] != "Null":
                try:
                    potential_actions = task[6]

                    action_names = [
                        uuid_to_name.get(action, action) for action in potential_actions
                    ]

                except (TypeError, KeyError) as e:
                    logger.error(f"Error parsing potentialAction for task {uuid}: {e}")
                    potential_actions = task[6]

            task_data[uuid] = {
                "name": task[0],
                "uuid": uuid,
                "object": task[2],
                "identifier": task[3],
                "actionStatus": task[4],
                "agent": task[5],
                "potentialAction": action_names if potential_actions else None,
            }

        logger.debug(f"Tasks: {task_data}")
        return task_data

    def add_subtasks(
        self,
        current_task_id: str,
        current_task_name: str,
        potential_actions: List[Dict[str, str]] | None,
        max_identifier: int,
    ):
        current_identifier = max_identifier + 1
        subtasks = []
        task_data = {}

        if not potential_actions or potential_actions == []:
            return current_identifier, task_data

        for action in potential_actions:
            current_identifier += 1
            task_id = self.next_task_id()
            self.upsert(
                "Action",
                ["uuid", "name", "actionStatus", "identifier", "object", "agent"],
                [
                    [
                        task_id,
                        action["task"],
                        "Active",
                        current_identifier,
                        current_task_id,
                        action.get("agent", "Human"),
                    ]
                ],
            )

            subtasks.append(task_id)

            task_data[task_id] = {
                "name": action["task"],
                "uuid": task_id,
                "object": current_task_id,
                "identifier": current_identifier,
                "actionStatus": "Active",
                "agent": action.get("agent", "Human"),
            }

        self.update(
            "Action",
            ["uuid", "name", "potentialAction"],
            [[current_task_id, current_task_name, subtasks]],
        )
        logger.debug(
            f"Updated potentialAction for task UUID '{current_task_id}' with: {subtasks}"
        )

        return current_identifier, task_data

    def update_task_status(
        self, task_uuid: str, task_name: str, status: str, result: str
    ):
        raw_result = f'___"{result}"___'  # formatting like this allows us to store newlines, tabs and other special characters in the databse without breaking the query

        vector_embeddings = get_ollama_embedding(result)

        # Update method here so we don't overwrite any field that is not being updated
        self.update(
            "Action",
            ["uuid", "name", "actionStatus", "result"],
            [[task_uuid, task_name, status, raw_result]],
        )

        # Need to do this part separately because Update will fail if the text field does not already exist
        self.upsert(
            "Action",
            text=raw_result,
            embeddings=vector_embeddings,
            references=[["Action", [task_uuid]]],
        )
        logger.debug(f"Updated actionStatus for task UUID '{task_uuid}' to '{status}'")

    def get_previous_results(self, email_id: str):
        results = self.lookup("Action", ["result"], condition=f"object = '{email_id}'")
        results = json.loads(results)
        return [result[0] for result in results["rows"]]

    def get_context(self, query: str, top_results_num: int):
        query_embedding = get_ollama_embedding(query)
        results = self.vector_search(
            query_vector=query_embedding, number_of_results=top_results_num
        )
        try:
            results = json.loads(results)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON results: {e}")
            return []

        context_list = []

        if "rows" not in results:
            logger.error("Malformed results: missing 'rows'")
            return context_list

        for row in results["rows"]:
            if len(row) > 1 and isinstance(row[1], str):
                context_text = row[1]
                context_list.append(context_text.strip('"'))
        return context_list
