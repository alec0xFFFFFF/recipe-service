import hashlib
import os

import boto3
from botocore.exceptions import NoCredentialsError
from flask import Blueprint, request, jsonify
from psycopg2.extras import NumericRange
from sqlalchemy.exc import IntegrityError

import extract
from agents import baseAgent
from sqlalchemy import text
from werkzeug.utils import secure_filename
from data.models import db, Recipe, DescriptionEmbeddings, IngredientsEmbeddings

bp = Blueprint('bp', __name__)


@bp.route('/', methods=['POST'])
def submit_recipe():
    print(f"insert req received for recipe file")
    if 'recipe' not in request.files:
        return 'No file part', 400

    files = request.files.getlist('recipe')

    if not files or any(file.filename == '' for file in files):
        return 'No selected file', 400
    ocr_text, md5 = ocr_and_md5_recipe_request_images(files)
    print(f"md5: {md5}")
    # don't double process same image
    result = db.session.query(Recipe).filter(Recipe.submission_md5 == md5).first()
    if result:
        return jsonify(result.to_dict())

    print("passed md5 check")

    recipe, description_embeddings, ingredients_embeddings = generate_recipe_from_image(ocr_text, md5)
    db.session.add(recipe)
    db.session.commit()
    print("successfully added recipe")
    recipe_id = recipe.id
    description_embeddings_record = DescriptionEmbeddings(recipe_id=recipe_id, embeddings=description_embeddings)
    ingredients_embeddings_record = IngredientsEmbeddings(recipe_id=recipe_id, embeddings=ingredients_embeddings)
    db.session.add(description_embeddings_record)
    print("added description embeddings")
    db.session.add(ingredients_embeddings_record)
    print("added ingredients embeddings")
    db.session.commit()
    print("successfully added recipe with embeddings")
    return recipe.to_dict()


def upload_to_s3(local_file, md5):
    """
    Upload a file to an S3 bucket

    :param local_file: File to upload
    :param md5: md5 for filename
    :return: True if file was uploaded, else False
    """
    # Create an S3 client
    s3 = boto3.client('s3', aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"), aws_secret_access_key=os.environ.get("AWS_SECRET_KEY_ID"), region_name="us-west-2")

    try:
        s3.upload_fileobj(local_file, os.environ.get("IMAGE_BUCKET_NAME"), f"{md5}.png")
        print(f"Upload Successful: {local_file}")
        return True
    except FileNotFoundError:
        print("The file was not found")
        return False
    except NoCredentialsError:
        print("Credentials not available")
        return False


def ocr_and_md5_recipe_request_images(files):
    all_ocr_text = ''
    md5s = []
    for file in files:
        filename = secure_filename(file.filename)
        md5 = extract.calculate_md5(file.stream)
        print(f"req received for recipe file {filename}: {md5}")
        file.stream.seek(0)
        uploaded = upload_to_s3(file, md5)

        file.stream.seek(0)  # Reset stream pointer
        ocr_text = extract.extractText(file)
        all_ocr_text += ocr_text + ' '  # Concatenate text from each file
        md5s.append(md5)
    concatenated_md5s = ''.join(md5s)
    print("finished ocr'ing")

    # Compute MD5 of the concatenated string of individual hashes
    combined_md5 = hashlib.md5(concatenated_md5s.encode()).hexdigest()
    return all_ocr_text, combined_md5


def generate_recipe_from_image(ocr_text, md5):
    agent = baseAgent.Agent()
    print(f"ocr text: {ocr_text}")
    ingredients = agent.generate_response(
        f"You are an food recipe ingredients extraction agent. Your goal is to extract the ingredients from the "
        f"recipe provided by the user. You must use the exact wordage of the ingredient and measurement in the "
        f"recipe, but return a bulleted list of all ingredients needed. If the provided text is unintelligible return <none>.",
        ocr_text)
    steps = agent.generate_response(
        f"You are an food recipe steps extraction agent. Your goal is to extract the steps from the recipe provided "
        f"by the user. You must use the exact wordage of the steps in the recipe, but return a bulletted list of all "
        f"steps. If the provided text is unintelligible return <none>.",
        ocr_text)
    equipment = agent.generate_response(
        f"You are an food recipe equipment extraction agent. Your goal is to extract the equipment from the recipe "
        f"provided by the user. You must use the exact wordage of the equipment in the recipe, but return a bulletted "
        f"list of all equipment. If the provided text is unintelligible return <none>.",
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
        "How many minutes will it take to make this dish given the following information: " +
        ocr_text))
    description = agent.generate_response(
        f"You are a recipe description agent. Your goal is to return a very descriptive 15-30 word description of the "
        f"dish in the recipe. You must describe the type of food it is, taste, cuisine (e.g. italian), seasonality, "
        f"ingredients, and ease. If the provided text is unintelligible return <none>.",
        ocr_text)
    title = agent.generate_response(
        f"You are a recipe titling agent. Your goal is to return a succinct yet descriptive title for a dish. The title must be accurate. If the provided text is unintelligible return <none>.",
        ocr_text)
    author = agent.generate_response("Extract the author or writer of the recipe. If there is none return <none>",
                                     ocr_text)

    description_embeddings = agent.get_embedding(description)
    ingredients_embeddings = agent.get_embedding(ingredients)
    print("all agents run")
    print(f"description: {description}")
    if description == "<none>":
        raise Exception
    # todo if refusal fail loudly
    return Recipe(ingredients=ingredients,
                  steps=steps,
                  equipment=equipment,
                  time=time,
                  description=description,
                  servings=servings,
                  title=title,
                  author=author,
                  submission_md5=md5
                  ), description_embeddings, ingredients_embeddings


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


