import os
import sys
import requests
import re
from pyairtable import Api
from dotenv import load_dotenv
from datetime import datetime, timedelta
import urllib.parse
import time

def download_image(url, save_path):
    """Download an image from a URL and save it locally."""
    try:
        response = requests.get(url, stream=True, timeout=10)
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            return True
    except Exception as e:
        print(f"Error downloading image {url}: {e}")
    return False

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
    """Fetch a thumbnail image of the plant from Wikipedia API.
    Returns None gracefully if no image is found."""
    try:
        time.sleep(1) # Be nice to Wikipedia API
        headers = {'User-Agent': 'TRMNL-Water-Me-Please/1.0'}
        # Search for the page title first
        encoded_name = urllib.parse.quote(f"{plant_name} plant")
        search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={encoded_name}&utf8=&format=json"
        response = requests.get(search_url, headers=headers, timeout=10)
        
        if response.status_code != 200 or not response.text.strip():
            print(f"  ℹ️  No Wikipedia result for '{plant_name}' (no response)")
            return None
        
        data = response.json()
        
        if not data.get('query', {}).get('search'):
            print(f"  ℹ️  No Wikipedia result for '{plant_name}'")
            return None
            
        title = data['query']['search'][0]['title']
        
        # Get the main image for the title
        image_url = f"https://en.wikipedia.org/w/api.php?action=query&titles={title}&prop=pageimages&format=json&pithumbsize=500"
        response = requests.get(image_url, headers=headers, timeout=10)
        
        if response.status_code != 200 or not response.text.strip():
            return None
        
        data = response.json()
        
        pages = data.get('query', {}).get('pages', {})
        for page_id in pages:
            if 'thumbnail' in pages[page_id]:
                return pages[page_id]['thumbnail']['source']
        
        print(f"  ℹ️  No image found on Wikipedia for '{plant_name}'")
    except (ValueError, KeyError):
        # JSON decode errors or missing keys — plant simply has no Wikipedia image
        print(f"  ℹ️  Could not parse Wikipedia response for '{plant_name}' (skipping)")
    except requests.exceptions.RequestException:
        # Network timeout or connection error
        print(f"  ℹ️  Wikipedia lookup timed out for '{plant_name}' (skipping)")
    except Exception as e:
        print(f"  ℹ️  Unexpected issue looking up '{plant_name}': {e}")
        
    return None

# Load environment variables from .env file
load_dotenv()

# Configuration
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = os.getenv("AIRTABLE_TABLE_NAME")
TRMNL_WEBHOOK_URL = os.getenv("TRMNL_WEBHOOK_URL")
TRMNL_DEVICE_API_KEY = os.getenv("TRMNL_DEVICE_API_KEY")
TRMNL_PLUGIN_NAME = os.getenv("TRMNL_PLUGIN_NAME", "water") # Pattern to match in current image_name or plugin identifier

def is_plant_plugin_active():
    """Verify if the Plant Watering plugin is currently displayed on TRMNL screen."""
    if not TRMNL_DEVICE_API_KEY:
        # If device API key is not configured, skip screen check safely
        return True
        
    try:
        url = "https://trmnl.com/api/display/current"
        headers = {"access-token": TRMNL_DEVICE_API_KEY}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            image_name = data.get("image_name", "")
            if TRMNL_PLUGIN_NAME.lower() in image_name.lower():
                print(f"  ✅ Screen Context Verified: Active screen '{image_name}' matches plant plugin.")
                return True
            else:
                print(f"  ℹ️  Screen Context Check: Active screen '{image_name}' is NOT the plant plugin. Skipping button action.")
                print(f"  🔍 DEBUG: TRMNL API raw response data: {data}")
                return False
        else:
            print(f"  ⚠️ Could not query TRMNL device state (HTTP {response.status_code}). Proceeding safely.")
            return True
    except Exception as e:
        print(f"  ⚠️ Error checking TRMNL device screen state: {e}. Proceeding safely.")
        return True

