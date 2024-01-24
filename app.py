import os

from flask import Flask, request
from agents import baseAgent
import extract
from data.models import db, Recipe, DescriptionEmbeddings

app = Flask(__name__)

with app.app_context():
    db.create_all()

db_params = {
    "dbname": os.environ.get("PGDATABASE"),
    "user": os.environ.get("PGUSER"),
    "password": os.environ.get("PGPASSWORD"),
    "host": os.environ.get("PGHOST"),
    "port": int(os.environ.get("PGPORT"))
}

# Database configuration
app.config[
    'SQLALCHEMY_DATABASE_URI'] = f'postgresql://{db_params["user"]}:{db_params["password"]}@{db_params["host"]}:{db_params["port"]}/{db_params["dbname"]}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)


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
    md5 = extract.calculate_md5(file.stream)
    # todo see if we've processed this before
    print(md5)
    agent = baseAgent.Agent()
    ingredients = agent.generate_response(
        f"You are an food recipe ingredients extraction agent. Your goal is to extract the ingredients from the recipe provided by the user. You must use the exact wordage of the ingredient and measurement in the recipe, but return a bulletted list of all ingredients needed.",
        text)
    steps = agent.generate_response(
        f"You are an food recipe steps extraction agent. Your goal is to extract the steps from the recipe provided by the user. You must use the exact wordage of the steps in the recipe, but return a bulletted list of all steps.",
        text)
    equipment = agent.generate_response(
        f"You are an food recipe equipment extraction agent. Your goal is to extract the equipment from the recipe provided by the user. You must use the exact wordage of the equipment in the recipe, but return a bulletted list of all equipment.",
        text)
    time = agent.generate_response(
        f"You are a recipe time extraction and estimation agent. Your goal is to return the total number of minutes it will take to complete the recipe. You must use the exact minutes estimate if provided, but if none is provided do your best to accurately estimate the time it will take. Only return the number of minutes ex: 35.",
        text)
    description = agent.generate_response(
        f"You are a recipe description agent. Your goal is to return a very descriptive 15-30 word description of the dish in the recipe. You must describe the type of food it is, taste, cuisine (e.g. italian), seasonality, ingredients, and ease.",
        text)
    title = agent.generate_response(
        f"You are a recipe titling agent. Your goal is to return a succinct yet descriptive title for a dish.", text)
    author = agent.generate_response("Extract the author or writer of the recipe. If there is none return <none>", text)
    # todo store file in s3 to audit? or check hash of file before processing?

    embeddings = agent.get_embedding(description)

    # todo store this stuff in vector db
    print(embeddings)

    recipe = Recipe(ingredients=ingredients,
                    steps=steps,
                    equipment=equipment,
                    time=time,
                    description=description,
                    title=title,
                    author=author,
                    submission_md5=md5
                    )
    db.session.add(recipe)
    embeddings = DescriptionEmbeddings(recipe_id=recipe.id, embeddings=embeddings)
    db.session.add(embeddings)
    db.session.commit()

    return recipe.to_dict()


if __name__ == '__main__':
    app.run()
