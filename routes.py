from flask import render_template, request, jsonify, redirect, url_for, flash
from dotenv import load_dotenv
import aiconfigs
from notion_service import NotionService
import os

notion_service = NotionService()
load_dotenv()

def register_routes(app):
    @app.route('/')
    def index():
        """Main page with form and entries"""
        entries = notion_service.get_entries()
        return render_template('python_frontend.html', entries=entries)

    @app.route('/map')
    def map():
        """Map page"""    
        api_key = os.getenv("GOOGLE_MAPS_API")
        if not api_key:
            flash('Google Maps API key not configured', 'error')
            return redirect(url_for('index'))

        # Get entries with coordinates
        entries = notion_service.get_entries()
        markers = []
        for entry in entries:
            if entry.get('latitude') and entry.get('longitude'):
                markers.append({
                    'lat': entry['latitude'],
                    'lng': entry['longitude'],
                    'title': entry.get('tabelog_data', {}).get('name', 'Restaurant'),
                    'url': entry.get('url', ''),  # Tabelog URL
                    'notion_url': entry.get('notion_url', '')
                }) 
        # print("markers: ", markers)
        return render_template('map.html', 
                             api_key=api_key,
                             markers=markers,
                             center_lat=34.92534863829663,
                             center_lng=135.79543051024322
                            )
   
    @app.route('/add_entry', methods=['POST'])
    def add_entry():
        """Handle form submission"""
        link_url = request.form.get('link_url', '').strip()
        notes = request.form.get('notes', '').strip()
        
        # Validation
        if not link_url or not notes:
            flash('Please fill in both link and notes!', 'error')
            return redirect(url_for('index'))
        
        if not notion_service.validate_url(link_url):
            flash('Please enter a valid Tabelog URL!', 'error')
            return redirect(url_for('index'))
    
        # Get coordinates from AI
        ai_response = aiconfigs.get_ai_response(link_url)
        parsed_coordinates = aiconfigs.parse_coordinates(ai_response["response"])
        latitude = float(parsed_coordinates["latitude"]) if parsed_coordinates else None
        longitude = float(parsed_coordinates["longitude"]) if parsed_coordinates else None
        
        # Get AI model and provider info
        model_info = {
            "model": ai_response.get("model", "Unknown"),
            "provider": ai_response.get("provider", "Unknown")
        }
        
        # Save to Notion with Tabelog data and AI info
        success, message = notion_service.create_entry(link_url, notes, latitude, longitude, ai_model_info=model_info)
        
        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')
        return redirect(url_for('index'))

    @app.route('/delete_entry/<entry_id>')
    def delete_entry(entry_id):
        """Delete an entry"""
        success, message = notion_service.delete_entry(entry_id)
        
        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')
        
        return redirect(url_for('index'))

    @app.route('/api/debug/database')
    def debug_database():
        """Debug endpoint to see database properties"""
        result, error = notion_service.get_database_info()
        if error:
            return jsonify({"error": error}), 400 if "not configured" in error else 500
        return jsonify(result)
    return app
