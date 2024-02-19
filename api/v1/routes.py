import asyncio
import hashlib
import io
import os
import tempfile

import boto3
import requests
import socketio
import websockets
from botocore.exceptions import NoCredentialsError
from elevenlabs import generate, stream, set_api_key
from flask import Blueprint, request, jsonify, send_file
from psycopg2.extras import NumericRange
from sqlalchemy.exc import IntegrityError

import extract
from agents import baseAgent
from sqlalchemy import text
from werkzeug.utils import secure_filename

from agents.baseAgent import Agent
from data.models import db, Recipe, DescriptionEmbeddings, IngredientsEmbeddings
WEBRTC_SERVER_URL = os.getenv('WEBRTC_SERVER_URL')  # Replace with your WebRTC server endpoint

bp = Blueprint('bp', __name__)

set_api_key(os.getenv("ELEVEN_LABS_KEY"))


def is_only_whitespace(s):
    return s.isspace()


@bp.route('/audio-recipe-options', methods=['POST'])
def audio_get_recipe_options():
    if 'file' not in request.files:
        return "No file part", 400
    file = request.files['file']
    if file.filename == '':
        return "No selected file", 400
    if file:
        try:
            print(f"attempting to process audio")
            # todo save input and output to s3
            with tempfile.NamedTemporaryFile(suffix='.m4a', delete=False) as tmp:
                file.save(tmp.name)
                tmp_path = tmp.name
                # OpenAI API call with the converted .mp3 file
                with open(tmp_path, 'rb') as tmp_file:
                    agent = baseAgent.Agent()
                    recipe_request = agent.get_transcript(tmp_file)
                    print(f"Recipe request: {recipe_request}")
                    closest_embeddings = get_nearest_recipes(recipe_request)
                    numbered_recipes = "\n".join(
                        [f"{i + 1}. Title: {item['title']}, Description: {item['description']}" for i, item in
                         enumerate(closest_embeddings)])

                    # generate a response based on user
                    response = agent.generate_response(
                        f"You are a culinary assistant and your job is to pitch recipes for the user to make for their next meal.Your response will be read directly by a narrator so make it cohesive and don't label the options with numbers. if any recipe looks incomplete or has `sorry` in it you must not give that option. Address the user's recipe request by describing and pitching the following recipes: {numbered_recipes}",
                        recipe_request)
                    print(f"recommendations: {response}")
                    audio_bytes = agent.text_to_speech(response)
                    CHUNK_SIZE = 1024
                    chunks = b''
                    for chunk in audio_bytes.iter_content(chunk_size=CHUNK_SIZE):
                        if chunk:
                            chunks += chunk
                    out_bytes = io.BytesIO(chunks)
                    return send_file(out_bytes, mimetype='audio/wav', as_attachment=True, download_name='narration'
                                                                                                        '.mp3')
        except Exception as e:
            return str(e), 500
    return str("no file"), 400


@bp.route("/eleven-labs", methods=['GET'])
def eleven_labs():
    return os.getenv("ELEVEN_LABS_KEY")


@bp.route('/chat', methods=['POST'])
def chat():
    print("chat recieved")
    msg = request.json['content']
    # todo run classifier for recommendation, response, technique and
    # persist messages and use history in request
    print(f"Chat request: {msg}")
    closest_embeddings = get_nearest_recipes(msg)
    numbered_recipes = "\n".join(
        [f"{i + 1}. Title: {item['title']}, Description: {item['description']}" for i, item in
         enumerate(closest_embeddings)])
    # generate a response based on user
    agent = baseAgent.Agent()
    response = agent.generate_response(
        f"You are a culinary assistant and your job is to pitch recipes for the user to make for their next meal.Your response will be read directly by a narrator so make it cohesive and don't label the options with numbers. if any recipe looks incomplete or has `sorry` in it you must not give that option. Address the user's recipe request by describing and pitching the following recipes: {numbered_recipes}",
        msg)
    print(f"recommendations: {response}")
    return jsonify({"content": response})


@bp.route('/', methods=['POST'])
def submit_recipe():
    print(f"insert req received for recipe file")
    if 'recipe' not in request.files:
        return 'No file part', 400

    files = request.files.getlist('recipe')

    ocr_text_from_request = request.form.get('ocr_text', '')

    if not files or any(file.filename == '' for file in files):
        return 'No selected file', 400
    ocr_text, md5 = ocr_and_md5_recipe_request_images(files)
    if not is_only_whitespace(ocr_text_from_request):
        # print(f"------ocr_text from req: {ocr_text_from_request}")
        # print(ocr_text_from_request)
        # ocr_text = ocr_text_from_request
        pass
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
    s3 = boto3.client('s3', aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                      aws_secret_access_key=os.getenv("AWS_SECRET_KEY_ID"), region_name="us-west-2")

    try:
        s3.upload_fileobj(local_file, os.getenv("IMAGE_BUCKET_NAME"), f"{md5}.png")
        print(f"Upload Successful: {md5}.png")
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
        file.stream.seek(0)
        file_content = file.read()
        md5_hash = extract.calculate_md5(io.BytesIO(file_content))
        print(f"req received for recipe file {filename}: {md5_hash}")
        # Reset the stream position after MD5 calculation
        file_in_memory = io.BytesIO(file_content)
        file.stream.seek(0)
        uploaded = upload_to_s3(file_in_memory, md5_hash)

        file_in_memory_1 = io.BytesIO(file_content)
        file.stream.seek(0)  # Reset stream pointer
        agent = Agent()
        ocr_text = agent.generate_vision_response(file_in_memory_1,
                                                  "Extract all the text in this image of a recipe. Skip the pleasantries and just return only the transcribed text.")
        all_ocr_text += ocr_text + "\n"  # Concatenate text from each file
        md5s.append(md5_hash)
    concatenated_md5s = ''.join(md5s)
    print(f"finished ocr'ing: {all_ocr_text}")

    # Compute MD5 of the concatenated string of individual hashes
    combined_md5 = hashlib.md5(concatenated_md5s.encode()).hexdigest()
    return all_ocr_text, combined_md5


