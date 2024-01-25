from flask import Blueprint, request, jsonify
from psycopg2.extras import NumericRange

import extract
from agents import baseAgent
from sqlalchemy import text
from data.models import db, Recipe, DescriptionEmbeddings, IngredientsEmbeddings

bp = Blueprint('bp', __name__)


@bp.route('/', methods=['POST'])
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

    md5 = extract.calculate_md5(file.stream)
    print(f"req received for recipe file: {md5}")
    ocr_text = extract.extractText(file)

    # don't double process same image
    result = db.session.query(Recipe).filter(Recipe.submission_md5 == md5).first()
    if result:
        return jsonify(result.to_dict())

    agent = baseAgent.Agent()
    ingredients = agent.generate_response(
        f"You are an food recipe ingredients extraction agent. Your goal is to extract the ingredients from the recipe provided by the user. You must use the exact wordage of the ingredient and measurement in the recipe, but return a bulletted list of all ingredients needed.",
        ocr_text)
    steps = agent.generate_response(
        f"You are an food recipe steps extraction agent. Your goal is to extract the steps from the recipe provided by the user. You must use the exact wordage of the steps in the recipe, but return a bulletted list of all steps.",
        ocr_text)
    equipment = agent.generate_response(
        f"You are an food recipe equipment extraction agent. Your goal is to extract the equipment from the recipe provided by the user. You must use the exact wordage of the equipment in the recipe, but return a bulletted list of all equipment.",
        ocr_text)
    servings = parse_numeric_range_or_null(agent.generate_response(
        f"""You are an food recipe servings extraction agent. Your goal is to extract the servings from the recipe provided by the user. You must use the exact wordage of the servings in the recipe, if amount fo servings not specified than make an educated guess. You must only return a number range e.g. `2-4`
        Example:
        [user]: How many servings is this dish given the following information: This recipe serves a family of 2-4, but can be stretched to feed more by scaling.
        [assistant]: 2-4
        """,
        "How many servings is this dish given the following information: " +
        ocr_text))
    time = parse_int_or_null(agent.generate_response(
        f"""You are a recipe time extraction and estimation agent. Your goal is to return the total number of minutes it will take to complete the recipe. You must use the exact minutes estimate if provided, but if none is provided do your best to accurately estimate the time it will take. You must only return the number of minutes e.g. `35`
        Example:
        [user]: How much minutes will it take to make this dish given the following information: This recipe takes 15 minutes of prep time and 20 minutes of cooking time.
        [assistant]: 35
        [user]: How much minutes will it take to make this dish given the following information: The estimated total time for this Zesty Lemon Garlic Shrimp Pasta recipe is 45 minutes.
        [assistant]: 45
        """,
        "How much minutes will it take to make this dish given the following information: " +
        ocr_text))
    description = agent.generate_response(
        f"You are a recipe description agent. Your goal is to return a very descriptive 15-30 word description of the dish in the recipe. You must describe the type of food it is, taste, cuisine (e.g. italian), seasonality, ingredients, and ease.",
        ocr_text)
    title = agent.generate_response(
        f"You are a recipe titling agent. Your goal is to return a succinct yet descriptive title for a dish.",
        ocr_text)
    author = agent.generate_response("Extract the author or writer of the recipe. If there is none return <none>",
                                     ocr_text)

    description_embeddings = agent.get_embedding(description)
    ingredients_embeddings = agent.get_embedding(ingredients)

    recipe = Recipe(ingredients=ingredients,
                    steps=steps,
                    equipment=equipment,
                    time=time,
                    description=description,
                    servings=servings,
                    title=title,
                    author=author,
                    submission_md5=md5
                    )
    db.session.add(recipe)
    db.session.commit()
    recipe_id = recipe.id
    description_embeddings = DescriptionEmbeddings(recipe_id=recipe_id, embeddings=description_embeddings)
    ingredients_embeddings = IngredientsEmbeddings(recipe_id=recipe_id, embeddings=ingredients_embeddings)
    db.session.add(description_embeddings)
    db.session.add(ingredients_embeddings)
    db.session.commit()

    return recipe.to_dict()


def parse_int_or_null(input_string):
    try:
        res = int(input_string)
        print(f"parsed int: {res}")
        return res
    except ValueError:
        return None


def parse_numeric_range_or_null(input_string):
    # Check if the input_string contains a hyphen ("-")
    try:
        if "-" in input_string:
            start, end = map(float, input_string.split("-"))
            res = NumericRange(int(start), int(end) + 1)
            print(f"parsed numeric range: {res}")
            return res
        else:
            value = float(input_string)
            res = NumericRange(int(value), int(value) + 1)
            print(f"parsed numeric range: {res}")
            return res
    except ValueError:
        return None


@bp.route('/image', methods=['POST'])
def generate_image():
    if 'food' not in request.files:
        return 'No file part'

    file = request.files['food']

    if file.filename == '':
        return 'No selected file'
    # submit image, add description, use prompt and do a dalle-2 variation
    byte_array = file.stream.read()
    agent = baseAgent.Agent()
    url = agent.get_image_variations(byte_array)
    return jsonify({"image": url})


@bp.route('/', methods=['GET'])
def search_for_recipe():
    agent = baseAgent.Agent()
    query_string = request.args.get('query', '')

    if not query_string:
        return jsonify({"error": "No query string provided"}), 400

    embeddings = agent.get_embedding(query_string)
    sql_query = text("""
        SELECT * FROM recipe
        WHERE id IN (
        SELECT recipe_id FROM description_embeddings
        ORDER BY embeddings <-> CAST(:embeddings AS vector)
        LIMIT 5)
    """)

    query_params = {"embeddings": embeddings}

    result = db.session.execute(sql_query, query_params)

    # Retrieve the rows from the result
    rows = result.fetchall()

    # Serialize the results
    closest_embeddings = [
        {"author": row.author, "title": row.title, "description": row.description} for row in
        rows]

    return jsonify({"dishes": closest_embeddings})


def init_api_v1(app):
    app.register_blueprint(bp, url_prefix='/v1')
