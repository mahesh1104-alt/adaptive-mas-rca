import json
import os
import time
import base64
import requests

from app.repository_config import REPOSITORIES


GITHUB_API = "https://api.github.com"

# Local in-memory cache
CACHE_TTL = 300  # 5 minutes
_cache = {}


class RepositoryConnector:

    def __init__(self):
        self.github_token = os.getenv("GITHUB_TOKEN")

        if not self.github_token:
            raise RuntimeError(
                "GITHUB_TOKEN environment variable is not set"
            )

    def _headers(self):
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.github_token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _get(self, url, params=None):
        response = requests.get(
            url,
            headers=self._headers(),
            params=params,
            timeout=15,
        )

        if not response.ok:
            raise RuntimeError(
                f"GitHub API error: {response.status_code} "
                f"{response.text}"
            )

        return response.json()

    # ---------------------------------------------------------
    # CACHE
    # ---------------------------------------------------------

    def _get_cache(self, key):
        item = _cache.get(key)

        if item is None:
            return None

        timestamp, value = item

        if time.time() - timestamp > CACHE_TTL:
            del _cache[key]
            return None

        return value

    def _set_cache(self, key, value):
        _cache[key] = (
            time.time(),
            value,
        )

    # ---------------------------------------------------------
    # CONFIG
    # ---------------------------------------------------------

    def get_service_config(self, service_name):
        config = REPOSITORIES.get(service_name)

        if config is None:
            raise ValueError(
                f"Unknown service: {service_name}"
            )

        return config

    # ---------------------------------------------------------
    # LIST FILES
    # ---------------------------------------------------------

    def list_files(self, service_name):
        config = self.get_service_config(service_name)

        cache_key = f"files:{service_name}"

        cached = self._get_cache(cache_key)

        if cached is not None:
            return cached

        url = (
            f"{GITHUB_API}/repos/"
            f"{config['owner']}/"
            f"{config['repo']}/"
            f"contents/{config['path']}"
        )

        params = {
            "ref": config["branch"]
        }

        data = self._get(
            url,
            params
        )

        files = []

        if isinstance(data, list):

            for item in data:

                files.append({
                    "name": item["name"],
                    "path": item["path"],
                    "type": item["type"],
                    "size": item.get("size"),
                    "url": item["html_url"],
                })

        self._set_cache(
            cache_key,
            files
        )

        return files

    # ---------------------------------------------------------
    # GET SOURCE FILE
    # ---------------------------------------------------------

    def get_file(self, service_name, file_path):

        config = self.get_service_config(service_name)

        cache_key = (
            f"file:{service_name}:{file_path}"
        )

        cached = self._get_cache(cache_key)

        if cached is not None:
            return cached

        # If only "app.py" is provided,
        # prepend the service repository path.
        if file_path.startswith(config["path"]):
            full_path = file_path
        else:
            full_path = (
                f"{config['path'].rstrip('/')}/"
                f"{file_path.lstrip('/')}"
            )

        url = (
            f"{GITHUB_API}/repos/"
            f"{config['owner']}/"
            f"{config['repo']}/"
            f"contents/{full_path}"
        )

        params = {
            "ref": config["branch"]
        }

        data = self._get(
            url,
            params
        )

        content = data.get("content", "")

        # GitHub normally returns Base64 encoded content.
        if data.get("encoding") == "base64":

            try:
                decoded_content = base64.b64decode(
                    content
                ).decode(
                    "utf-8",
                    errors="replace"
                )

            except Exception:
                decoded_content = content

        else:
            decoded_content = content

        result = {
            "service": service_name,
            "name": data["name"],
            "path": data["path"],
            "sha": data["sha"],
            "size": data.get("size"),
            "encoding": "utf-8",
            "content": decoded_content,
            "download_url": data.get(
                "download_url"
            ),
            "html_url": data["html_url"],
        }

        self._set_cache(
            cache_key,
            result
        )

        return result

    # ---------------------------------------------------------
    # RECENT COMMITS
    # ---------------------------------------------------------

    def get_recent_commits(
        self,
        service_name,
        file_path=None,
        limit=5,
    ):

        config = self.get_service_config(
            service_name
        )

        limit = min(
            max(limit, 1),
            5
        )

        path_for_cache = (
            file_path
            if file_path
            else config["path"]
        )

        cache_key = (
            f"commits:"
            f"{service_name}:"
            f"{path_for_cache}:"
            f"{limit}"
        )

        cached = self._get_cache(
            cache_key
        )

        if cached is not None:
            return cached

        url = (
            f"{GITHUB_API}/repos/"
            f"{config['owner']}/"
            f"{config['repo']}/"
            f"commits"
        )

        params = {
            "sha": config["branch"],
            "per_page": limit,
        }

        if file_path:

            if file_path.startswith(
                config["path"]
            ):
                full_path = file_path

            else:
                full_path = (
                    f"{config['path'].rstrip('/')}/"
                    f"{file_path.lstrip('/')}"
                )

            params["path"] = full_path

        data = self._get(
            url,
            params
        )

        commits = []

        for commit in data[:limit]:

            commit_data = commit.get(
                "commit",
                {}
            )

            author = commit_data.get(
                "author",
                {}
            )

            commits.append({
                "sha": commit.get("sha"),
                "message": commit_data.get(
                    "message"
                ),
                "author": author.get(
                    "name"
                ),
                "date": author.get(
                    "date"
                ),
                "url": commit.get(
                    "html_url"
                ),
            })

        self._set_cache(
            cache_key,
            commits
        )

        return commits