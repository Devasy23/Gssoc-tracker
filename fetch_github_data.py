import aiohttp
import asyncio
import pymongo
import os
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

# Fetch repo details and aggregate stats (stars, forks, issues, PRs)
async def fetch_repo_data(repo_name, project_name, session):
    url = f"https://api.github.com/repos/{repo_name}"
    async with session.get(url, headers=HEADERS) as response:
        if response.status == 200:
            repo = await response.json()
            open_issues = await fetch_paginated_data(f"https://api.github.com/repos/{repo_name}/issues?state=open", session)
            closed_issues = await fetch_paginated_data(f"https://api.github.com/repos/{repo_name}/issues?state=closed", session)
            open_prs = await fetch_paginated_data(f"https://api.github.com/repos/{repo_name}/pulls?state=open", session)
            closed_prs = await fetch_paginated_data(f"https://api.github.com/repos/{repo_name}/pulls?state=closed", session)
            
            repo_data = {
                "project_name": project_name,
                "repo_name": repo_name,
                "stars": repo["stargazers_count"],
                "forks": repo["forks_count"],
                "watchers": repo["watchers_count"],
                "open_issues": repo["open_issues_count"],
                "closed_issues": len(closed_issues),
                "open_prs": len(open_prs),
                "closed_prs": len(closed_prs),
                "average_open_issues": len(open_issues) / (len(open_issues) + len(closed_issues)) if (open_issues and closed_issues) else 0,
                "average_closed_issues": len(closed_issues) / (len(open_issues) + len(closed_issues)) if (open_issues and closed_issues) else 0,
                "average_open_prs": len(open_prs) / (len(open_prs) + len(closed_prs)) if (open_prs and closed_prs) else 0,
                "average_closed_prs": len(closed_prs) / (len(open_prs) + len(closed_prs)) if (open_prs and closed_prs) else 0
            }
            return repo_data
        else:
            print(f"Failed to fetch data for {repo_name}")
            return None

# Save repository data to MongoDB
async def save_to_mongo(repo_data):
    await repos_collection.insert_one(
        repo_data
    )

# Fetch all repo data asynchronously
async def fetch_all_repo_data():
    projects = await fetch_projects_from_db()  # Get projects from MongoDB synchronously
    async with aiohttp.ClientSession() as session:
        tasks = []
        print(f"Total projects: {len(projects)}")
        for project in projects:
            github_url = project['github_url']
            project_name = project['project_name']
            repo_name = extract_repo_name(github_url)

            print(f"Fetching data for: {repo_name}")
            task = asyncio.create_task(fetch_repo_data(repo_name, project_name, session))
            tasks.append(task)
        
        repo_data_list = await asyncio.gather(*tasks)
        for repo_data in repo_data_list:
            if repo_data:
                await save_to_mongo(repo_data)
                print(f"Saved data for {repo_data['repo_name']}")

# Main entry point
if __name__ == "__main__":
    asyncio.run(fetch_all_repo_data())
