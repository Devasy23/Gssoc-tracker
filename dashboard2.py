import streamlit as st
import pymongo
import pandas as pd
import plotly.express as px
import os
from datetime import datetime, timedelta


MONGO_URI = st.secrets["MONGO_URI"]
client = pymongo.MongoClient(MONGO_URI)
db = client["gssoc"]
collection = db["repo_stats"]

def calculate_composite_score(row):
    high_weight = 0.7 * (row["forks_percentile"] + row["contributors_percentile"] + row["closed_prs_percentile"]) / 3
    low_weight = 0.3 * (row["stars_percentile"] + row["watchers_percentile"] + row["size_percentile"] + row["open_issues_percentile"] + row["closed_issues_percentile"]) / 5
    return high_weight + low_weight

@st.cache_data
def load_data():
    data = list(collection.find({}))
    df = pd.DataFrame(data)
    
    # Calculate percentiles for each metric
    for metric in ["stars", "forks", "watchers", "contributors", "size", "open_issues", "closed_issues", "open_prs", "closed_prs"]:
        df[f"{metric}_percentile"] = df[metric].rank(pct=True)
        
    # calculate composite score
    df["composite_score"] = df.apply(calculate_composite_score, axis=1)
    
    return df.sort_values(by="composite_score", ascending=False)

def main():
    st.title("GSSoC Extd 2024 Leaderboard")
    
    df = load_data()
    
    st.sidebar.header("Filters")
    
    
    st.header("Leaderboard")
    st.dataframe(df[['repo_name', 'composite_score','stars', 'forks', 'watchers', 'contributors', 'closed_prs']].head(10))
    
    st.header("Project Statistics")
    selected_project = st.selectbox("Select a project", df['repo_name'].unique())
    project_df = df[df['repo_name'] == selected_project]
    
    # Display project stats
    st.subheader("Current Stats")
    col1, col2, col3 = st.columns(3)
    col1.metric("Stars", project_df['stars'].iloc[0])
    col2.metric("Forks", project_df['forks'].iloc[0])
    col3.metric("Contributors", project_df['contributors'].iloc[0])
    
    st.subheader("Trends over Time")
    
    metrics = ['stars', 'forks', 'watchers', 'contributors', 'size', 'open_issues', 'closed_issues', 'open_prs', 'closed_prs']
    for metric in metrics:
        fig = px.line(project_df, x='date_fetched', y=metric, title=f"{metric.capitalize()} over Time")
        st.plotly_chart(fig)
        
if __name__ == "__main__":
    main()