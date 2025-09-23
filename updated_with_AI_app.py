"City Info App"
from collections import OrderedDict
import json
import os
from urllib.parse import urlparse
import boto3
from botocore.exceptions import ClientError
from flask import Flask, render_template, request, render_template_string

app = Flask(__name__)
dynamodb = boto3.resource("dynamodb")
cities_table = dynamodb.Table("Cities")

bedrock = boto3.client(service_name="bedrock-runtime")
bedrock_agent = boto3.client("bedrock-agent-runtime")
MODEL_ID = "amazon.nova-lite-v1:0"

KB_PROMPTS = [
    "What activities are popular in the reviews?",
    "What food do the reviews recommend?",
    "What did reviewers like the most?",
    "What are the recommended neighborhoods?",
]


def relative_url(endpoint):
    "Build a relative URL from an absolute path"
    start_dir = os.path.dirname(urlparse(request.url).path)
    relative_path = os.path.relpath(endpoint, start=start_dir)
    return relative_path


# Register the custom filters with Flask
app.jinja_env.filters["relative_url"] = relative_url


def load_cities():
    "Load all the cities from the data store"
    results = []
    response = cities_table.scan()
    for item in response["Items"]:
        city = {
            "Name": item["CityName"],
            "CountryCode": item["CountryCode"],
            "CountryName": item["CountryName"],
            "TopThingsToDo": item["TopThingsToDo"],
        }
        results.append(city)
    return results


def load_city(name):
    "Load a city name and country code"
    response = cities_table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key("CityName").eq(name)
    )
    if response["Items"]:
        item = response["Items"][0]
        return {
            "Name": item["CityName"],
            "CountryCode": item["CountryCode"],
            "CountryName": item["CountryName"],
            "TopThingsToDo": item["TopThingsToDo"],
        }
    return None


@app.route("/")
def home_route():
    "Select a city homepage"
    cities = load_cities()
    return render_template("index.html", cities=cities)


@app.route("/city/<name>")
def city_route(name):
    "Render a city page"
    city = load_city(name)
    if not city:
        return render_template("404.html"), 404

    return render_template("city.html", city=city, kb_prompts=KB_PROMPTS)


@app.route("/suggestions/<name>", methods=["POST"])
def suggestions_route(name):
    "Get suggestions for a city"
    parameters = {
        "days": request.form["days"],
        "children": "children" in request.form,
        "car": "car" in request.form,
        "interests": request.form.getlist("interests"),
    }
    prompt_template = """
Give me an itinerary{% if parameters.days %} for {{parameters.days}} 
days{% endif %} for {{city.Name}}, {{city.CountryName}}{% if parameters.children %}, with 
children{% endif %}. 
{% if parameters.car %}I have a car. {% endif %}
{% if parameters.interests %}
I am interested in {{ parameters.interests|join(', ') }}. 
{% endif %}
Consider these things to do {{ city.TopThingsToDo|join(', ') }}.
""".replace(
        "\n", ""
    )
    city = load_city(name)
    prompt = render_template_string(prompt_template, city=city, parameters=parameters)

    # Use the format that worked in the test
    try:
        # Nova Lite format with content as an array of objects with text field
        request_body = {"messages": [{"role": "user", "content": [{"text": prompt}]}]}

        response = bedrock.invoke_model(modelId=MODEL_ID, body=json.dumps(request_body))

        # Parse the response
        response_body = json.loads(response["body"].read())

        # Extract the response content based on the format we saw in the test
        if "output" in response_body and "message" in response_body["output"]:
            content = response_body["output"]["message"].get("content", [])
            result = "".join(item.get("text", "") for item in content)
        else:
            # Fallback to return the whole response
            result = f"Unexpected response format: {response_body}"

        # Return the formatted result
        return f"PROMPT&gt; {prompt}<br>----------<br>{result}"

    except (ClientError, KeyError, ValueError) as e:
        error_msg = str(e)
        return f"Error: {error_msg}"


