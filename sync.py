import os
import requests
from pyairtable import Api
from dotenv import load_dotenv
from datetime import datetime
import urllib.parse
import time

def get_plant_image(plant_name):
    """Fetch a thumbnail image of the plant from Wikipedia API"""
    try:
        time.sleep(1) # Be nice to Wikipedia API
        headers = {'User-Agent': 'TRMNL-Water-Me-Please/1.0'}
        # Search for the page title first
        encoded_name = urllib.parse.quote(f"{plant_name} plant")
        search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={encoded_name}&utf8=&format=json"
        response = requests.get(search_url, headers=headers)
        data = response.json()
        
        if not data.get('query', {}).get('search'):
            return None
            
        title = data['query']['search'][0]['title']
        
        # Get the main image for the title
        image_url = f"https://en.wikipedia.org/w/api.php?action=query&titles={title}&prop=pageimages&format=json&pithumbsize=500"
        response = requests.get(image_url, headers=headers)
        data = response.json()
        
        pages = data.get('query', {}).get('pages', {})
        for page_id in pages:
            if 'thumbnail' in pages[page_id]:
                return pages[page_id]['thumbnail']['source']
    except Exception as e:
        print(f"Error fetching image for {plant_name}: {e}")
        
    return None

# Load environment variables from .env file
load_dotenv()

# Configuration
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME")
TRMNL_WEBHOOK_URL = os.getenv("TRMNL_WEBHOOK_URL")

def main():
    # 1. Validate configuration
    if not all([AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME]):
        print("Error: Missing required Airtable environment variables. Please check your .env file.")
        return

    print(f"Fetching data from Airtable base '{AIRTABLE_BASE_ID}', table '{AIRTABLE_TABLE_NAME}'...")

    # 2. Fetch data from Airtable
    api = Api(AIRTABLE_API_KEY)
    table = api.table(AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME)
    
    try:
        # You can customize this query. For example, sorting or using a specific view:
        # records = table.all(view="Grid view", sort=["Date"])
        records = table.all()
    except Exception as e:
        print(f"Failed to fetch from Airtable: {e}")
        return

    # 3. Transform the data for TRMNL
    # (Customize this logic based on your specific Airtable columns)
    items = []
    for record in records:
        fields = record.get("fields", {})
        
        # Extract plant watering data
        plant_name = fields.get("Plant Name", "Unknown")
        last_watered = fields.get("Last Watered", "N/A")
        next_watering = fields.get("Next Watering Date", "N/A")
        plant_pic = fields.get("Plant Pic") or fields.get("Plant pic")
        
        # Calculate if starving (<= 3 days left)
        is_starving = False
        if next_watering != "N/A":
            try:
                # Assuming YYYY-MM-DD format from Airtable
                next_date = datetime.strptime(next_watering, "%Y-%m-%d").date()
                today = datetime.now().date()
                if (next_date - today).days <= 3:
                    is_starving = True
            except ValueError:
                pass
        
        # Fetch plant image: 1. Airtable, 2. Wikipedia, 3. None
        image_url = None
        if plant_pic and isinstance(plant_pic, list) and len(plant_pic) > 0:
            image_url = plant_pic[0].get("url")
            
        if not image_url and plant_name != "Unknown":
            image_url = get_plant_image(plant_name)
        
        items.append({
            "plant_name": plant_name,
            "last_watered": last_watered,
            "next_watering": next_watering,
            "image_url": image_url,
            "is_starving": is_starving
        })
        
    # Filter for only starving plants
    items = [item for item in items if item["is_starving"]]
    
    # Sort items alphabetically by plant_name
    items.sort(key=lambda x: x["plant_name"].lower())
    
    # TRMNL expects the payload inside a "merge_variables" object
    payload = {
        "merge_variables": {
            "items": items
        }
    }

    # 4. Push to TRMNL
    import json
    print("\nGenerated Payload for TRMNL:")
    print(json.dumps(payload, indent=2))
    
    if not TRMNL_WEBHOOK_URL or "your_uuid_here" in TRMNL_WEBHOOK_URL:
        print("\nSkipping TRMNL Webhook since TRMNL_WEBHOOK_URL is not configured yet.")
        return

    print("\nSending payload to TRMNL...")
    try:
        response = requests.post(
            TRMNL_WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status() # Raise an exception for bad status codes
        print("Successfully updated TRMNL plugin!")
    except requests.exceptions.RequestException as e:
        print(f"Failed to update TRMNL plugin. Error: {e}")
        if response is not None:
            print(f"Response text: {response.text}")

if __name__ == "__main__":
    main()
