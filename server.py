import sys
import subprocess
import os
from flask import Flask, request, jsonify, send_from_directory

# --- Configuration ---
# This must match the DOWNLOAD_DIR in your downloader script
DOWNLOAD_DIR = "pixiv_downloads"

# Initialize the Flask app
app = Flask(__name__)


# --- 1. API Endpoint to Start a Download (No changes) ---
@app.route('/api/start-download', methods=['POST'])
def start_download():
    """
    API endpoint to start a download.
    Expects a JSON body like:
    {
        "url": "https://www.pixiv.net/en/artworks/123456",
        "depth": 1
    }
    """
    print("Received download request...")

    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "No JSON data provided"}), 400

    url = data.get('url')
    depth = data.get('depth')

    if not url or depth is None:
        return jsonify({"status": "error", "message": "Missing 'url' or 'depth'"}), 400

    try:
        depth_str = str(int(depth))
    except ValueError:
        return jsonify({"status": "error", "message": "'depth' must be an integer"}), 400

    print(f"Starting download for: {url} (Depth: {depth_str})")

    command = [
        sys.executable,
        'pixiv_downloader.py',
        url,
        depth_str
    ]

    try:
        subprocess.Popen(command)
        print("Download process started successfully.")
        return jsonify({
            "status": "success",
            "message": "Download process started."
        }), 202

    except Exception as e:
        print(f"Failed to start subprocess: {e}")
        return jsonify({"status": "error", "message": f"Failed to start process: {e}"}), 500


# --- 2. NEW: API Endpoint to List Downloaded Images ---
@app.route('/api/images', methods=['GET'])
def get_images():
    """
    Scans the download directory and returns a list of image/video filenames,
    sorted by most recent first.
    """
    allowed_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.mp4', '.webp')
    images = []
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)  # Create it if it doesn't exist

    try:
        # Sort files by modification time (newest first)
        files = sorted(
            os.scandir(DOWNLOAD_DIR),
            key=lambda f: f.stat().st_mtime,
            reverse=True
        )
        for f in files:
            if f.is_file() and f.name.lower().endswith(allowed_extensions):
                images.append(f.name)
        return jsonify(images)
    except Exception as e:
        print(f"Error reading download directory: {e}")
        return jsonify({"status": "error", "message": "Could not list images"}), 500


# --- 3. NEW: Route to Serve Downloaded Files ---
@app.route('/downloads/<path:filename>')
def serve_image(filename):
    """
    Serves a specific file from the DOWNLOAD_DIR.
    """
    return send_from_directory(DOWNLOAD_DIR, filename)


# --- 4. NEW: Route to Serve the Main Webpage ---
@app.route('/')
def index():
    """
    Serves the main index.html file.
    """
    return send_from_directory('.', 'index.html')


# This block allows you to run the server directly
if __name__ == '__main__':
    # Runs the server on http://127.0.0.1:5000
    app.run(debug=True, host='0.0.0.0')