def main():
    # 0. Check for CLI arguments or environment variables
    is_flic_trigger = (
        "--water-all" in sys.argv
        or os.getenv("TRIGGER_TYPE") == "flic"
        or os.getenv("EVENT_TYPE") in ["flic_water_all", "flic_water_all_dev"]
        or os.getenv("WATER_ALL") == "true"
    )

    # 1. Validate configuration
    if not all([AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME]):
        print("Error: Missing required Airtable environment variables. Please check your .env file.")
        return

    print(f"Fetching data from Airtable base '{AIRTABLE_BASE_ID}', table '{AIRTABLE_TABLE_NAME}'...")

    # 2. Fetch data from Airtable
    # Ensure assets directory exists
    assets_dir = "assets"
    if not os.path.exists(assets_dir):
        os.makedirs(assets_dir)

    api = Api(AIRTABLE_API_KEY)
    table = api.table(AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME)
    
    try:
        records = table.all()
    except Exception as e:
        print(f"Failed to fetch from Airtable: {e}")
        return

    # --- Flic Trigger: Mark all currently due plants as watered ---
    if is_flic_trigger:
        print("⚡ Flic Button Trigger Detected: Checking screen context...")
        if not is_plant_plugin_active():
            print("ℹ️ Button press ignored because Plant Dashboard is not currently on the TRMNL screen.")
        else:
            print("Processing 'Water All Due Plants'...")
            flic_updates = []
            today_str = datetime.now().strftime("%Y-%m-%d")
            today_date = datetime.now().date()

            for record in records:
                fields = record.get("fields", {})
                next_watering = fields.get("Next Watering Date", "N/A")
                is_due = False
                if next_watering != "N/A":
                    try:
                        next_dt = datetime.strptime(next_watering, "%Y-%m-%d").date()
                        if (next_dt - today_date).days <= 0:
                            is_due = True
                    except ValueError:
                        pass

                if is_due:
                    plant_name = fields.get("Plant Name", "Unknown")
                    print(f"  -> Marking due plant as watered: {plant_name}")
                    freq_str = fields.get("Frequency")
                    days = parse_frequency(freq_str) or 7 # Default to 7 days if frequency unspecified

                    next_dt = datetime.now() + timedelta(days=days)
                    flic_updates.append({
                        "id": record["id"],
                        "fields": {
                            "Last Watered": today_str,
                            "Next Watering Date": next_dt.strftime("%Y-%m-%d"),
                            "Watered ?": False
                        }
                    })

            if flic_updates:
                print(f"Batch updating {len(flic_updates)} due plants in Airtable...")
                try:
                    table.batch_update(flic_updates)
                    # Re-fetch records to reflect updates for TRMNL rendering
                    records = table.all()
                    print("✅ Successfully marked all due plants as watered in Airtable!")
                except Exception as e:
                    print(f"Failed to update Airtable for Flic trigger: {e}")
            else:
                print("ℹ️  No plants currently due for watering. Duplicate press ignored safely.")

    # --- Maintenance: Handle manual "Watered ?" Checkboxes ---
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
        
        # Calculate if due today or overdue (missed watering)
        is_starving = False
        if next_watering != "N/A":
            try:
                # Assuming YYYY-MM-DD format from Airtable
                next_date = datetime.strptime(next_watering, "%Y-%m-%d").date()
                today = datetime.now().date()
                if (next_date - today).days <= 0:
                    is_starving = True
            except ValueError:
                pass
        
        if is_starving:
            # Fetch plant image ONLY for thirsty plants: 1. Airtable, 2. Wikipedia, 3. None
            remote_url = None
            if plant_pic and isinstance(plant_pic, list) and len(plant_pic) > 0:
                remote_url = plant_pic[0].get("url")
                
            if not remote_url and plant_name != "Unknown":
                remote_url = get_plant_image(plant_name)

            # Local Image Hosting Logic (Always refresh to ensure latest photo from Airtable)
            image_url = None
            if remote_url:
                record_id = record.get("id", "unknown")
                local_filename = f"{record_id}.jpg"
                local_path = os.path.join(assets_dir, local_filename)
                
                # Always download and overwrite to ensure we have the latest user photo
                if download_image(remote_url, local_path):
                    # Use raw GitHub URL for the final payload
                    image_url = f"https://raw.githubusercontent.com/damiththa/water-me-please/main/assets/{local_filename}"

            # Build minified item for TRMNL
            formatted_date = "N/A"
            is_overdue = False
            if next_watering != "N/A":
                try:
                    d = datetime.strptime(next_watering, "%Y-%m-%d")
                    formatted_date = f"{d.month}/{d.day}"
                    is_overdue = d.date() < datetime.now().date()
                except:
                    formatted_date = next_watering[-5:].replace("-", "/")

            item_data = {
                "n": plant_name[:20],  # n = name (increased from 14 to 20)
                "x": formatted_date,   # x = next watering date
                "i": image_url,        # i = image_url
                "_raw_date": next_watering # Temp sorting key
            }
            if is_overdue:
                item_data["o"] = True  # o = overdue flag
            items.append(item_data)
        
    # Sort items by oldest next_watering date first
    items.sort(key=lambda x: x.get("_raw_date", "9999-12-31"))
    
    # Remove the temporary sort key and limit to 8 items since TRMNL shows max 8
    for item in items:
        item.pop("_raw_date", None)
    items = items[:8]
    
    # 4. Final Payload
    import json
    payload = {"merge_variables": {"items": items}}
    
    print(f"\nPayload Size: {len(json.dumps(payload))} bytes (Limit: 2048)")
    print(f"Sending payload to TRMNL Webhook (contains {len(items)} plants)...")

    if not TRMNL_WEBHOOK_URL or "your_uuid_here" in TRMNL_WEBHOOK_URL:
        print("\nSkipping TRMNL Webhook since TRMNL_WEBHOOK_URL is not configured.")
        return

    try:
        response = requests.post(
            TRMNL_WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        print("Successfully updated TRMNL plugin!")
    except requests.exceptions.RequestException as e:
        print(f"Failed to update TRMNL plugin. Error: {e}")

if __name__ == "__main__":
    main()