def generate_recipe_from_image(ocr_text, md5):
    agent = baseAgent.Agent()
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
def get_recipe(recipe_id):
    try:
        recipe = Recipe.query.filter_by(id=recipe_id).first()
        print(f"found recipe {recipe}")
        return recipe.to_dict()
    except IntegrityError:
        db.session.rollback()
        return jsonify({'message': 'Deletion failed due to integrity error'}), 500


@bp.route('/recipes/<int:recipe_id>', methods=['DELETE'])
def delete_recipe(recipe_id):
    try:
        print(f"deleting recipe: {recipe_id}")
        recipe = db.session.query(Recipe).filter_by(id=recipe_id).first()
        if recipe:
            sql_query = text("""
                DELETE FROM description_embeddings WHERE recipe_id = :recipe_id;
            """)

            query_params = {"recipe_id": recipe_id}

            result = db.session.execute(sql_query, query_params)
            sql_query = text("""
                            DELETE FROM ingredients_embeddings WHERE recipe_id = :recipe_id;
                        """)
            result = db.session.execute(sql_query, query_params)
            db.session.commit()
            db.session.delete(recipe)
            db.session.commit()
            return jsonify({'message': 'Parent and its children deleted successfully'}), 200
        else:
            print(f"error not found when deleting recipe: {recipe_id}")
            return jsonify({'message': 'Parent not found'}), 404
    except IntegrityError:
        db.session.rollback()
        print(f"error deleting recipe: {recipe_id}")
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


def get_nearest_recipes(query):
    agent = baseAgent.Agent()
    embeddings = agent.get_embedding(query)
    sql_query = text("""
            SELECT recipe.* FROM recipe
            JOIN description_embeddings ON recipe.id = description_embeddings.recipe_id
            ORDER BY description_embeddings.embeddings <-> CAST(:embeddings AS vector)
            LIMIT 5;
        """)

    query_params = {"embeddings": embeddings}

    result = db.session.execute(sql_query, query_params)

    # Retrieve the rows from the result
    rows = result.fetchall()

    return [
        {"id": row.id, "author": row.author, "title": row.title, "description": row.description} for row in
        rows]


@bp.route('/', methods=['GET'])
def search_for_recipe():
    agent = baseAgent.Agent()
    query_string = request.args.get('query', '')

    if not query_string:
        return jsonify({"error": "No query string provided"}), 400

    # Serialize the results
    closest_embeddings = get_nearest_recipes(query_string)
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

def generate_example_text(text):
    yield "Hello world"
    yield "this is a test"
    yield text


@bp.route("/speak", methods=["POST"])
def speak():
    audio = generate(
        text=generate_example_text(request.args.get('text', 'goodbye world')),
        voice="Antoni",
        model="eleven_multilingual_v2",
        stream=True
    )
    stream(audio)


@bp.route('/offer', methods=['POST'])
def offer():
    data = request.get_json()
    user_query = data.get("userQuery")  # Extract the user query

    # todo accept audio file or text file then run the search and format and return

    # Forward the offer and user query to the WebRTC server
    webrtc_response = requests.post(WEBRTC_SERVER_URL, json={
        'sdp': data['sdp'],
        'type': data['type'],
        'userQuery': user_query
    })

    # Assuming the WebRTC server responds with an SDP answer
    return jsonify(webrtc_response.json())


# todo recommend recipe based on my pantry

# create shopping list from recipes i've added and my pantry

# create account via google and apple

def init_api_v1(app):
    app.register_blueprint(bp, url_prefix='/v1')


def register_socketio_events(sio):
    @sio.on('connect')
    def handle_connect():
        print('Client connected to my_blueprint')
        socketio.emit('someEvent', "hello from the server", broadcast=True)

    @sio.on('disconnect')
    def handle_disconnect():
        print('Client disconnected from my_blueprint')

    @sio.on('messageEvent')
    def handle_message_event(data):
        print('Received message:', data)

    @sio.on('audio_chunk')
    def handle_audio_chunk(data):
        # 'data' is the received audio chunk
        # Append this chunk to an audio file or process as needed
        print("Received an audio chunk")

    @sio.on('some_event')
    def handle_some_event(data):
        # This will broadcast the message to all clients except the sender
        socketio.emit('someEvent', data, broadcast=True)

    @sio.on('stream-speak')
    def handle_text_data(json):
        text = json['text']

        asyncio.get_event_loop().run_until_complete(
            websockets.connect(
                lambda ws: text_to_speech(ws, text)
            )
        )
