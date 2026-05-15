import os
import requests
import re
from pyairtable import Api
from dotenv import load_dotenv
from datetime import datetime, timedelta
import urllib.parse
import time

def parse_frequency(freq_str):
    """Smart parse frequency strings like '7 days', '1 week', '14'"""
    if not freq_str:
        return None
    
    freq_str = str(freq_str).lower().strip()
    
    # Try to find a number
    match = re.search(r'(\d+)', freq_str)
    if not match:
        return None
    
    val = int(match.group(1))
    
    if 'week' in freq_str:
        return val * 7
    elif 'month' in freq_str:
        return val * 30 # Simple approximation
    else:
        return val # Default to days

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
        records = table.all()
    except Exception as e:
        print(f"Failed to fetch from Airtable: {e}")
        return

    # --- Maintenance: Handle "Watered ?" Checkboxes ---
    updates = []
    for record in records:
        fields = record.get("fields", {})
        if fields.get("Watered ?") is True:
            plant_name = fields.get("Plant Name", "Unknown")
            print(f"Maintenance: {plant_name} marked as watered. Updating dates...")
            
            # 1. Determine the "Last Watered" date
            # Use the hidden modified date if available, else today
            raw_hidden_date = fields.get("Watered Date Hidden")
            if raw_hidden_date:
                # Airtable modified time is ISO 8601 string (UTC)
                new_last_watered = raw_hidden_date[:10] # Just the date YYYY-MM-DD
            else:
                new_last_watered = datetime.now().strftime("%Y-%m-%d")
            
            # 2. Calculate "Next Watering Date"
            freq_str = fields.get("Frequency")
            days = parse_frequency(freq_str)
            
            update_fields = {
                "Last Watered": new_last_watered,
                "Watered ?": False
            }
            
            if days:
                last_dt = datetime.strptime(new_last_watered, "%Y-%m-%d")
                next_dt = last_dt + timedelta(days=days)
                update_fields["Next Watering Date"] = next_dt.strftime("%Y-%m-%d")
            
            updates.append({
                "id": record["id"],
                "fields": update_fields
            })
            
    if updates:
        print(f"Batch updating {len(updates)} records in Airtable...")
        try:
            table.batch_update(updates)
            # Re-fetch records to reflect updates for TRMNL rendering
            records = table.all()
        except Exception as e:
            print(f"Failed to update Airtable maintenance: {e}")

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
