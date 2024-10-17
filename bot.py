import os
import requests
import json
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from github import Github

# Configuration
DETAILS_URL = "https://ct.bnano.info/details/"
DATA_API = "https://ct.bnano.info/api/data/"
RESULTS_API = "https://ct.bnano.info/api/results/"
REPO_NAME = "nanocurrency/nano-node"
COMMENT_MARKER = "<!-- GR0VITY_DEV_BOT_NANOCT -->"


def get_test_data(commit_hash):
    response = requests.get(f"{DATA_API}{commit_hash}")
    if response.status_code == 200:
        return response.json()
    return None


def get_test_results(commit_hash):
    response = requests.get(f"{RESULTS_API}{commit_hash}")
    if response.status_code == 200:
        return response.json()
    return None


def format_comment(data, results):
    comment = f"{COMMENT_MARKER}\n## Test Results for Commit {
        data[0]['hash']}\n\n"
    comment += f"**Pull Request {data[0]['pull_request']
                                 }:** [Results]({DETAILS_URL}{data[0]['hash']})\n"
    if results is None:
        comment += "\n**Status:** Test results are not yet available. Please check back later.\n"
    else:
        comment += f"**Overall Status:** {data[0]['overall_status']}\n\n"
        comment += "### Test Case Results\n\n"
        for result in results:
            status_emoji = "✅" if result['status'] == "PASS" else "❌"
            comment += f"- {status_emoji} **{result['testcase']}**: {
                result['status']} (Duration: {result['duration']}s)\n"
            if result['status'] == "FAIL" and result.get('log'):
                comment += f" - [Log]({result['log']})\n"
    comment += f"\nLast updated: {datetime.now(
        timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
    return comment


def update_or_create_comment(pr, comment_body, commit_hash):
    for comment in pr.get_issue_comments():
        if COMMENT_MARKER in comment.body:
            if commit_hash in comment.body:
                print(f"Comment for commit {
                      commit_hash} already exists. Skipping.")
                return
            comment.edit(comment_body)
            return
    pr.create_issue_comment(comment_body)


def process_pull_request(pr):
    commit_hash = pr.head.sha
    data = get_test_data(commit_hash)
    if not data:
        print(f"No data available for PR #{pr.number}. Skipping.")
        return
    results = get_test_results(commit_hash)
    comment_body = format_comment(data, results)
    update_or_create_comment(pr, comment_body, commit_hash)


def main():
    github_token = os.environ.get("GH_BOT_PAT")
    if not github_token:
        raise ValueError("GH_BOT_PAT environment variable is not set")

    g = Github(github_token)
    repo = g.get_repo(REPO_NAME)
    open_prs = sorted(repo.get_pulls(state='open'),
                      key=lambda x: x.updated_at, reverse=True)

    # Use UTC for consistency
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=48)
    recent_prs = [pr for pr in open_prs if pr.updated_at.replace(
        tzinfo=timezone.utc) > cutoff_time]

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(process_pull_request, pr)
                   for pr in recent_prs]
        for future in as_completed(futures):
            future.result()


if __name__ == "__main__":
    main()
