from enum import Enum

import openai
import threading
from typing import List
from pydantic import BaseModel

from data.chat.action import Action
from data.chat.role import Role

class Refusal(Exception):
    def __init__(self, field, message="Invalid input"):
        self.field = field
        self.message = message
        super().__init__(f"{self.field}: {self.message}")

class ClassifierResultType(BaseModel):
    raw_result: str
    result_type: Enum

    @staticmethod
    def string_to_enum(input_string, enum):
        for member in enum:
            if member.name == input_string.upper():
                return member
        raise ValueError(f"{input_string} is not a valid enum name")
    def parse_result(self):
        # check if refusal/none
        if self.raw_result is None or self.raw_result == "" or self.raw_result == "<none>" or self.raw_result == "none":
            raise Refusal(field="raw_result", message=f"result:{self.raw_result}")
        return self.string_to_enum(self.raw_result, self.result_type)


class ActionResult(ClassifierResultType):
    result_type: Enum = Action.__class__



class Classifier(BaseModel):
    prompt: str
    result_type: ClassifierResultType


class Message(BaseModel):
    role: Role
    message: str
    id: int
    user_id: int


class ConversationModel(BaseModel):
    conversation_id: int
    latest_user_msg: Message
    latest_assistant_msg: Message
    messages: List[Message]


# Define Pydantic model for storing responses
class ChatCompletionResponse(BaseModel):
    prompt: str
    role: str
    completion: str


# Function to send a chat completion request
def fetch_chat_completion(prompt: str, usr_msg: Message, conversation: ConversationModel,
                          responses: List[ChatCompletionResponse]):
    response = openai.ChatCompletion.create(
        model="gpt-4",  # specify the model
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    responses.append(ChatCompletionResponse(prompt=prompt, completion=response['choices'][0]['message']['content']))


# Main function to send multiple requests
def main(prompts: List[str], usr_msg: Message, conversation: ConversationModel):
    threads = []
    responses = []

    for prompt in prompts:
        thread = threading.Thread(target=fetch_chat_completion, args=(prompt, usr_msg, conversation, responses))
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()

    return responses


if __name__ == "__main__":
    # Example prompts
    # ACTION CLASSIFIER, RECIPE SELECTION, ACTIONS, TECHNIQUES?
    prompts = ["is the user asking for a recipe?", "did the user select a recipe and wants ingredients and steps?",
               "is the user attempting one of these actions?", "Is the user asking for a substitution?",
               "Is the user asking for a technique or how to do something?"]
    # which aisle is the ingredient in
    # which store has my ingredients -> drive business and safe
    # modify recipe -> replace or scale up/down -> serving sizes so no calculations in the aisle
    # nyt cooking comments very active
    usr_msg = "hello can i get a recipe"
    conversation = ["convo"]
    # Run the main function
    chat_responses = main(prompts, usr_msg, conversation)
