import json
from typing import List

import ollama
from ollama import Message


def conditional_entity_addition(data):
    # Retrieve the entity type from the data
    entity_type = data.get("entity_type", None)
    # If no entity type is provided, return an error
    if not entity_type:
        return {"error": "Entity type is required."}, 400

    # Adjusted to access nested 'data'
    entity_data = data.get("data", {})

    search_results = [
        {"id": "1", "name": "John Smith"},
        {"id": "2", "name": "Jane Doe"},
    ]

    # Combine all search results
    combined_results = {result["id"]: result for result in search_results}.values()
    print(f"Combined results: {list(combined_results)}")
    combined_results_str = ", ".join(json.dumps(result) for result in combined_results)

    # Prepare the message for OpenAI API
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

    # Make a call to OpenAI API
    try:
        response = ollama.chat(
            model="llama3",
            messages=prompt,
            stream=True,
        )

        if isinstance(response, dict) and "response" in response:
            response_text = response["response"]
            return response_text
        else:
            ai_response = ""
            for chunk in response:
                if isinstance(chunk, dict):
                    if (
                        "message" in chunk
                        and isinstance(chunk["message"], dict)
                        and "content" in chunk["message"]
                    ):
                        print(chunk["message"]["content"], end="", flush=True)
                        ai_response += chunk["message"]["content"]
                    else:
                        raise Exception("Invalid chunk structure")
            print(f"AI response: {ai_response}")

            # Process the AI's response
            if "no matches" in ai_response.lower():
                # If no match found, add the new entity
                # entity_id = add_entity(entity_type, data)
                print("adding entity\n\n")
                entity_id = "123"
                return {"success": True, "entity_id": entity_id}, 200
            else:
                # If a match is found, return the match details
                match_id = ai_response
                return {
                    "success": False,
                    "message": "Match found",
                    "match_id": match_id,
                }, 200

    except Exception as e:
        print(f"Error calling OpenAI: {e}")
        return {"error": str(e)}, 500


# Mocking the input data
input_data = {"entity_type": "person", "data": {"name": "John Doe", "age": 30}}

# Call the function and print the result
result, status_code = conditional_entity_addition(input_data)
print(result, status_code)
