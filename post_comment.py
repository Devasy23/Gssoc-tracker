import os
import sys
import requests


def post_comment(repo_owner, repo_name, pr_number, github_token):
    # Get PR author
    pr_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls/{pr_number}"
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    pr_response = requests.get(pr_url, headers=headers)
    pr_author = pr_response.json()["user"]["login"]


    # Get PR stats
    query = f"""
    query($owner:String!, $repo:String!) {{
            repository(owner:$owner, name:$repo) {{
                pullRequests(first:100, orderBy:{{field:CREATED_AT, direction:DESC}}) {{
                    totalCount
                    nodes {{
                        author {{
                            login
                        }}
                        additions
                        deletions
                    }}
                }}
            }}
        }}
    """
    variables = {
        "owner": repo_owner,
        "repo": repo_name,
        "author": pr_author
    }
    graphql_url = "https://api.github.com/graphql"
    response = requests.post(graphql_url, json={"query": query, "variables": variables}, headers=headers)
    # print(response.json())
    data = response.json()["data"]["repository"]["pullRequests"]


    total_prs = data["totalCount"]
    recent_prs = data["nodes"][:10]
    total_additions = sum(pr["additions"] for pr in recent_prs)
    total_deletions = sum(pr["deletions"] for pr in recent_prs)

    comment1 = f"![Author's GitHub stats](https://github-readme-stats.vercel.app/api?username={pr_author}&show_icons=true&theme=radical)"
    # Prepare comment
    # comment = f"""
    # 📊 **Contributor Stats for @{pr_author}:**

    # - **Total PRs Merged:** {total_prs}
    # - **Recent Contributions (last 10 PRs):**
    # - Lines Added: {total_additions}
    # - Lines Deleted: {total_deletions}

    # Keep up the great work! 🚀

    # ![Author's GitHub stats](https://github-readme-stats.vercel.app/api?username={pr_author}&show_icons=true&theme=radical)
    # """


    # Post comment
    comment_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/issues/{pr_number}/comments"
    requests.post(comment_url, json={"body": comment1}, headers=headers)


if __name__ == "__main__":
    repo_owner = sys.argv[1]
    repo_name = sys.argv[2]
    pr_number = sys.argv[3]
    github_token = sys.argv[4]
    post_comment(repo_owner, repo_name, pr_number, github_token)