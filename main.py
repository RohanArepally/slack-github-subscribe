import os
from typing import Dict, List

import modal
from modal import Stub, web_endpoint

stub = Stub(
    image=modal.Image.debian_slim().pip_install("requests").pip_install("slack-sdk")
)
stub.has_processed_by_commit_id = modal.Dict.new()


@stub.function(secret=modal.Secret.from_name("slack-github-subscribe"))
@web_endpoint(method="POST")
def f(item: Dict):
    import slack_sdk
    import requests

    files_or_dirs: List[str] = [item.strip() for item in os.environ["PATHS_TO_SUBSCRIBE_TO"].split(",")]
    files_updated = []

    repo = item["repository"]
    commits_url = item["pull_request"]["commits_url"]
    github_repo_name = repo["full_name"]

    commits = requests.get(commits_url).json()
    for commit in commits:
        commit_id = commit["sha"]
        if commit_id in stub.has_processed_by_commit_id:
            continue

        commit = requests.get(commit["url"]).json()
        for file in commit["files"]:
            filename = file["filename"]
            path = f"{github_repo_name}/{filename}"
            for p in files_or_dirs:
                if path == p or (path.startswith(p) and p.endswith("/")):
                    files_updated += [filename]
                    stub.has_processed_by_commit_id[commit_id] = True
                    break

    if not files_updated:
        return

    user_id: str = os.environ["SLACK_USER_ID"]
    client = slack_sdk.WebClient(token=os.environ["SLACK_BOT_TOKEN"])
    title = item["pull_request"]["title"]
    author = item["pull_request"]["user"]["login"]
    files_list = "\n".join([f"`{f}`" for f in files_updated])
    formatted_message = f"*{title}*\nPR URL: {item['pull_request']['html_url']}\nRepo: {github_repo_name}\nAuthor: {author}\n\n*Files Updated:*\n{files_list}"

    client.chat_postMessage(channel=user_id, text=formatted_message)
    return
