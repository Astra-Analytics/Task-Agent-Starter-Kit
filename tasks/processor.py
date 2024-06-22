import json
import logging
import os
import re
import threading
import time

import flask
from dotenv import load_dotenv
from flask import Flask
from flask import current_app as app

from integrations.email.fetcher import email_queue
from tasks.agents import (
    conditional_entity_addition,
    entity_extraction_agent,
    objective_agent,
    task_creation_agent,
)
from tasks.execution import execution_agent
from tasks.storage import SingleTaskListStorage

# Load environment variables from .env file
load_dotenv()

MAX_THREADS = int(os.getenv("MAX_THREADS", 4))

logger = logging.getLogger(__name__)

# Initialize task storage
tasks_storage = SingleTaskListStorage()

# Ensure the app context is created
app = Flask(__name__)


def sanitize_json_response(response):
    # Remove trailing commas before closing brackets or braces
    sanitized_response = re.sub(r",\s*([\]}])", r"\1", response)
    return sanitized_response


def process_entity_extraction_and_addition(email_data):
    try:
        body = email_data["Body"]
        logger.debug("Calling entity_extraction_agent...")
        entity_extraction_response = entity_extraction_agent(body)
        logger.debug(f"Entity extraction response: {entity_extraction_response}")

        if entity_extraction_response:
            sanitized_response = sanitize_json_response(entity_extraction_response)
            entity_data = json.loads(sanitized_response)

            # Process the entire entity data in one call to conditional_entity_addition
            addition_response = conditional_entity_addition(
                {"entities": entity_data["entities"]}
            )
            logger.info(f"Entity addition response: {addition_response}")

        else:
            logger.info("No entities extracted.")
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        logger.error(f"Entity extraction response was: {entity_extraction_response}")
    except Exception as e:
        logger.error(
            f"Error processing entity extraction and addition: {e}", exc_info=True
        )


def process_email(email_data):
    try:
        email_id = email_data["Message-ID"]
        existing_tasks = tasks_storage.get_tasks(object=email_id)
        email_subject = email_data["Subject"]
        logger.info(f"Existing tasks for email '{email_subject}': {existing_tasks}")

        # Check if the task with identifier 0 is complete
        if any(
            task["identifier"] == 0 and task["actionStatus"] == "Complete"
            for task in existing_tasks.values()
        ):
            logger.info(
                f"Email with ID {email_id} has already been fully processed. Skipping."
            )
            return

        # If no existing tasks, proceed with objective agent and primary task creation
        if not existing_tasks:
            to = email_data["To"]
            from_email = email_data["From"]
            subject = email_data["Subject"]
            timestamp = email_data["Timestamp"]
            body = email_data["Body"]
            attachments = ""  # Assuming no attachments for simplicity

            logger.info(f"Starting entity extraction for email ID {email_id}")
            entity_extraction_processor(email_data)

            logger.debug("Calling objective_agent...")
            objective_response = objective_agent(
                to, from_email, subject, timestamp, body, attachments
            )

            if not objective_response["tasks_found"]:
                logger.info("No tasks identified in the email.")
                return

            OBJECTIVE = objective_response["tasks"][0]["name"]
            logger.info(f"OBJECTIVE: {OBJECTIVE}")

            primary_task = {
                "uuid": tasks_storage.next_task_id(),
                "name": OBJECTIVE,
                "agent": "AI",
                "actionStatus": "Active",
                "identifier": 0,
                "object": email_id,
            }
            tasks_storage.append(primary_task)
            logger.debug(f"Primary task created: {primary_task}")

            # Add this new task to the existing_tasks dictionary
            existing_tasks[primary_task["uuid"]] = primary_task

            # Update the dashboard after processing
            with app.app_context():
                update_dashboard()

            current_identifier = 0
            max_identifier = 0

        else:
            # Set current_identifier to the largest identifier that is not complete
            incomplete_tasks = [
                task
                for task in existing_tasks.values()
                if task["actionStatus"] != "Complete"
            ]
            if incomplete_tasks:
                max_identifier = max(task["identifier"] for task in incomplete_tasks)
                current_identifier = max_identifier
            else:
                logger.info(
                    f"All tasks for email ID {email_id} are complete. Skipping."
                )
                return

        tasks = existing_tasks

        while current_identifier >= 0:
            # Find the task with the current_identifier and agent as AI
            task = next(
                (
                    t
                    for t in tasks.values()
                    if t["identifier"] == current_identifier and t["agent"] == "AI"
                ),
                None,
            )

            if not task:
                logger.info("No more AI tasks to process.")
                break

            logger.info(
                f"Processing task: {task['name']} with identifier {current_identifier}"
            )

            previous_results = tasks_storage.get_previous_results(email_id)
            context = tasks_storage.get_context(task["name"], 5)
            result = execution_agent(task["name"], previous_results, context)

            if result == "More context needed":
                new_tasks = task_creation_agent(task["name"], previous_results)
                current_identifier, tasks = tasks_storage.add_subtasks(
                    current_task_id=task["uuid"],
                    current_task_name=task["name"],
                    potential_actions=new_tasks,
                    max_identifier=max_identifier,
                )
                max_identifier = current_identifier
                logger.info(f"Created new sub-tasks: {new_tasks}")
            else:
                task["actionStatus"] = "Complete"
                tasks_storage.update_task_status(
                    task["uuid"], task["name"], "Complete", result
                )
                current_identifier -= 1

            time.sleep(1)

            # Update the dashboard after processing
            with app.app_context():
                update_dashboard()

    except Exception as e:
        logger.error(f"Error processing email: {e}", exc_info=True)
    finally:
        email_queue.task_done()


def entity_extraction_processor(email_data):
    entity_thread = threading.Thread(
        target=process_entity_extraction_and_addition,
        args=(email_data,),
        daemon=True,
        name=f"EntityExtraction-{email_data['Message-ID']}",
    )
    entity_thread.start()


def update_dashboard():
    logger.info("Updating dashboard...")
    tasks = tasks_storage.get_tasks()
    agent_tasks = [task for task in tasks.values() if task["agent"] == "AI"]
    human_tasks = [task for task in tasks.values() if task["agent"] != "AI"]
    flask.g.agent_tasks = agent_tasks
    flask.g.human_tasks = human_tasks


def email_processor():
    active_threads = {}
    while True:
        if len(active_threads) < MAX_THREADS:
            email_data = email_queue.get()
            email_id = email_data["Subject"]
            if email_id not in active_threads:
                thread = threading.Thread(
                    target=process_email,
                    args=(email_data,),
                    daemon=True,
                    name=f"EmailProcessor-{email_id}",
                )
                active_threads[email_id] = thread
                thread.start()
        # Clean up finished threads
        for email_id, thread in list(active_threads.items()):
            if not thread.is_alive():
                del active_threads[email_id]


def start_processing():
    processor_thread = threading.Thread(
        target=email_processor, daemon=True, name="EmailProcessorThread"
    )
    processor_thread.start()
