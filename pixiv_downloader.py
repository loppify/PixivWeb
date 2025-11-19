import argparse
import os
import sys
import re
import time

import requests  # To download from ugoira.com API
import concurrent.futures
from pixivpy3 import AppPixivAPI
from pixivpy3.utils import PixivError

REFRESH_TOKEN = ""
USER_AGENT = "PixivAndroidApp/5.0.234 (Android 11; Pixel 5)"
DOWNLOAD_DIR = "pixiv_downloads"
MAX_DOWNLOAD_WORKERS = 30

# --- Ugoira (Animation) Configuration ---
# If True, download Ugoira as a static JPG/PNG instead of the animation.
DOWNLOAD_UGOIRA_STATIC_PREVIEW_INSTEAD = False
UGOIRA_API_URL = "https://ugoira.com/api/illusts/queue"

# --- Headers to mimic a browser and pass server checks ---
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://ugoira.com/"
}
# --- Tag Filtering (Regex-based) ---
# Art MUST NOT match any blacklist patterns.
# If whitelist is NOT empty, art MUST match at least one whitelist pattern.
# Use regex syntax. Matching is case-insensitive.
# Example: "^Solo$" matches the tag "Solo" exactly. "Genshin" matches any tag containing "Genshin".

TAG_BLACKLIST = [
    # "R-18",
    # "R-18G",
    "guro",
    "巨乳",  # lagre breasts
    "爆乳化"
    # "loli"
]
TAG_WHITELIST = [
    # "Original",
    # "^Solo$",
]


