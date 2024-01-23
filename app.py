from flask import Flask, request
from agents import baseAgent
import extract

app = Flask(__name__)


@app.route('/', methods=['POST'])
def submit_recipe():
    # input of an image
    # three agents to split up
    # store everything
    # return id
    # todo handle multiple files and concatenate together
    if 'recipe' not in request.files:
        return 'No file part'

    file = request.files['recipe']

    if file.filename == '':
        return 'No selected file'
    print("req received")
    text = extract.extractText(file)
    agent = baseAgent.Agent()
    ingredients = agent.generate_response(f"You are an food recipe ingredients extraction agent. Your goal is to extract the ingredients from the recipe provided by the user. You must use the exact wordage of the ingredient and measurement in the recipe, but return a bulletted list of all ingredients needed.", text)
    steps = agent.generate_response(f"You are an food recipe steps extraction agent. Your goal is to extract the steps from the recipe provided by the user. You must use the exact wordage of the steps in the recipe, but return a bulletted list of all steps.", text)
    equipment = agent.generate_response(f"You are an food recipe equipment extraction agent. Your goal is to extract the equipment from the recipe provided by the user. You must use the exact wordage of the equipment in the recipe, but return a bulletted list of all equipment.", text)
    time = agent.generate_response(f"You are a recipe time extraction and estimation agent. Your goal is to return the total number of minutes it will take to complete the recipe. You must use the exact minutes estimate if provided, but if none is provided do your best to accurately estimate the time it will take.", text)
    description = agent.generate_response(f"You are a recipe description agent. Your goal is to return a very descriptive 15-30 word description of the dish in the recipe. You must describe the type of food it is, taste, cuisine (e.g. italian), seasonality, ingredients, and ease.", text)
    # todo store file in s3
    # todo classifier?


    embeddings = agent.get_embedding(description)


    # todo store this stuff in vector db
    print(embeddings)

    return {"ingredients": ingredients,
            "steps": steps,
            "equipment": equipment,
            "time": time,
            "description": description
            }


if __name__ == '__main__':
    app.run()
