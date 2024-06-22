import logging
import time
from queue import Queue

from .gmail import fetch_latest_email, gmail_service

logger = logging.getLogger(__name__)

email_queue = Queue()
processed_email_ids = set()


def email_fetcher(credentials):
    logger.info("Starting email fetcher...")
    while True:
        service = gmail_service(credentials)
        if not service:
            logger.warning("Failed to create Gmail service, retrying in 10 seconds...")
            time.sleep(10)  # Retry after some time if service is not available
            continue

        email_data = fetch_latest_email(service)
        if email_data and email_data["Message-ID"] not in processed_email_ids:
            logger.info(f"New email found: {email_data['Message-ID']}")
            email_queue.put(email_data)
            processed_email_ids.add(email_data["Message-ID"])
        else:
            logger.debug("No new emails found.")
        time.sleep(10)  # Adjust the interval as needed
