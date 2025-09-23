"Unit tests for the travel app"
import json
import unittest
from unittest.mock import patch
import app

FAKE_CITY1 = {
    "CityName": "Test-city-1",
    "CountryCode": "TC1",
    "CountryName": "TestCountry1",
    "TopThingsToDo": ["TODO1", "TODO2"]
}

FAKE_CITY2 = {
    "CityName": "Test-city-2",
    "CountryCode": "TC2",
    "CountryName": "TestCountry2",
    "TopThingsToDo": ["TODO1", "TODO2"]
}

FAKE_KB_RESPONSE = {
    "citations": [
        {
            "generatedResponsePart": {
                "textResponsePart": {
                    "text": "Answer text"
                }
            },
            "retrievedReferences": [
                {
                    "content": {
                        "text": "Review text"
                    },
                    "location": {
                        "s3Location": {
                            "uri": "s3://fake-bucket/location_1.txt"
                        }
                    },
                    "metadata": {
                        "Stars": 4,
                    }
                }
            ]
        }
    ]
}

def mock_cities_scan():
    "The cities returned from the database"
    return {"Items" : [ FAKE_CITY1, FAKE_CITY2 ]}

#  pylint: disable=invalid-name, unused-argument
def mock_cities_query(KeyConditionExpression):
    "Query for a single city"
    return {"Items" : [ FAKE_CITY1 ]}

#  pylint: disable=invalid-name, unused-argument
def mock_cities_query_no_results(KeyConditionExpression):
    "Query for a single city"
    return {"Items" : [ ]}

def mock_invoke_model_with_response_stream(body, modelId):
    "Mock the chunked responsed from from the LLM"
    return {
        "body": [
            { "chunk" : { "bytes": b"{ \"outputText\" : \"response text\"}" }}
        ]
    }

def mock_invoke_model(body, modelId):
    "Mock the standard response from the LLM"

    # Mock response that matches Nova Lite format
    mock_response_body = {
        "output": {
            "message": {
                "content": [
                    {"text": "response text"}
                ]
            }
        }
    }

    # Create a mock response object with a read() method
    class MockResponse:  # pylint: disable=too-few-public-methods
        "Mock response object for Bedrock API"
        def read(self):
            "Return JSON response as bytes"
            return json.dumps(mock_response_body).encode('utf-8')

    return {
        "body": MockResponse()
    }

#  pylint: disable=redefined-builtin, unused-argument
def mock_retrieve_and_generate(input, retrieveAndGenerateConfiguration):
    "Mock the KB response"
    return FAKE_KB_RESPONSE

#  pylint: disable=redefined-builtin, unused-argument
def mock_retrieve_and_generate_no_citations(input, retrieveAndGenerateConfiguration):
    "Mock the KB response"
    return {
        "citations": []
    }

class FlaskTestCase(unittest.TestCase):
    "Test Fixture"

    @patch('app.cities_table.scan', mock_cities_scan)
    def test_homepage(self):
        "Test the homepage has results from the data store"
        tester = app.app.test_client(self)
        response = tester.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Test-city-1, TestCountry', response.data.decode('utf-8'))
        self.assertIn('Test-city-2, TestCountry2', response.data.decode('utf-8'))

    @patch('app.cities_table.query', mock_cities_query)
    def test_city_detail_page(self):
        "Test a details page has todo, itinerary, and reviews"
        tester = app.app.test_client(self)
        response = tester.get('/city/Test-city-1')
        self.assertIn('Itinerary Planner Test-city-1', response.data.decode('utf-8'))
        self.assertEqual(response.status_code, 200)


    @patch('app.cities_table.query', mock_cities_query_no_results)
    def test_city_detail_404(self):
        "Test empty results from the data store"
        tester = app.app.test_client(self)
        response = tester.get('/city/this-doesnt-exist')
        self.assertEqual(response.status_code, 404)


    @patch('app.cities_table.query', mock_cities_query)
    @patch('app.bedrock.invoke_model', mock_invoke_model)
    def test_suggestions(self):
        "Test the suggestions route"
        tester = app.app.test_client(self)
        response = tester.post('/suggestions/Test-city-1', data={
            'days': '2',
            'car': 'on',
            'children': 'on',
            'interests': ['nightlife', 'museums']
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"response text", response.data)

    @patch('app.cities_table.query', mock_cities_query)
    @patch('app.bedrock_agent.retrieve_and_generate', mock_retrieve_and_generate)
    def test_knowledgebase(self):
        "Test the suggestions route"
        tester = app.app.test_client(self)
        response = tester.post('/kb/Test-city-1', data={
            'q': '0'
        })
        self.assertEqual("Answer text<sup>[1]</sup>", response.json['Output'])
        self.assertEqual("⭐️⭐️⭐️⭐️ Review text", response.json['Reviews'][0])

    @patch('app.cities_table.query', mock_cities_query)
    @patch('app.bedrock_agent.retrieve_and_generate', mock_retrieve_and_generate_no_citations)
    def test_knowledgebase_no_citations(self):
        "Ensure the correct response when KB has no citations"
        tester = app.app.test_client(self)
        response = tester.post('/kb/Test-city-1', data={
            'q': '0'
        })
        self.assertEqual(
            "Sorry, I don't have enough reviews for this location.",
            response.json['Output']
        )