@app.route("/kb/<name>", methods=["POST"])
def kb_route(name):
    "Answer KB prompts about a city"
    city = load_city(name)

    template = """
A chat between a curious User and an artificial intelligence Bot. The Bot
gives helpful, detailed, and polite answers to the User's questions.

In this session, the model has access to search results and a user's question,
your job is to answer the user's question using only information from the
search results.

Model Instructions:
- You should provide concise answer to simple questions when the answer is
directly contained in search results, but when comes to yes/no question,
provide some details.
- In case the question requires multi-hop reasoning, you should find relevant
information from search results and summarize the answer based on relevant
information with logical reasoning.
- If the search results do not contain information that can answer the
question, please state that you could not find an exact answer to the question,
and if search results are completely irrelevant, say that you could not find an
exact answer, then summarize search results.
- $output_format_instructions$
- DO NOT USE INFORMATION THAT IS NOT IN SEARCH RESULTS!

User: $query$ Bot:
Resource: Search Results: $search_results$ Bot:
"""

    q_index = int(request.form["q"])
    prompt = KB_PROMPTS[q_index]

    params = {
        "input": {
            "text": prompt,
        },
        "retrieveAndGenerateConfiguration": {
            "type": "KNOWLEDGE_BASE",
            "knowledgeBaseConfiguration": {
                "modelArn": MODEL_ID,
                "retrievalConfiguration": {
                    "vectorSearchConfiguration": {
                        "filter": {"equals": {"key": "City", "value": city["Name"]}}
                    }
                },
                "knowledgeBaseId": os.getenv("KNOWLEDGE_BASE_ID"),
                "generationConfiguration": {
                    "promptTemplate": {"textPromptTemplate": template}
                },
            },
        },
    }

    try:
        response = bedrock_agent.retrieve_and_generate(**params)
    except ClientError as e:  # pragma: no cover
        if e.response["Error"]["Code"] == "ThrottlingException":
            return {"Output": "Please wait 30 seconds and try again."}
        raise

    full_output = ""
    refs = OrderedDict()
    if len(response["citations"]) == 0:
        return {"Output": "Sorry, I don't have enough reviews for this location."}

    for c in response["citations"]:
        full_output += c["generatedResponsePart"]["textResponsePart"]["text"]
        for r in c["retrievedReferences"]:
            if r["location"]["s3Location"]["uri"] not in refs:
                stars = "⭐️" * int(r["metadata"]["Stars"])
                refs[r["location"]["s3Location"]["uri"]] = (
                    stars + " " + r["content"]["text"]
                )
            full_output += f"<sup>[{len(refs.keys())}]</sup>"

    return {"Output": full_output, "Reviews": list(refs.values())}


@app.route("/check_models")
def check_models():
    "Check available models"
    try:
        # Create a regular bedrock client (not bedrock-runtime)
        bedrock_client = boto3.client("bedrock")

        # Use the bedrock client to list models
        response = bedrock_client.list_foundation_models()
        models = response.get("modelSummaries", [])

        model_list = "<h3>Available Models:</h3><ul>"
        for model in models:
            model_id = model.get("modelId", "Unknown")
            model_list += f"<li>{model_id}</li>"
        model_list += "</ul>"

        # Print to console for debugging
        print("\n" + "=" * 50)
        print("Available Models:")
        for model in models:
            print(f"- {model.get('modelId', 'Unknown')}")
        print("=" * 50 + "\n")

        return model_list
    except (ClientError, KeyError) as e:
        error_msg = f"Error listing models: {str(e)}"
        print(error_msg)
        return error_msg


@app.route("/test_model", methods=["GET", "POST"])
def test_model():
    "Test different model formats"
    if request.method == "GET":
        # Return a form to test different formats
        return """
        <h1>Test Nova Lite Model</h1>
        <form method="POST">
            <label>JSON Request Body:</label><br>
            <textarea name="request_body" rows="10" cols="80">{"messages": [{"role": "user", "content": "Hello, world!"}]}</textarea><br>
            <input type="submit" value="Test">
        </form>
        """
    # Process the form submission
    try:
        request_body = request.form["request_body"]

        # Invoke the model with the provided request body
        response = bedrock.invoke_model(modelId=MODEL_ID, body=request_body)

        # Parse and return the response
        response_body = json.loads(response["body"].read())
        return f"<h2>Success!</h2><pre>{json.dumps(response_body, indent=2)}</pre>"

    except (ClientError, KeyError, ValueError) as e:
        return f"<h2>Error</h2><p>{str(e)}</p>"