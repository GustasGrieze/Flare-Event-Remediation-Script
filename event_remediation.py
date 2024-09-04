import requests
import logging
import json
from config import sprints
from APIKEY import api_key

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

API_KEY = api_key
TOKEN_GEN_URL = "https://api.flare.systems/tokens/generate"
QUERY_URL = "https://api.flare.io/firework/v2/search/"

class Member:
    def __init__(self, name, assets_to_monitor, categories, severities, reporting_email, enabled):
        self.name = name
        self.assets_to_monitor = assets_to_monitor
        self.categories = categories
        self.severities = severities
        self.reporting_email = reporting_email
        self.enabled = enabled
        self.events = object
        self.emails_to_send = []

def run_sprints():
    logging.info("Starting the sprint execution")

    members = []
    for company in sprints:
        members.append(Member(company['name'], company['assets_to_monitor'], company['categories'],
                              company['severities'], company['reporting_email'], company['enabled']))

    token = get_temporary_token()
    if not token:
        logging.error("Cannot get a temporary token. Exiting.")
        return

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    for member in members:
        if not member.enabled:
            logging.info(f"Skipping disabled member: {member.name}")
            continue
        logging.info(f"Processing member: {member.name}")
        for asset in member.assets_to_monitor:
            logging.info(f"Processing asset: {asset} for member: {member.name}")
            fetch_events(asset, member.categories, member.severities, headers)

    logging.info("Sprint execution completed")

def fetch_events(asset, categories, severities, headers):
    search_after = ""
    post_data_dict = {
        "query": asset,
        "types[]": categories,
        "risks[]": severities,
        "has_notes": False,
        "has_modified_risk_score": False,
        "event_actions[]": [],
        "lite": True,
        "size": 50000, 
        "sort_by": "created",
        "order": "desc",
        "fetch_type": "results",
        "force_materialized": False,
        "use_global_policies": True,
        "time_zone": "Europe/Vilnius"
    }

    for _ in range(15):
        logging.info(f"Post data: {post_data_dict}")
        response = requests.post(QUERY_URL, json=post_data_dict, headers=headers)
        logging.info(f"HTTP Status Code: {response.status_code}")
        if response.status_code != 200:
            logging.error(f"Error with API request: {response.status_code} - {response.text}")
            break

        data = response.json()
        logging.info(f"Response data: {json.dumps(data, indent=2)}")
        
        # Log total number of hits found
        total_hits = data.get("search_info", {}).get("nb_hits", None)
        logging.info(f"Total hits for asset {asset}: {total_hits}")

        events = data.get('items')
        if events:
            for event in events:
                logging.info(f"Resolving event: {event['uid']} for asset: {asset}")
                resolve_alert(event['uid'], headers['Authorization'][7:])
        
        search_after = data.get("search_after")
        if search_after:
            post_data_dict["search_after"] = search_after
            logging.info("Continuing to next set of events with search_after token")
        else:
            logging.info("No more events found. Proceeding to next asset.")
            break

def get_temporary_token() -> str:
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Basic {API_KEY}',
    }
    payload = json.dumps({
        "tenant_id": 169258
    })
    try:
        response = requests.request("POST", TOKEN_GEN_URL, headers=headers, data=payload)
        response.raise_for_status()
        data = json.loads(response.content)
        logging.info("Temporary token received successfully")
        return data.get("token")
    except requests.exceptions.RequestException as e:
        logging.warning(f"Error making the request: {e}")
        return ""
    except json.JSONDecodeError as e:
        logging.warning(f"Error decoding JSON: {e}")
        return ""

def resolve_alert(uid: str, token: str) -> int:
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}'
    }
    url = f"https://api.flare.io/firework/v2/activities/{uid}/user_metadata/remediated"
    data = {
        'identifier_id': 0,
        "is_remediated": True
    }
    logging.info(f"Closing and resolving alert with UID: {uid}")
    try:
        response = requests.put(url, json=data, headers=headers)
        response.raise_for_status()
        logging.info(f"Successfully resolved alert with UID: {uid}")
    except requests.exceptions.RequestException as e:
        logging.warning(f"Failed to resolve alert with UID: {uid}, error: {e}")
    return 0

def main():
    logging.info("Starting main function")
    run_sprints()
    logging.info("Main function completed")

if __name__ == "__main__":
    main()