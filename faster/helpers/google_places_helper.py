"""Helper functions for interacting with the Google Places API."""
import json
from pathlib import Path

import requests


def get_google_places_api_key(creds_path="../../creds.json"):
    """Loads the Google Places API key from a credentials file.

    Args:
        creds_path (str): The path to the credentials file.

    Returns:
        str: The Google Places API key.

    Raises:
        FileNotFoundError: If the credentials file is not found.
    """
    creds_file = Path(creds_path)
    if not creds_file.exists():
        raise FileNotFoundError(f"Credentials file not found: {creds_path}")
    with open(creds_file) as f:
        creds = json.load(f)
    return creds.get("google_places_api_key")


# Query Google Places API for merchant info
def get_place_types(merchant_name, api_key=None):
    """Look up a merchant name using Google Places API and,
    return place types/categories.

    Args:
        merchant_name (str): The merchant or place name to look up.
        api_key (str): Google Places API key. If None, loads from creds.json.

    Returns:
        list: List of place types (categories) or empty list if not found.
    """
    if api_key is None:
        api_key = get_google_places_api_key()
    endpoint = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
    params = {
        "input": merchant_name,
        "inputtype": "textquery",
        "fields": "place_id",
        "key": api_key,
    }
    resp = requests.get(endpoint, params=params, timeout=5)
    data = resp.json()
    candidates = data.get("candidates", [])
    if not candidates:
        return []
    place_id = candidates[0]["place_id"]
    # Now get details for the place
    details_endpoint = "https://maps.googleapis.com/maps/api/place/details/json"
    details_params = {"place_id": place_id, "fields": "type,name", "key": api_key}
    details_resp = requests.get(details_endpoint, params=details_params, timeout=5)
    details_data = details_resp.json()
    result = details_data.get("result", {})
    return result.get("types", [])


# print(get_place_types("Starbucks"))
