from selenium import webdriver
from selenium.webdriver.common.by import By
import pymongo
import logging
from dotenv import load_dotenv
import time
import os

load_dotenv()

MONGO_URI = os.getenv('MONGO_URI')
# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# MongoDB connection (optional if you want to store the data)
client = pymongo.MongoClient('MONGO_URI')
db = client["gssoc"]
projects_collection = db["projects"]
driver = webdriver.Chrome()

# GSSoC project page URL
url = 'https://gssoc.girlscript.tech/project'

# Function to scrape GSSoC projects
def scrape_gssoc_projects():
    driver.get(url)
    time.sleep(5)  # Wait for the page to load fully (increase this time if necessary)
    
    project_data = []

    # Find all project divs
    project_divs = driver.find_elements(By.XPATH, '//*[@id="__next"]/div/section/div[2]/div[4]/div')
    
    for i, project_div in enumerate(project_divs, start=1):
        try:
            # Extract the project name
            project_name = project_div.find_element(By.XPATH, './/div/div/div[1]/div[1]/a').text.strip()
            
            # Extract the GitHub URL
            github_url = project_div.find_element(By.XPATH, './/div/div/div[1]/div[1]/a').get_attribute('href')
            
            # Extract the project tag
            tag_elements = project_div.find_elements(By.XPATH, './/div/div/div[2]/button')
            tags = []
            for tag_element in tag_elements:
                tags.append(tag_element.text.strip() if tag_element else "No tag")
            
            # Prepare project info
            project_info = {
                "project_name": project_name.split(". ")[1],
                "github_url": github_url,
                "tags": tags
            }
            
            # Print the extracted data
            print(project_info)
            
            # Optional: Store the data in MongoDB
            projects_collection.update_one(
                {"github_url": github_url}, 
                {"$set": project_info}, 
                upsert=True
            )
            
            project_data.append(project_info)
        
        except Exception as e:
            print(f"Error parsing project {i}: {e}")
    
    return project_data

# Run the scraper
scraped_projects = scrape_gssoc_projects()

# Optional: Close the driver after scraping
driver.quit()

# Optional: Display the collected data
for project in scraped_projects:
    print(project)