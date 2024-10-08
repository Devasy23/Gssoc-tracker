import streamlit as st
import pymongo
import pandas as pd
import plotly.express as px
import os
from datetime import datetime, timedelta


MONGO_URI = st.secrets["MONGO_URI"]

# Set up MongoDB connection
client = pymongo.MongoClient(MONGO_URI)
db = client["gssoc"]
collection = db["repo_stats"]

# Helper to calculate top gainers
def calculate_top_gainers(df, metric, period="today"):
    if period == "today":
        # Calculate today's gains
        df["gain"] = df.groupby("repo_name")[f"{metric}"].transform(lambda x: x - x.shift(1))
    elif period == "week":
        # Calculate weekly gains
        df["gain"] = df.groupby("repo_name")[f"{metric}"].transform(lambda x: x - x.shift(7))

    return df.sort_values(by="gain", ascending=False).head(5)

# Fetch the current data from MongoDB
def fetch_github_data():
    # Assuming the documents store metrics for each day
    data = list(collection.find({}))
    return pd.DataFrame(data)

# Load data
st.title("GSSoC 2024 Leaderboard")
st.markdown("View top repositories based on stars, forks, contributors, etc.")

df = fetch_github_data()

# Assuming that df has columns like 'stars_today', 'stars_last_week', 'stars_start', 'forks_today', etc.
# And 'repo_name' column to identify repositories

# Sidebar options
view_option = st.sidebar.selectbox("View", ["Top 5 Gainers Today", "Top 5 Gainers This Week", "Overall Leaderboard"])

# Date: set 7th Oct as the starting point
start_date = datetime(2024, 10, 7)
today = datetime.now()

# Top 5 gainers in terms of forks, stars, etc.
metrics = ["stars", "forks", "watchers", "contributors", "size"]

# Display top gainers for today or this week
if view_option == "Top 5 Gainers Today":
    st.header("Top 5 Gainers Today")
    for metric in metrics:
        st.subheader(f"Top 5 Repositories for {metric.capitalize()}")
        top_gainers_today = calculate_top_gainers(df, metric, period="today")
        st.write(top_gainers_today)

        # Bar chart visualization
        fig = px.bar(top_gainers_today, x="repo_name", y="gain", title=f"Top 5 Gainers Today ({metric.capitalize()})")
        st.plotly_chart(fig)

elif view_option == "Top 5 Gainers This Week":
    # if it is 7 days after 7th october 2024
    if (today - start_date).days >= 7:
        st.header("Top 5 Gainers This Week")
        for metric in metrics:
            st.subheader(f"Top 5 Repositories for {metric.capitalize()}")
            top_gainers_week = calculate_top_gainers(df, metric, period="week")
            # st.write(top_gainers_week[["repo_name", f"{metric}_today", f"{metric}_last_week", "gain"]])

            # Bar chart visualization
            fig = px.bar(top_gainers_week, x="repo_name", y="gain", title=f"Top 5 Gainers This Week ({metric.capitalize()})")
            st.plotly_chart(fig)

    else:
        st.info("Data not available yet. Please try again later after 14th October.")

# Overall leaderboard (total gain since the start of the race)
elif view_option == "Overall Leaderboard":
    st.header("Overall Leaderboard (Since 7th Oct)")

    for metric in metrics:
        st.write(df)
        st.subheader(f"Leaderboard for {metric.capitalize()}")

        # Calculate the starting value for each repository
        start_values = df.loc[df.groupby("repo_name")["date_fetched"].idxmin()][["repo_name", metric]].set_index("repo_name")
        start_values.columns = [f"{metric}_start"]
        
        # Merge the start values into the main DataFrame
        df = df.merge(start_values, on="repo_name", how="left")

        df[f"total_gain_{metric}"] = df[f"{metric}"] - df[f"{metric}_start"]
        leaderboard = df.sort_values(by=f"total_gain_{metric}", ascending=False).head(5)
        st.write(leaderboard[["repo_name", f"{metric}", f"{metric}_start", f"total_gain_{metric}"]])

        # Line chart visualization for overall gain
        fig = px.line(leaderboard, x="repo_name", y=f"total_gain_{metric}", title=f"Total Gains ({metric.capitalize()})")
        st.plotly_chart(fig)