class PixivDownloader:
    """
    Downloader for Pixiv with tag filtering and
    concurrent downloads. All images are saved to a single directory.
    """
    def __init__(self, refresh_token, base_path, max_workers=10):
        self.api = AppPixivAPI()
        self.base_path = base_path
        self.max_workers = max_workers
        self.user_id = None
        self.processed_illust_ids = set()

        print("Compiling regex filters...")
        self.blacklist_patterns = [
            re.compile(p, re.IGNORECASE) for p in TAG_BLACKLIST
        ]
        self.whitelist_patterns = [
            re.compile(p, re.IGNORECASE) for p in TAG_WHITELIST
        ]
        print(f"Blacklist patterns: {len(self.blacklist_patterns)}")
        print(f"Whitelist patterns: {len(self.whitelist_patterns)}")

        print("Ugoira handling set to use ugoira.com API.")

        os.makedirs(self.base_path, exist_ok=True)
        self._authenticate(refresh_token)

    def _authenticate(self, token):
        try:
            print("Attempting to authenticate...")
            self.api.auth(refresh_token=token, headers={"User-Agent": USER_AGENT})
            self.user_id = self.api.user_id
            print(f"Authentication successful! Logged in as user: {self.user_id}")
        except PixivError as e:
            print(f"Authentication failed: {e}")
            sys.exit(1)

    def _is_illust_allowed(self, illust):
        if not illust or not hasattr(illust, 'tags'):
            print("  [Filter] Skipping illust with no tags.")
            return False

        tag_names = [tag.name for tag in illust.tags]

        for pattern in self.blacklist_patterns:
            for tag in tag_names:
                if pattern.search(tag):
                    print(f"  [Filter] REJECTED (Blacklist: '{pattern.pattern}' on tag '{tag}'): Illust {illust.id}")
                    return False

        if self.whitelist_patterns:
            found_match = False
            for pattern in self.whitelist_patterns:
                for tag in tag_names:
                    if pattern.search(tag):
                        found_match = True
                        break
                if found_match:
                    break

            if not found_match:
                print(f"  [Filter] REJECTED (Not in whitelist): Illust {illust.id}")
                return False

        return True

    def _make_safe_filename(self, filename):
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename

    def _download_job(self, url, path, name):
        try:
            if os.path.exists(os.path.join(path, name)):
                print(f"  [Thread] Skipping (already exists): {name}")
                return
            print(f"  [Thread] Downloading: {name}")
            self.api.download(url, path=path, name=name)
            print(f"  [Thread] Finished: {name}")
        except PixivError as e:
            print(f"    [Thread] FAILED: {name}: {e}")
        except Exception as e:
            print(f"    [Thread] FAILED (Unknown Error): {name}: {e}")

    def _ugoira_download_via_api_job(self, illust_id, path, base_filename):
        mp4_name = f"{base_filename}.mp4"
        mp4_path = os.path.join(path, mp4_name)

        try:
            if os.path.exists(mp4_path):
                print(f"  [Thread] Skipping (MP4 already exists): {mp4_name}")
                return

            print(f"  [Thread] Requesting Ugoira MP4 from API for: {illust_id}")

            payload = {"text": str(illust_id)}
            try:
                response = requests.post(UGOIRA_API_URL, json=payload, timeout=10)
                response.raise_for_status()  # Raise exception for 4xx/5xx errors
            except requests.exceptions.RequestException as e:
                print(f"    [Thread] FAILED API request for {illust_id}: {e}")
                return

            try:
                result = response.json()
            except requests.exceptions.JSONDecodeError:
                print(f"    [Thread] FAILED to parse API response for {illust_id}. Not valid JSON.")
                return

            if not result.get('ok') or not result.get('data') or len(result['data']) == 0:
                print(f"    [Thread] FAILED: API returned no data for {illust_id}. Response: {result}")
                return

            mp4_url = result['data'][0].get('preview', {}).get('mp4')

            if not mp4_url:
                print(f"    [Thread] FAILED: API response for {illust_id} did not contain an MP4 URL.")
                return

            print(f"  [Thread] Downloading MP4: {mp4_name}")

            try:
                dl_response = requests.get(mp4_url, stream=True, timeout=30, headers=BROWSER_HEADERS)
                dl_response.raise_for_status()

                with open(mp4_path, 'wb') as f:
                    for chunk in dl_response.iter_content(chunk_size=8192):
                        f.write(chunk)

                print(f"  [Thread] Finished downloading: {mp4_name}")

            except requests.exceptions.RequestException as e:
                print(f"    [Thread] FAILED to download MP4 for {illust_id} from {mp4_url}: {e}")
                if os.path.exists(mp4_path):
                    os.remove(mp4_path)

        except Exception as e:
            print(f"    [Thread] FAILED (Unknown Error) processing Ugoira {illust_id}: {e}")

    def _download_illust(self, illust, directory, executor):
        if not illust:
            print("  [Error] Received empty illust object. Cannot download.")
            return

        title = self._make_safe_filename(illust.title)
        artist_name = self._make_safe_filename(illust.user.name)
        base_filename = f"[{illust.user.id}_{artist_name}]_[{illust.id}_{title}]"

        if illust.type == 'ugoira':
            if DOWNLOAD_UGOIRA_STATIC_PREVIEW_INSTEAD:
                print(f"  Queueing Ugoira (Static Preview): {title}")
                url = illust.image_urls.large
                if not url:
                    print(f"  [Error] Could not find static preview URL for ugoira: {illust.id}")
                    return

                filename = f"{base_filename}.{url.split('.')[-1].split('?')[0]}"
                executor.submit(self._download_job, url, directory, filename)

            else:
                print(f"  Queueing Ugoira (Animation as MP4): {title}")
                executor.submit(self._ugoira_download_via_api_job, illust.id, directory, base_filename)

        elif (illust.type == 'illust' or illust.type != 'manga') and illust.page_count == 1:
            url = (illust.meta_single_page.original_image_url
                   if illust.meta_single_page.original_image_url
                   else illust.image_urls.large)
            if not url:
                print(f"  [Error] Could not find URL for illust: {illust.id}")
                return

            filename = f"{base_filename}.{url.split('.')[-1].split('?')[0]}"
            executor.submit(self._download_job, url, directory, filename)


        elif illust.type == 'manga' or illust.page_count > 1:
            print(f"  Queueing manga/multi-page post: {title} ({illust.page_count} pages)")
            for i, page in enumerate(illust.meta_pages):
                url = page.image_urls.original
                filename = f"{base_filename}_p{i}.{url.split('.')[-1].split('?')[0]}"
                executor.submit(self._download_job, url, directory, filename)

        else:
            print(
                f"  [Warning] Unknown illust type or page count for {illust.id}: type={illust.type}, pages={illust.page_count}")

    def _fetch_all(self, api_method, *args, **kwargs):
        all_illusts = []
        try:
            json_result = api_method(*args, **kwargs)
            while True:
                if "illusts" in json_result:
                    all_illusts.extend(json_result.illusts)
                next_url = json_result.get("next_url")
                if not next_url:
                    break
                print(f"Fetching next page... (Total found so far: {len(all_illusts)})")
                next_qs = self.api.parse_qs(next_url)
                json_result = api_method(**next_qs)
        except PixivError as e:
            print(f"Error fetching results: {e}")
        return all_illusts

    def download_related_recursive(self, initial_illust_id, depth=1):
        print(f"\n--- Starting Recursive Download ---")
        print(f"Initial Artwork ID: {initial_illust_id}")
        print(f"Recursion Depth: {depth}")

        current_layer_ids = [initial_illust_id]

        for i in range(depth + 1):
            print(f"\n--- Processing Layer {i} ---")
            next_layer_ids = set()
            illusts_to_download = []

            for illust_id in current_layer_ids:
                if illust_id in self.processed_illust_ids:
                    print(f"  Skipping already processed ID: {illust_id}")
                    continue

                print(f"  Fetching details for: {illust_id}")

                try:
                    self.processed_illust_ids.add(illust_id)
                    json_result = self.api.illust_detail(illust_id)
                    illust = json_result.illust

                    max_tries = 3
                    sleep_time = 120

                    tries = 1
                    while not illust and tries < max_tries + 1:
                        print(
                            f"    Could not fetch illust details for {illust_id}. Retrying in {sleep_time * tries} seconds. Try {tries}")
                        self._authenticate(REFRESH_TOKEN)
                        time.sleep(sleep_time * tries)
                        self.processed_illust_ids.add(illust_id)
                        json_result = self.api.illust_detail(illust_id)
                        illust = json_result.illust
                        tries += 1

                    if not illust:
                        print(f"    Could not fetch illust details for {illust_id}. Skipping...")
                        continue

                    if not self._is_illust_allowed(illust):
                        print(f"  Skipping {illust_id} (Tag Filter).")
                        continue

                    illusts_to_download.append(illust)

                    if i < depth:
                        related_json = self.api.illust_related(illust_id)
                        if related_json.illusts:
                            for related_illust in related_json.illusts[:30]:
                                if related_illust.id not in self.processed_illust_ids and self._is_illust_allowed(
                                        related_illust):
                                    next_layer_ids.add(related_illust.id)
                                else:
                                    if related_illust.id in self.processed_illust_ids:
                                        print(f"  Skipping related (already processed): {related_illust.id}")
                                    else:
                                        print(f"  Skipping related (Tag Filter): {related_illust.id}")

                except PixivError as e:
                    print(f"    Error processing {illust_id}: {e}")
                except Exception as e:
                    print(f"    Unexpected error processing {illust_id}: {e}")

            if not illusts_to_download:
                print(f"No new (allowed) illusts to download for Layer {i}.")
            else:
                print(f"Layer {i}: Found {len(illusts_to_download)} new allowed illusts. Starting download pool...")
                with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    for illust in illusts_to_download:
                        self._download_illust(illust, self.base_path, executor)
                print(f"Layer {i} download task complete.")

            current_layer_ids = list(next_layer_ids)
            if not current_layer_ids:
                print("\nNo more allowed related illusts found. Stopping recursion.")
                break
            else:
                print(f"Layer {i} complete. Found {len(current_layer_ids)} new illusts for Layer {i + 1}.")

        print("\n--- Recursive Download Finished ---")

    def download_bookmarks(self, user_id=None, restrict='public'):
        if user_id is None:
            user_id = self.user_id
        print(f"\n--- Downloading Bookmarks for user {user_id} (Restrict: {restrict}) ---")

        illusts = self._fetch_all(self.api.user_bookmarks_illust, user_id=user_id, restrict=restrict)

        illusts_to_download = []
        for illust in illusts:
            if illust.id in self.processed_illust_ids:
                print(f"  Skipping already processed ID: {illust.id}")
                continue

            if self._is_illust_allowed(illust):
                self.processed_illust_ids.add(illust.id)
                illusts_to_download.append(illust)

        print(f"Found {len(illusts_to_download)} allowed bookmarked illustrations. Starting download pool...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            for illust in illusts_to_download:
                self._download_illust(illust, self.base_path, executor)
        print(f"Bookmark download task complete for user {user_id}.")

    def download_user_illusts(self, user_id):
        print(f"\n--- Downloading All Illustrations for user {user_id} ---")

        illusts = self._fetch_all(self.api.user_illusts, user_id=user_id)

        illusts_to_download = []
        for illust in illusts:
            if illust.id in self.processed_illust_ids:
                print(f"  Skipping already processed ID: {illust.id}")
                continue

            if self._is_illust_allowed(illust):
                self.processed_illust_ids.add(illust.id)
                illusts_to_download.append(illust)
        print(f"Found {len(illusts_to_download)} allowed illustrations. Starting download pool...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            for illust in illusts_to_download:
                self._download_illust(illust, self.base_path, executor)
        print(f"User illust download task complete for user {user_id}.")


def parse_illust_id_from_url(url):
    """Extracts the artwork ID from a pixiv URL."""
    match = re.search(r'/artworks/(\d+)', url)
    if match:
        return int(match.group(1))
    return None


if __name__ == "__main__":

    if REFRESH_TOKEN == "YOUR_REFRESH_TOKEN_GOES_HERE":
        print("Error: Please edit the script and add your REFRESH_TOKEN at the top.")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Pixiv Recursive Downloader")
    parser.add_argument("url", type=str, help="The starting Pixiv artwork URL")
    parser.add_argument("depth", type=int, help="The recursion depth (e.g., 0, 1, 2)")

    args = parser.parse_args()

    print(f"Script started with URL: {args.url} and Depth: {args.depth}")

    illust_id = parse_illust_id_from_url(args.url)
    if not illust_id:
        print(f"Invalid URL provided: {args.url}")
        print("Please use a URL like: https://www.pixiv.net/en/artworks/123456")
        sys.exit(1)

    if args.depth < 0:
        print(f"Invalid depth: {args.depth}. Must be 0 or greater.")
        sys.exit(1)

    my_downloader = PixivDownloader(refresh_token=REFRESH_TOKEN,
                                    base_path=DOWNLOAD_DIR,
                                    max_workers=MAX_DOWNLOAD_WORKERS)

    my_downloader.download_related_recursive(illust_id, args.depth)

    print("\nAll tasks complete.")