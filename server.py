import sys
import subprocess
import os
from flask import Flask, request, jsonify, send_from_directory

DOWNLOAD_DIR = "pixiv_downloads"

app = Flask(__name__)


@app.route('/api/start-download', methods=['POST'])
def start_download():
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


@app.route('/api/images', methods=['GET'])
def get_images():
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 30, type=int)
        if page < 1: page = 1
        if limit < 1: limit = 30

        start_index = (page - 1) * limit
        end_index = page * limit

        allowed_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.mp4', '.webp')

        if not os.path.exists(DOWNLOAD_DIR):
            os.makedirs(DOWNLOAD_DIR)
            return jsonify({"files": [], "total": 0, "page": 1})

        all_files = sorted(
            [f for f in os.scandir(DOWNLOAD_DIR) if f.is_file() and f.name.lower().endswith(allowed_extensions)],
            key=lambda f: f.stat().st_mtime,
            reverse=True
        )

        total_files = len(all_files)

        paginated_files = [f.name for f in all_files[start_index:end_index]]

        return jsonify({
            "files": paginated_files,
            "total": total_files,
            "page": page,
            "has_more": end_index < total_files
        })

    except Exception as e:
        print(f"Error reading download directory: {e}")
        return jsonify({"status": "error", "message": "Could not list images"}), 500


@app.route('/downloads/<path:filename>')
def serve_image(filename):
    return send_from_directory(DOWNLOAD_DIR, filename)


@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)