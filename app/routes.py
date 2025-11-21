import sys
import os
import subprocess
import time
from flask import Blueprint, request, jsonify, send_from_directory, current_app, render_template
from PIL import Image
from .data.database import get_db

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    return render_template('index.html')


@main_bp.route('/downloads/<path:filename>')
def serve_image(filename):
    return send_from_directory(os.path.abspath(current_app.config['DOWNLOAD_FOLDER']), filename)


@main_bp.route('/api/start-download', methods=['POST'])
def start_download():
    data = request.get_json()
    url = data.get('url')
    depth = str(data.get('depth', 0))

    if not url: return jsonify({"status": "error", "message": "URL required"}), 400

    cmd = [sys.executable, "-m", "app.core.downloader", url, depth]

    try:
        subprocess.Popen(cmd, cwd=os.getcwd())
        return jsonify({"status": "success", "message": "Download started in background."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@main_bp.route('/api/sync', methods=['POST'])
def sync_library():
    db = get_db()
    folder = current_app.config['DOWNLOAD_FOLDER']
    allowed = ('.jpg', '.jpeg', '.png', '.gif', '.mp4', '.webm')

    existing_rows = db.execute("SELECT filename FROM media").fetchall()
    existing_files = {row['filename'] for row in existing_rows}

    found_files = []
    if os.path.exists(folder):
        with os.scandir(folder) as it:
            for entry in it:
                if entry.is_file() and entry.name.lower().endswith(allowed):
                    found_files.append(entry)

    new_entries = []
    for entry in found_files:
        if entry.name not in existing_files:
            mtime = entry.stat().st_mtime
            width = 0
            height = 0

            if entry.name.lower().endswith(('.mp4', '.webm')):
                width, height = 1920, 1080
            else:
                try:
                    with Image.open(entry.path) as img:
                        width, height = img.size
                except:
                    pass

            new_entries.append((entry.name, mtime, width, height))

    if new_entries:
        try:
            db.executemany(
                "INSERT OR IGNORE INTO media (filename, mtime, width, height, is_favorite, is_viewed) VALUES (?, ?, ?, ?, 0, 0)",
                new_entries
            )
            db.commit()
        except Exception as e:
            print(f"Sync Insert Error: {e}")
            db.rollback()

    found_filenames = {e.name for e in found_files}
    to_delete = existing_files - found_filenames

    if to_delete:
        try:
            to_delete_list = list(to_delete)
            chunk_size = 900
            for i in range(0, len(to_delete_list), chunk_size):
                chunk = to_delete_list[i:i + chunk_size]
                placeholders = ','.join('?' * len(chunk))
                db.execute(f"DELETE FROM media WHERE filename IN ({placeholders})", chunk)
            db.commit()
        except Exception as e:
            print(f"Sync Delete Error: {e}")
            db.rollback()

    return jsonify({"status": "success", "added": len(new_entries), "removed": len(to_delete)})


@main_bp.route('/api/images', methods=['GET'])
def get_images():
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 30, type=int)
    show_favs = request.args.get('favorites', 'false') == 'true'

    db = get_db()
    offset = (page - 1) * limit

    where_clause = ""
    if show_favs:
        where_clause = "WHERE is_favorite = 1"

    count_sql = f"SELECT COUNT(*) as count FROM media {where_clause}"
    total = db.execute(count_sql).fetchone()['count']

    data_sql = f"""
        SELECT filename, is_favorite, is_viewed, width, height 
        FROM media 
        {where_clause}
        ORDER BY mtime
        LIMIT ? OFFSET ?
    """

    rows = db.execute(data_sql, (limit, offset)).fetchall()

    results = []
    for row in rows:
        results.append({
            "name": row['filename'],
            "favorite": bool(row['is_favorite']),
            "viewed": bool(row['is_viewed']),
            "width": row['width'] or 0,
            "height": row['height'] or 0
        })

    return jsonify({
        "files": results,
        "total": total,
        "has_more": (offset + limit) < total
    })


@main_bp.route('/api/toggle-favorite', methods=['POST'])
def toggle_favorite():
    filename = request.json.get('filename')
    db = get_db()

    existing = db.execute("SELECT is_favorite FROM media WHERE filename = ?", (filename,)).fetchone()

    if existing:
        new_val = not bool(existing['is_favorite'])
        db.execute("UPDATE media SET is_favorite = ? WHERE filename = ?", (new_val, filename))
    else:
        new_val = True
        db.execute("INSERT INTO media (filename, is_favorite, is_viewed) VALUES (?, ?, 0)", (filename, new_val))

    db.commit()

    return jsonify({"status": "success", "favorite": new_val})


@main_bp.route('/api/mark-viewed', methods=['POST'])
def mark_viewed():
    filename = request.json.get('filename')
    db = get_db()

    existing = db.execute("SELECT 1 FROM media WHERE filename = ?", (filename,)).fetchone()

    if existing:
        db.execute("UPDATE media SET is_viewed = 1 WHERE filename = ?", (filename,))
    else:
        db.execute("INSERT INTO media (filename, is_viewed, is_favorite) VALUES (?, 1, 0)", (filename,))

    db.commit()

    return jsonify({"status": "success"})


@main_bp.route('/api/delete-viewed', methods=['POST'])
def delete_viewed():
    db = get_db()
    folder = current_app.config['DOWNLOAD_FOLDER']

    rows = db.execute("SELECT filename FROM media WHERE is_viewed = 1 AND is_favorite = 0").fetchall()

    count = 0
    deleted_files = []
    for row in rows:
        fname = row['filename']
        path = os.path.join(folder, fname)
        try:
            if os.path.exists(path):
                os.remove(path)
                count += 1
            deleted_files.append(fname)
        except Exception as e:
            print(f"Error deleting {fname}: {e}")

    if deleted_files:
        placeholders = ','.join('?' * len(deleted_files))
        db.execute(f"DELETE FROM media WHERE filename IN ({placeholders})", deleted_files)
        db.commit()

    return jsonify({"status": "success", "deleted": count})
