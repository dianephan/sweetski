from datetime import datetime
from notion_client import Client
import os
from tabelog_scraper import scrape_tabelog

class NotionService:
    def __init__(self, notion_token=None):
        self.notion = Client(auth=notion_token or os.getenv("NOTION_TOKEN"))
        self.database_id = os.getenv("NOTION_DATABASE_ID")

    def validate_url(self, url):
        """Validate URL format"""
        return url.startswith("https://tabelog.com/en/")

    def create_entry(self, link_url, notes, latitude=None, longitude=None, ai_model_info=None):
        """Create a new entry in Notion with Tabelog data"""
        try:
            if not self.database_id:
                return False, "Database ID not configured"
            
            # Scrape Tabelog data if it's a Tabelog URL
            tabelog_data = None
            if self.validate_url(link_url):
            # if "tabelog.com" in link_url:
                tabelog_data = scrape_tabelog(link_url)
            
            # Prepare properties for Notion
            properties = {
                "Link": {"url": link_url},
                "Notes": {
                    "rich_text": [{
                        "type": "text",
                        "text": {"content": notes}
                    }]
                },
                "Date": {
                    "date": {"start": datetime.now().isoformat()}
                }
            }

            if latitude and longitude:
                properties.update({
                    "Latitude": {"number": latitude},
                    "Longitude": {"number": longitude}
                })
            
            # Add Tabelog data properties if available
            if tabelog_data:
                if tabelog_data.get("name"):
                    properties["Name"] = {
                        "title": [{
                            "type": "text",
                            "text": {"content": tabelog_data["name"]}
                        }]
                    }
                
                if tabelog_data.get("rating"):
                    properties["Rating"] = {"number": tabelog_data["rating"]}
                
                if tabelog_data.get("categories"):
                    properties["Category"] = {
                        "rich_text": [{
                            "type": "text",
                            "text": {"content": ", ".join(tabelog_data["categories"])}
                        }]
                    }
                
                if tabelog_data.get("address"):
                    properties["Address"] = {
                        "rich_text": [{
                            "type": "text",
                            "text": {"content": tabelog_data["address"]}
                        }]
                    }

            if ai_model_info:
                properties["AI_Model"] = {
                    "rich_text": [{
                        "type": "text",
                        "text": {"content": ai_model_info["provider"]}
                    }]
                }

            # Create page in Notion
            self.notion.pages.create(
                parent={"database_id": self.database_id},
                properties=properties
            )
            
            return True, "Entry saved successfully!"
        
        except Exception as e:
            return False, f"Error saving entry: {str(e)}"

    def get_entries(self):
        """Get entries from Notion database with Tabelog data"""
        try:
            if not self.database_id:
                return []
            
            response = self.notion.databases.query(database_id=self.database_id)
            
            entries = []
            for page in response.get("results", []):
                entry = {
                    "id": page["id"],
                    "title": "",
                    "url": "",  # Tabelog URL
                    "notion_url": page["url"],  # Notion page URL
                    "content": "",
                    "created_time": page.get("created_time", ""),
                    "tabelog_data": {}
                }
                
                properties = page.get("properties", {})
                
                # Extract Link property (URL)
                if "Link" in properties:
                    link_prop = properties["Link"]
                    if link_prop["type"] == "url" and link_prop["url"]:
                        entry["title"] = link_prop["url"]
                        entry["url"] = link_prop["url"]
                
                # Extract Notes property (rich_text)
                if "Notes" in properties:
                    notes_prop = properties["Notes"]
                    if notes_prop["type"] == "rich_text" and notes_prop["rich_text"]:
                        entry["content"] = notes_prop["rich_text"][0]["plain_text"]
                
                # Extract Date property (date type)
                if "Date" in properties:
                    date_prop = properties["Date"]
                    if date_prop["type"] == "date" and date_prop["date"]:
                        entry["date"] = date_prop["date"]["start"]
                
                # Extract Tabelog data
                tabelog_data = {}
                
                # Restaurant Name (title type)
                if "Name" in properties:
                    name_prop = properties["Name"]
                    if name_prop["type"] == "title" and name_prop["title"]:
                        tabelog_data["name"] = name_prop["title"][0]["plain_text"]
                
                # Rating
                if "Rating" in properties:
                    rating_prop = properties["Rating"]
                    if rating_prop["type"] == "number" and rating_prop["number"] is not None:
                        tabelog_data["rating"] = rating_prop["number"]
                
                # Categories (rich_text type)
                if "Category" in properties:
                    category_prop = properties["Category"]
                    if category_prop["type"] == "rich_text" and category_prop["rich_text"]:
                        categories_text = category_prop["rich_text"][0]["plain_text"]
                        tabelog_data["categories"] = [cat.strip() for cat in categories_text.split(",")]
                
                # Address
                if "Address" in properties:
                    address_prop = properties["Address"]
                    if address_prop["type"] == "rich_text" and address_prop["rich_text"]:
                        tabelog_data["address"] = address_prop["rich_text"][0]["plain_text"]
                
                if "Latitude" in properties:
                    latitude_prop = properties["Latitude"]
                    if latitude_prop["type"] == "number" and latitude_prop["number"] is not None:
                        entry["latitude"] = latitude_prop["number"]
                
                if "Longitude" in properties:
                    longitude_prop = properties["Longitude"]
                    if longitude_prop["type"] == "number" and longitude_prop["number"] is not None:
                        entry["longitude"] = longitude_prop["number"]
                
                if "AI_Model" in properties:
                    ai_model_prop = properties["AI_Model"]
                    if ai_model_prop["type"] == "rich_text" and ai_model_prop["rich_text"]:
                        entry["ai_model_info"] = ai_model_prop["rich_text"][0]["plain_text"]
                
                entry["tabelog_data"] = tabelog_data
                entries.append(entry)
            
            return entries
        
        except Exception as e:
            print(f"Error getting entries: {e}")
            return []

    def delete_entry(self, entry_id):
        """Delete an entry by archiving it"""
        try:
            self.notion.pages.update(entry_id, archived=True)
            return True, "Entry deleted successfully!"
        except Exception as e:
            return False, f"Error deleting entry: {str(e)}"

    def get_database_info(self):
        """Get database properties for debugging"""
        try:
            if not self.database_id:
                return None, "Database ID not configured"
            
            database = self.notion.databases.retrieve(self.database_id)
            properties = database.get("properties", {})
            
            property_info = {
                prop_name: {
                    "type": prop_value["type"],
                    "id": prop_value.get("id", "N/A")
                }
                for prop_name, prop_value in properties.items()
            }
            
            return {
                "database_id": self.database_id,
                "database_title": database.get("title", []),
                "properties": property_info
            }, None
            
        except Exception as e:
            return None, str(e)
