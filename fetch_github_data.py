import aiohttp
import asyncio
import pymongo
from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport
import os
import datetime
import motor.motor_asyncio
from dotenv import load_dotenv

load_dotenv()


# MongoDB connection setup
client = motor.motor_asyncio.AsyncIOMotorClient(os.getenv("MONGO_URI"))
db = client["gssoc"]
projects_collection = db["projects"]
repos_collection = db["repos"]

# GitHub API setup
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"}

# Constants for GitHub rate limits and pagination
MAX_PER_PAGE = 100
RATE_LIMIT_REPOS_PER_HOUR = 5
API_CALLS_PER_REPO = 5  # Approx. with pagination
PAGE_LIMIT = 1000

# Fetch project data from MongoDB
async def fetch_projects_from_db():
    cursor = projects_collection.find({}, {"project_name": 1, "github_url": 1})
    projects = []
    async for project in cursor:
        projects.append(project)
    return projects


async def fetch_repo_data(repo_owner, repo_name, project_name, session):
    query = gql("""
    query($owner: String!, $name: String!) {
      repository(owner: $owner, name: $name) {
        stargazerCount
        forkCount
        watchers {
          totalCount
        }
        issues(states: [OPEN, CLOSED]) {
          totalCount
        }
        openIssues: issues(states: [OPEN]) {
          totalCount
        }
        pullRequests(states: [OPEN, CLOSED]) {
          totalCount
        }
        openPullRequests: pullRequests(states: [OPEN]) {
          totalCount
        }
        pullRequestsWithComments: pullRequests(first: 1) {
          totalCount
          nodes {
            comments {
              totalCount
            }
          }
        }
        issuesWithComments: issues(first: 1) {
          totalCount
          nodes {
            comments {
              totalCount
            }
          }
        }
      }
    }
    """)

    transport = AIOHTTPTransport(url='https://api.github.com/graphql', headers={'Authorization': f'Bearer {GITHUB_TOKEN}'})
    async with Client(transport=transport, fetch_schema_from_transport=True) as client:
        result = await client.execute(query, variable_values={"owner": repo_owner, "name": repo_name})
        
        repo = result['repository']
        
        total_prs = repo['pullRequests']['totalCount']
        total_issues = repo['issues']['totalCount']
        pr_comments = repo['pullRequestsWithComments']['nodes'][0]['comments']['totalCount'] if repo['pullRequestsWithComments']['nodes'] else 0
        issue_comments = repo['issuesWithComments']['nodes'][0]['comments']['totalCount'] if repo['issuesWithComments']['nodes'] else 0
        
        avg_comments_per_pr = pr_comments / total_prs if total_prs > 0 else 0
        avg_comments_per_issue = issue_comments / total_issues if total_issues > 0 else 0

        repo_data = {
            "project_name": project_name,
            "repo_name": f"{repo_owner}/{repo_name}",
            "date": datetime.utcnow(),
            "stars": repo['stargazerCount'],
            "forks": repo['forkCount'],
            "watchers": repo['watchers']['totalCount'],
            "open_issues_count": repo['openIssues']['totalCount'],
            "closed_issues_count": repo['issues']['totalCount'] - repo['openIssues']['totalCount'],
            "open_prs_count": repo['openPullRequests']['totalCount'],
            "closed_prs_count": repo['pullRequests']['totalCount'] - repo['openPullRequests']['totalCount'],
            "pr_comments_count": pr_comments,
            "issue_comments_count": issue_comments,
            "average_comments_per_pr": avg_comments_per_pr,
            "average_comments_per_issue": avg_comments_per_issue,
        }
        return repo_data

# In your main function, you'll need to split the repo_name into owner and name
async def fetch_all_repo_data():
    projects = await fetch_projects_from_db()
    async with aiohttp.ClientSession() as session:
        tasks = []
        for project in projects:
            github_url = project['github_url']
            project_name = project['project_name']
            repo_owner, repo_name = extract_repo_owner_and_name(github_url)

            print(f"Fetching data for: {repo_owner}/{repo_name}")
            task = asyncio.create_task(fetch_repo_data(repo_owner, repo_name, project_name, session))
            tasks.append(task)
        
        repo_data_list = await asyncio.gather(*tasks)
        for repo_data in repo_data_list:
            if repo_data:
                await save_to_mongo(repo_data)
                print(f"Saved data for {repo_data['repo_name']}")

def extract_repo_owner_and_name(github_url):
    try:
        parts = github_url.replace("https://github.com/", "").split("/")
        return parts[0], parts[1]
    except Exception as e:
        print(f"Invalid GitHub URL: {github_url}")
        return extract_repo_name(github_url), ""

# Extract repo name from GitHub URL
def extract_repo_name(github_url):
    return github_url.replace("https://github.com/", "")

# Fetch paginated data (for issues, PRs, commits)
async def fetch_paginated_data(url, session):
    page = 1
    all_data = []
    while True:
        paginated_url = f"{url}?per_page={MAX_PER_PAGE}&page={page}"
        async with session.get(paginated_url, headers=HEADERS) as response:
            data = await response.json()
            if not data or response.status != 200:
                break
            all_data.extend(data)
            if len(data) < MAX_PER_PAGE:
                break
            page += 1
    return all_data



# Save repository data to MongoDB
async def save_to_mongo(repo_data):
    await repos_collection.insert_one(
        repo_data
    )



# Main entry point
if __name__ == "__main__":
    asyncio.run(fetch_all_repo_data())
