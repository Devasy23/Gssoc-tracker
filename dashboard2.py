import streamlit as st
import pymongo
import pandas as pd
import plotly.express as px
from datetime import datetime

# MongoDB connection
MONGO_URI = st.secrets["MONGO_URI"]
client = pymongo.MongoClient(MONGO_URI)
db = client["gssoc"]
collection = db["repo_stats"]

# Calculate Composite Score (from dashboard2.py)
def calculate_composite_score(row):
    high_weight = 0.7 * (row["forks_percentile"] + row["contributors_percentile"] + row["closed_prs_percentile"]) / 3
    low_weight = 0.3 * (row["stars_percentile"] + row["watchers_percentile"] + row["size_percentile"] + row["open_issues_percentile"] + row["closed_issues_percentile"]) / 5
    return high_weight + low_weight

# Load data with caching
@st.cache_data
def load_data():
    data = list(collection.find({}))
    df = pd.DataFrame(data)
    
    # Calculate percentiles for metrics
    for metric in ["stars", "forks", "watchers", "contributors", "size", "open_issues", "closed_issues", "open_prs", "closed_prs"]:
        df[f"{metric}_percentile"] = df[metric].rank(pct=True)
        
    # Calculate composite score
    df["composite_score"] = df.apply(calculate_composite_score, axis=1)
    
    return df.sort_values(by="composite_score", ascending=False)

# Top gainers calculation (from dashboard.py)
def calculate_top_gainers(df, metric, period="today"):
    if period == "today":
        df["gain"] = df.groupby("repo_name")[f"{metric}"].transform(lambda x: x - x.shift(1))
    elif period == "week":
        df["gain"] = df.groupby("repo_name")[f"{metric}"].transform(lambda x: x - x.shift(7))

    return df.sort_values(by="gain", ascending=False).head(5)

# Main dashboard function
def main():
    st.title("GSSoC 2024 Comprehensive Leaderboard")

    df = load_data()
    
    # Sidebar with filters
    st.sidebar.header("Filters")
    view_option = st.sidebar.selectbox("View", ["Top 5 Gainers Today", "Top 5 Gainers This Week", "Overall Leaderboard", "Project Stats", "Composite Leaderboard"])
    selected_project = st.sidebar.selectbox("Select Project", df["repo_name"].unique())

    # Display Top Gainers
    metrics = ["stars", "forks", "watchers", "contributors", "size", "open_issues", "closed_issues", "open_prs", "closed_prs"]

    if view_option == "Top 5 Gainers Today":
        st.header("Top 5 Gainers Today")
        for metric in metrics:
            st.subheader(f"Top 5 Repositories for {metric.capitalize()}")
            top_gainers_today = calculate_top_gainers(df, metric, period="today")
            st.write(top_gainers_today)
            fig = px.bar(top_gainers_today, x="repo_name", y="gain", title=f"Top 5 Gainers Today ({metric.capitalize()})")
            st.plotly_chart(fig)

    elif view_option == "Top 5 Gainers This Week":
        st.header("Top 5 Gainers This Week")
        for metric in metrics:
            st.subheader(f"Top 5 Repositories for {metric.capitalize()}")
            top_gainers_week = calculate_top_gainers(df, metric, period="week")
            st.write(top_gainers_week)
            fig = px.bar(top_gainers_week, x="repo_name", y="gain", title=f"Top 5 Gainers This Week ({metric.capitalize()})")
            st.plotly_chart(fig)

    # Composite leaderboard
    elif view_option == "Composite Leaderboard":
        st.header("Composite Score Leaderboard")
        st.dataframe(df[['repo_name', 'composite_score', 'stars', 'forks', 'watchers', 'contributors', 'closed_prs']].head(10))

    # Project specific statistics
    elif view_option == "Project Stats":
        st.header(f"Statistics for {selected_project}")
        project_df = df[df["repo_name"] == selected_project]
        st.subheader("Current Stats")
        col1, col2, col3 = st.columns(3)
        col1.metric("Stars", project_df['stars'].iloc[0])
        col2.metric("Forks", project_df['forks'].iloc[0])
        col3.metric("Contributors", project_df['contributors'].iloc[0])

        st.subheader("Trends Over Time")
        for metric in metrics:
            fig = px.line(project_df, x='date_fetched', y=metric, title=f"{metric.capitalize()} Over Time")
            st.plotly_chart(fig)

    # Overall leaderboard
    elif view_option == "Overall Leaderboard":
        st.header("Overall Leaderboard (Since 7th Oct)")
        for metric in metrics:
            st.subheader(f"Leaderboard for {metric.capitalize()}")
            start_values = df.loc[df.groupby("repo_name")["date_fetched"].idxmin()][["repo_name", metric]].set_index("repo_name")
            start_values.columns = [f"{metric}_start"]
            df = df.merge(start_values, on="repo_name", how="left")
            df[f"total_gain_{metric}"] = df[f"{metric}"] - df[f"{metric}_start"]
            leaderboard = df.sort_values(by=f"total_gain_{metric}", ascending=False).head(5)
            st.write(leaderboard[["repo_name", metric, f"{metric}_start", f"total_gain_{metric}"]])
            fig = px.line(leaderboard, x="repo_name", y=f"total_gain_{metric}", title=f"Total Gains ({metric.capitalize()})")
            st.plotly_chart(fig)

if __name__ == "__main__":
    main()
