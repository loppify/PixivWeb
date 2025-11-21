import os
import sys
import re
import argparse
import requests
import concurrent.futures
from dotenv import load_dotenv
from pixivpy3 import AppPixivAPI
from pixivpy3.utils import PixivError

load_dotenv()

REFRESH_TOKEN = os.getenv("PIXIV_REFRESH_TOKEN")
USER_AGENT = os.getenv("USER_AGENT", "PixivAndroidApp/5.0.234 (Android 11; Pixel 5)")
DOWNLOAD_DIR = os.getenv("DOWNLOAD_FOLDER", "downloads")
MAX_DOWNLOAD_WORKERS = int(os.getenv("MAX_WORKERS", 5))

UGOIRA_API_URL = "https://ugoira.com/api/illusts/queue"
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://ugoira.com/"
}

TAG_BLACKLIST = ["guro", "巨乳", "爆乳化"]
TAG_WHITELIST = []


class PixivDownloader:
    def __init__(self, refresh_token, base_path, max_workers=5):
        self.api = AppPixivAPI()
        self.base_path = base_path
        self.max_workers = max_workers
        self.processed_illust_ids = set()
        self.blacklist_patterns = [re.compile(p, re.IGNORECASE) for p in TAG_BLACKLIST]
        self.whitelist_patterns = [re.compile(p, re.IGNORECASE) for p in TAG_WHITELIST]

        os.makedirs(self.base_path, exist_ok=True)
        self._authenticate(refresh_token)

    def _authenticate(self, token):
        try:
            print("Attempting to authenticate...")
            self.api.auth(refresh_token=token, headers={"User-Agent": USER_AGENT})
            print(f"Logged in as user: {self.api.user_id}")
        except PixivError as e:
            print(f"Authentication failed: {e}")
            sys.exit(1)

    def _is_illust_allowed(self, illust):
        if not illust or not hasattr(illust, 'tags'): return False
        tag_names = [tag.name for tag in illust.tags]

        for pattern in self.blacklist_patterns:
            for tag in tag_names:
                if pattern.search(tag):
                    print(f"  [Filter] REJECTED: {illust.id}")
                    return False
        return True

    def _make_safe_filename(self, filename):
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|', ' ', '#']
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename

    def _download_job(self, url, path, name):
        try:
            if os.path.exists(os.path.join(path, name)):
                print(f"  [Skip] Exists: {name}")
                return
            print(f"  [Download] {name}")
            self.api.download(url, path=path, name=name)
        except Exception as e:
            print(f"    [Error] {name}: {e}")

    def _ugoira_download(self, illust_id, path, base_filename):
        mp4_name = f"{base_filename}.mp4"
        mp4_path = os.path.join(path, mp4_name)
        if os.path.exists(mp4_path):
            print(f"  [Skip] MP4 Exists: {mp4_name}")
            return

        print(f"  [API] Requesting Ugoira: {illust_id}")
        try:
            res = requests.post(UGOIRA_API_URL, json={"text": str(illust_id)}, timeout=10)
            res.raise_for_status()
            data = res.json()
            if not data.get('ok') or not data.get('data'): return

            mp4_url = data['data'][0]['preview']['mp4']
            print(f"  [Download] MP4: {mp4_name}")

            dl = requests.get(mp4_url, stream=True, timeout=30, headers=BROWSER_HEADERS)
            with open(mp4_path, 'wb') as f:
                for chunk in dl.iter_content(chunk_size=8192): f.write(chunk)
        except Exception as e:
            print(f"    [Error] Ugoira {illust_id}: {e}")

    def _download_illust(self, illust, directory, executor):
        if not illust: return

        title = self._make_safe_filename(illust.title)
        artist = self._make_safe_filename(illust.user.name)
        base_name = f"[{illust.user.id}_{artist}]_[{illust.id}_{title}]"

        if illust.type == 'ugoira':
            executor.submit(self._ugoira_download, illust.id, directory, base_name)
        elif (illust.type == 'illust' or illust.type != 'manga') and illust.page_count == 1:
            url = illust.meta_single_page.original_image_url or illust.image_urls.large
            ext = url.split('.')[-1]
            executor.submit(self._download_job, url, directory, f"{base_name}.{ext}")
        elif illust.page_count > 1:
            for i, page in enumerate(illust.meta_pages):
                url = page.image_urls.original
                ext = url.split('.')[-1]
                executor.submit(self._download_job, url, directory, f"{base_name}_p{i}.{ext}")

    def download_recursive(self, initial_id, depth=1):
        current_ids = [initial_id]

        for i in range(depth + 1):
            print(f"\n--- Processing Layer {i} (Count: {len(current_ids)}) ---")
            next_ids = set()

            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                for illust_id in current_ids:
                    if illust_id in self.processed_illust_ids: continue

                    try:
                        self.processed_illust_ids.add(illust_id)
                        json_res = self.api.illust_detail(illust_id)
                        illust = json_res.illust

                        if not illust or not self._is_illust_allowed(illust): continue

                        self._download_illust(illust, self.base_path, executor)

                        if i < depth:
                            related = self.api.illust_related(illust_id)
                            if related.illusts:
                                for rel in related.illusts[:30]:
                                    if rel.id not in self.processed_illust_ids:
                                        next_ids.add(rel.id)
                    except Exception as e:
                        print(f"Error processing {illust_id}: {e}")

            current_ids = list(next_ids)
            if not current_ids: break


def parse_id(url):
    match = re.search(r'/artworks/(\d+)', url)
    return int(match.group(1)) if match else None


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("url", type=str)
    parser.add_argument("depth", type=int)
    args = parser.parse_args()

    illust_id = parse_id(args.url)
    if illust_id:
        dl = PixivDownloader(REFRESH_TOKEN, DOWNLOAD_DIR, MAX_DOWNLOAD_WORKERS)
        dl.download_recursive(illust_id, args.depth)
