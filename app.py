from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
import os
from dotenv import load_dotenv
from notion_client import Client
import json
from datetime import datetime
import re
from tabelog_scraper import scrape_tabelog
import aiconfigs

load_dotenv()
app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # For flash messages
notion = Client(auth=os.getenv("NOTION_TOKEN"))
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")

def validate_url(url):
    """Validate URL format"""
    return url.startswith("https://tabelog.com/en/")

def create_notion_entry(link_url, notes, latitude, longitude):
    """Create a new entry in Notion with Tabelog data"""
    try:
        database_id = os.getenv("NOTION_DATABASE_ID")
        if not database_id:
            return False, "Database ID not configured"
        
        # Scrape Tabelog data if it's a Tabelog URL
        tabelog_data = None
        if "tabelog.com" in link_url:
            tabelog_data = scrape_tabelog(link_url)
            print("tabelog_data: ", tabelog_data)
        
        # Prepare properties for Notion
        properties = {
            "Link": {
                "url": link_url
            },
            "Notes": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": notes
                        }
                    }
                ]
            },
            "Date": {
                "date": {
                    "start": datetime.now().isoformat()
                }
            }
        }

        if latitude and longitude:
            properties["Latitude"] = {
                "number": latitude
            }
            properties["Longitude"] = {
                "number": longitude
            }
        
        # Add Tabelog data properties if available
        # tricky part cuz of notion api. tabelog property has name but notion 
        if tabelog_data:
            if tabelog_data.get("name"):
                properties["Name"] = {
                    "title": [
                        {
                            "type": "text",
                            "text": {
                                "content": tabelog_data["name"]
                            }
                        }
                    ]
                }
            
            if tabelog_data.get("rating"):
                properties["Rating"] = {
                    "number": tabelog_data["rating"]
                }
            
            if tabelog_data.get("categories"):
                # Join categories into a single string for rich_text
                categories_text = ", ".join(tabelog_data["categories"])
                properties["Category"] = {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": categories_text
                            }
                        }
                    ]
                }
            
            if tabelog_data.get("address"):
                properties["Address"] = {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": tabelog_data["address"]
                            }
                        }
                    ]
                }
        # Create page in Notion
        new_page = notion.pages.create(
            parent={"database_id": database_id},
            properties=properties
        )
        
        return True, "Entry saved successfully!"
    
    except Exception as e:
        return False, f"Error saving entry: {str(e)}"

def get_notion_entries():
    """Get entries from Notion database with Tabelog data"""
    try:
        database_id = os.getenv("NOTION_DATABASE_ID")
        if not database_id:
            return []
        
        response = notion.databases.query(database_id=database_id)
        
        entries = []
        for page in response.get("results", []):
            entry = {
                "id": page["id"],
                "title": "",
                "url": page["url"],
                "content": "",
                "created_time": page.get("created_time", ""),
                "tabelog_data": {},
                # "latitude": "",
                # "longitude": "",
            }
            
            # Extract Link property (URL)
            if "properties" in page and "Link" in page["properties"]:
                link_prop = page["properties"]["Link"]
                if link_prop["type"] == "url" and link_prop["url"]:
                    entry["title"] = link_prop["url"]
                    entry["url"] = link_prop["url"]
            
            # Extract Notes property (rich_text)
            if "properties" in page and "Notes" in page["properties"]:
                notes_prop = page["properties"]["Notes"]
                if notes_prop["type"] == "rich_text" and notes_prop["rich_text"]:
                    entry["content"] = notes_prop["rich_text"][0]["plain_text"]
            
            # Extract Date property (date type)
            if "properties" in page and "Date" in page["properties"]:
                date_prop = page["properties"]["Date"]
                if date_prop["type"] == "date" and date_prop["date"]:
                    entry["date"] = date_prop["date"]["start"]
            
            # Extract Tabelog data from Notion properties
            tabelog_data = {}
            
            # Restaurant Name (title type)
            if "properties" in page and "Name" in page["properties"]:
                name_prop = page["properties"]["Name"]
                if name_prop["type"] == "title" and name_prop["title"]:
                    tabelog_data["name"] = name_prop["title"][0]["plain_text"]
            
            # Rating
            if "properties" in page and "Rating" in page["properties"]:
                rating_prop = page["properties"]["Rating"]
                if rating_prop["type"] == "number" and rating_prop["number"] is not None:
                    tabelog_data["rating"] = rating_prop["number"]
            
            # Categories (rich_text type)
            if "properties" in page and "Category" in page["properties"]:
                category_prop = page["properties"]["Category"]
                if category_prop["type"] == "rich_text" and category_prop["rich_text"]:
                    categories_text = category_prop["rich_text"][0]["plain_text"]
                    # Split the comma-separated categories back into a list
                    tabelog_data["categories"] = [cat.strip() for cat in categories_text.split(",")]
            
            # Address
            if "properties" in page and "Address" in page["properties"]:
                address_prop = page["properties"]["Address"]
                if address_prop["type"] == "rich_text" and address_prop["rich_text"]:
                    tabelog_data["address"] = address_prop["rich_text"][0]["plain_text"]
    
            entry["tabelog_data"] = tabelog_data    
            entries.append(entry)
        
        return entries
    
    except Exception as e:
        print(f"Error getting entries: {e}")
        return []

@app.route('/')
def index():
    """Main page with form and entries"""
    entries = get_notion_entries()
    return render_template('python_frontend.html', entries=entries)

@app.route('/add_entry', methods=['POST'])
def add_entry():
    """Handle form submission"""
    link_url = request.form.get('link_url', '').strip()
    notes = request.form.get('notes', '').strip()
    
    # Validation
    if not link_url or not notes:
        flash('Please fill in both link and notes!', 'error')
        return redirect(url_for('index'))
    
    if not validate_url(link_url):
        flash('Please enter a valid Tabelog URL!', 'error')
        return redirect(url_for('index'))
    
    # once url is validated, need to parse coordinates from url
    ai_response = aiconfigs.get_ai_response(link_url)
    print("ai_response: ", ai_response)
    parsed_coordinates = aiconfigs.parse_coordinates(ai_response["response"])
    latitude = float(parsed_coordinates["latitude"]) if parsed_coordinates else None
    longitude = float(parsed_coordinates["longitude"]) if parsed_coordinates else None
    
    # Save to Notion with Tabelog data
    success, message = create_notion_entry(link_url, notes, latitude, longitude)
    
    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
    
    return redirect(url_for('index'))

@app.route('/delete_entry/<entry_id>')
def delete_entry(entry_id):
    """Delete an entry"""
    try:
        # TO DO: are archived entries deleted?
        notion.pages.update(entry_id, archived=True)
        flash('Entry deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting entry: {str(e)}', 'error')
    
    return redirect(url_for('index'))

@app.route('/api/debug/database')
def debug_database():
    """Debug endpoint to see database properties"""
    try:
        database_id = os.getenv("NOTION_DATABASE_ID")
        if not database_id:
            return jsonify({"error": "Database ID not configured"}), 400
        
        database = notion.databases.retrieve(database_id)
        properties = database.get("properties", {})
        
        property_info = {}
        for prop_name, prop_value in properties.items():
            property_info[prop_name] = {
                "type": prop_value["type"],
                "id": prop_value.get("id", "N/A")
            }
        
        return jsonify({
            "database_id": database_id,
            "database_title": database.get("title", []),
            "properties": property_info
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("🌸 Starting Sweetski Python Frontend App...")
    print("🌐 Open http://localhost:5002 in your browser")
    print("✨ No JavaScript required - pure Python backend!")
    print("-" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5002) 