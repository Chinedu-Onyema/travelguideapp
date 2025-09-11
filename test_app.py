"Unit tests for the travel app" 

import unittest 

from unittest.mock import patch 

import app 

 

FAKE_CITY1 = { 

    "CityName": "Test-city-1", 

    "CountryCode": "TC1", 

    "CountryName": "TestCountry1", 

    "TopThingsToDo": ["TODO1", "TODO2"], 

    "Itinerary": "Day one\nDay two" 

} 

 

FAKE_CITY2 = { 

    "CityName": "Test-city-2", 

    "CountryCode": "TC2", 

    "CountryName": "TestCountry2", 

    "TopThingsToDo": ["TODO1", "TODO2"], 

    "Itinerary": "Day one\nDay two" 

} 

 

FAKE_REVIEW1 = { 

    "ReviewContent": "This is a review", 

    "Stars": 5 

} 

 

FAKE_REVIEW2 = { 

    "ReviewContent": "This is also a review", 

    "Stars": 4 

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

 

#  pylint: disable=invalid-name, unused-argument 

def mock_reviews_query(KeyConditionExpression): 

    "Query for city reviews" 

    return {"Items" : [ FAKE_REVIEW1, FAKE_REVIEW2 ]} 

 

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

    @patch('app.reviews_table.query', mock_reviews_query) 

    def test_city_detail_page(self): 

        "Test a details page has todo, itinerary, and reviews" 

        tester = app.app.test_client(self) 

        response = tester.get('/city/Test-city-1') 

        self.assertEqual(response.status_code, 200) 

        self.assertIn('<li>TODO1</li>', response.data.decode('utf-8')) 

        self.assertIn('<li>TODO2</li>', response.data.decode('utf-8')) 

        self.assertIn('Day one<br>Day two', response.data.decode('utf-8')) 

        self.assertIn('⭐️⭐️⭐️⭐️⭐️ This is a review', response.data.decode('utf-8')) 

        self.assertIn('⭐️⭐️⭐️⭐️ This is also a review', response.data.decode('utf-8')) 

 

    @patch('app.cities_table.query', mock_cities_query_no_results) 

    def test_city_detail_404(self): 

        "Test empty results from the data store" 

        # I'll finish this later 