@bp.route('/recipes/<int:recipe_id>', methods=['GET'])
def get_recipes(recipe_id):
    # delete description and ingredient embeddings
    try:
        recipe = Recipe.query.filter_by(id=recipe_id).first()
    except IntegrityError:
        db.session.rollback()
        return jsonify({'message': 'Deletion failed due to integrity error'}), 500
    raise NotImplementedError


@bp.route('/recipes/<int:recipe_id>', methods=['DELETE'])
def delete_recipe(recipe_id):
    try:
        recipe = Recipe.query.filter_by(id=recipe_id).first()
        if recipe:
            db.session.delete(recipe)
            db.session.commit()
            return jsonify({'message': 'Parent and its children deleted successfully'}), 200
        else:
            return jsonify({'message': 'Parent not found'}), 404
    except IntegrityError:
        db.session.rollback()
        return jsonify({'message': 'Deletion failed due to integrity error'}), 500


@bp.route('/recipes/<int:recipe_id>', methods=['PUT'])
def modify_recipe(recipe_id):
    print(f"update req received for recipe file(s)")
    if 'recipe' not in request.files:
        return 'No file part', 400

    files = request.files.getlist('recipe')

    if not files or any(file.filename == '' for file in files):
        return 'No selected file', 400
    ocr_text, md5 = ocr_and_md5_recipe_request_images(files)
    recipe, description_embeddings, ingredients_embeddings = generate_recipe_from_image(ocr_text, md5)
    recipe.recipe_id = recipe_id
    try:
        description_embeddings_record = DescriptionEmbeddings.query.filter_by(recipe_id=recipe_id).first()
        description_embeddings_record.embeddings = description_embeddings
        ingredients_embeddings_record = IngredientsEmbeddings.query.filter_by(recipe_id=recipe_id).first()
        ingredients_embeddings_record.embeddings = ingredients_embeddings
        db.session.add(description_embeddings_record)
        db.session.add(ingredients_embeddings_record)
        db.session.commit()
        return jsonify(recipe)
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': str(e)}), 500


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
        {"id": row.id, "author": row.author, "title": row.title, "description": row.description} for row in
        rows]
    print(f"found {len(closest_embeddings)} recipes")
    return jsonify({"dishes": closest_embeddings})


@bp.route('/pantry', methods=['POST'])
def add_item_to_pantry():
    # todo take in an optional image and payload with info
    # expiration
    # description
    # should have an amount and unit
    raise NotImplementedError


@bp.route('/pantry', methods=['PUT'])
def delete_pantry_item():
    # can change
    # delete from pantry
    raise NotImplementedError


@bp.route('/pantry', methods=['PUT'])
def modify_pantry_item():
    # can change
    # delete from pantry
    raise NotImplementedError


@bp.route('/pantry', methods=['GET'])
def search_pantry():
    agent = baseAgent.Agent()
    query_string = request.args.get('query', '')

    if not query_string:
        return jsonify({"error": "No query string provided"}), 400

    embeddings = agent.get_embedding(query_string)
    sql_query = text("""
        SELECT * FROM pantry_items
        WHERE id IN (
        SELECT pantry_item_id FROM pantry_item_embeddings
        ORDER BY embeddings <-> CAST(:embeddings AS vector)
        LIMIT 5) AND deleted = FALSE AND NOW() < expiration 
    """)

    query_params = {"embeddings": embeddings}

    result = db.session.execute(sql_query, query_params)

    # Retrieve the rows from the result
    rows = result.fetchall()

    # Serialize the results
    closest_embeddings = [
        {"id": row.id, "expiration": row.expiration, "name": row.name, "description": row.description,
         "image": row.image} for row in
        rows]

    return jsonify(closest_embeddings)


# todo recommend recipe based on my pantry

# create shopping list from recipes i've added and my pantry

# create account via google and apple

def init_api_v1(app):
    app.register_blueprint(bp, url_prefix='/v1')
