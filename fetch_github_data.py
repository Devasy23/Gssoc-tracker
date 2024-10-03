import requests
import pymongo
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# MongoDB connection setup
client = pymongo.MongoClient(os.getenv("MONGO_URI"))
db = client["gssoc"]
repos_collection = db["repos"]
projects_collection = db["projects"]

# GitHub API setup
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"}

# Function to fetch repositories from MongoDB projects collection
def fetch_projects_from_db():
    projects = projects_collection.find({}, {"project_name": 1, "github_url": 1})
    return list(projects)

# Extract repo name from the GitHub URL
def extract_repo_name(github_url):
    # Assuming URLs are in the format: https://github.com/org/repo
    return github_url.replace("https://github.com/", "")

# Function to fetch additional repo data: stars, forks, watchers, etc.
def fetch_repo_data(repo_name, project_name):
    url = f"https://api.github.com/repos/{repo_name}"
    response = requests.get(url, headers=HEADERS)
    # print(response.json())
    if response.status_code == 200:
        repo = response.json()
        repo_data = {
            "project_name": project_name,
            "repo_name": repo_name,
            "stars": repo["stargazers_count"],
            "forks": repo["forks_count"],
            "watchers": repo["subscribers_count"],
            "contributors": fetch_contributors(repo_name),
            "commits": fetch_commits(repo_name),
            "issues": fetch_issues(repo_name),
            "pull_requests": fetch_pull_requests(repo_name),
            "last_updated": datetime.utcnow(),
        }
        return repo_data
    else:
        print(f"Failed to fetch data for {repo_name}")
        return None

# Fetch contributors
def fetch_contributors(repo_name):
    url = f"https://api.github.com/repos/{repo_name}/contributors"
    response = requests.get(url, headers=HEADERS)
    # print(response.json())
    return response.json()

# Fetch commits
def fetch_commits(repo_name):
    url = f"https://api.github.com/repos/{repo_name}/commits"
    response = requests.get(url, headers=HEADERS)
    return response.json()

# Fetch issues
def fetch_issues(repo_name):
    url = f"https://api.github.com/repos/{repo_name}/issues?state=all"
    response = requests.get(url, headers=HEADERS)
    return response.json()

# Fetch pull requests
def fetch_pull_requests(repo_name):
    url = f"https://api.github.com/repos/{repo_name}/pulls?state=all"
    response = requests.get(url, headers=HEADERS)
    pr_data = response.json()
    for pr in pr_data:
        pr['comments'] = fetch_pr_comments(repo_name, pr['number'])
        pr['review_comments'] = fetch_pr_review_comments(repo_name, pr['number'])
    return pr_data

# Fetch PR comments
def fetch_pr_comments(repo_name, pr_number):
    url = f"https://api.github.com/repos/{repo_name}/issues/{pr_number}/comments"
    response = requests.get(url, headers=HEADERS)
    return response.json()

# Fetch PR review comments
def fetch_pr_review_comments(repo_name, pr_number):
    url = f"https://api.github.com/repos/{repo_name}/pulls/{pr_number}/comments"
    response = requests.get(url, headers=HEADERS)
    return response.json()

# Save repository data to MongoDB
def save_to_mongo(repo_data):
    repos_collection.update_one(
        {"repo_name": repo_data['repo_name']}, {"$set": repo_data}, upsert=True
    )

# Main function to fetch all GSSoC repo data from MongoDB
def fetch_all_gssoc_repo_data():
    projects = fetch_projects_from_db()  # Fetch all project URLs from 'projects' collection
    for project in projects:
        github_url = project['github_url']
        project_name = project['project_name']
        repo_name = extract_repo_name(github_url)
        
        print(f"Fetching data for: {repo_name}")
        repo_data = fetch_repo_data(repo_name, project_name)
        
        if repo_data:
            save_to_mongo(repo_data)
            print(f"Saved data for {repo_data['repo_name']}")
        # break

if __name__ == "__main__":
    fetch_all_gssoc_repo_data()
