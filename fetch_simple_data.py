import os
import aiohttp
import asyncio
import requests
import motor.motor_asyncio
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Environment variables (Make sure to set these in your environment)
GITHUB_API_TOKEN = os.getenv('GH_TOKEN')
MONGODB_URI = os.getenv('MONGO_URI')

# MongoDB setup
client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
db = client["gssoc"]
projects_collection = db["projects"]
stats_collection = db["repo_stats"]

# Helper to fetch repository details using REST API
async def fetch_repo_details(repo_name, session):
    repo_name = repo_name.removesuffix(".git") if repo_name.endswith(".git") else repo_name
    url = f"https://api.github.com/repos/{repo_name}"
    headers = {"Authorization": f"Bearer {GITHUB_API_TOKEN}"}
    
    async with session.get(url, headers=headers) as response:
        if response.status == 200:
            data = await response.json()
            return {
                "stars": data["stargazers_count"],
                "forks": data["forks_count"],
                "watchers": data["watchers_count"],
                "size": data["size"]
            }
        else:
            print(f"Failed to fetch REST data for {repo_name}, status: {response.status}")
            return None

# Helper to fetch data using GitHub GraphQL API
async def fetch_repo_graphql_details(repo_name, session):
    url = "https://api.github.com/graphql"
    headers = {
        "Authorization": f"Bearer {GITHUB_API_TOKEN}",
        "Content-Type": "application/json"
    }

    query = """
    query ($owner: String!, $repo: String!) {
      repository(owner: $owner, name: $repo) {
        issues(states: OPEN) { totalCount }
        closedIssues: issues(states: CLOSED) { totalCount }
        pullRequests(states: OPEN) { totalCount }
        closedPullRequests: pullRequests(states: MERGED) { totalCount }
      }
    }
    """

    repo_name = repo_name.removesuffix(".git") if repo_name.endswith(".git") else repo_name
    owner, repo = repo_name.split("/")  # owner/repo format
    variables = {
        "owner": owner,
        "repo": repo
    }

    async with session.post(url, json={"query": query, "variables": variables}, headers=headers) as response:
        if response.status == 200:
            result = await response.json()
            repo = result["data"]["repository"]
            try:
                return {
                    "open_issues": repo["issues"]["totalCount"],
                    "closed_issues": repo["closedIssues"]["totalCount"],
                    "open_prs": repo["pullRequests"]["totalCount"],
                    "closed_prs": repo["closedPullRequests"]["totalCount"]
                }
            except TypeError or ValueError:
                print(f"Failed to fetch GraphQL data for {repo_name}")
                return None
        else:
            print(f"Failed to fetch GraphQL data for {repo_name}, status: {response.status}")
            return None


# Fetch number of contributors using REST API
async def fetch_contributors_count(repo_name, session):
    repo_name = repo_name.removesuffix(".git") if repo_name.endswith(".git") else repo_name
    url = f"https://api.github.com/repos/{repo_name}/contributors"
    headers = {"Authorization": f"Bearer {GITHUB_API_TOKEN}"}
    
    async with session.get(url, headers=headers) as response:
        if response.status == 200:
            contributors = await response.json()
            return len(contributors)
        else:
            print(f"Failed to fetch contributors for {repo_name}, status: {response.status}")
            return None

# Fetch and combine repo data
async def fetch_repo_data(repo_name, project_name, session):
    # Fetching REST and GraphQL data
    repo_details = await fetch_repo_details(repo_name, session)
    repo_graphql_details = await fetch_repo_graphql_details(repo_name, session)
    contributors_count = await fetch_contributors_count(repo_name, session)

    if repo_details and repo_graphql_details and contributors_count is not None:
        combined_data = {
            "project_name": project_name,
            "repo_name": repo_name,
            "stars": repo_details["stars"],
            "forks": repo_details["forks"],
            "watchers": repo_details["watchers"],
            "contributors": contributors_count,
            "size": repo_details["size"],
            "open_issues": repo_graphql_details["open_issues"],
            "closed_issues": repo_graphql_details["closed_issues"],
            "open_prs": repo_graphql_details["open_prs"],
            "closed_prs": repo_graphql_details["closed_prs"],
            "date_fetched": datetime.utcnow()  # Save the date of data fetch
        }
        return combined_data
    else:
        print(f"Failed to fetch complete data for {repo_name}")
        return None

# Save data to MongoDB
async def save_to_mongo(repo_data):
    await stats_collection.insert_one(repo_data)

# Fetch all projects and their respective repo data
async def fetch_all_repo_data():
    projects = await projects_collection.find({}, {"project_name": 1, "github_url": 1}).to_list(None)
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        for project in projects:
            github_url = project["github_url"]
            project_name = project["project_name"]
            repo_name = extract_repo_name(github_url)

            print(f"Fetching data for: {repo_name}")
            task = asyncio.create_task(fetch_repo_data(repo_name, project_name, session))
            tasks.append(task)

        repo_data_list = await asyncio.gather(*tasks)
        for repo_data in repo_data_list:
            if repo_data:
                await save_to_mongo(repo_data)
                print(f"Saved data for {repo_data['repo_name']}")

# Extract repository name from GitHub URL
def extract_repo_name(github_url):
    return "/".join(github_url.strip("/").split("/")[-2:])

# Main execution
if __name__ == "__main__":
    asyncio.run(fetch_all_repo_data())
