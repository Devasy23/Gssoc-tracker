import streamlit as st
import pymongo
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta


MONGO_URI = st.secrets["MONGO_URI"]
client = pymongo.MongoClient(MONGO_URI)
db = client["gssoc"]
collection = db["repo_stats"]
metrics = ["stars", "forks", "watchers", "contributors", "size", "open_issues", "closed_issues", "open_prs", "closed_prs"]

# Helper to calculate top gainers with a synthetic score
def calculate_top_gainers(df, metric, period="today"):
    if period == "today":
        df["gain"] = df.groupby("repo_name")[f"{metric}"].transform(lambda x: x - x.shift(1))
    elif period == "week":
        df["gain"] = df.groupby("repo_name")[f"{metric}"].transform(lambda x: x - x.shift(7))
    
    # Normalize the gains to create a synthetic score
    df["synthetic_score"] = (df["gain"] - df["gain"].min()) / (df["gain"].max() - df["gain"].min())
    
    return df.sort_values(by="synthetic_score", ascending=False).head(5)

# Helper to calculate synthetic scores
def calculate_synthetic_scores(df, metric):
    df["gain"] = df.groupby("repo_name")[metric].transform(lambda x: x - x.shift(1))
    df["synthetic_score"] = (df["gain"] - df["gain"].min()) / (df["gain"].max() - df["gain"].min())
    return df

# Calculate composite score for leaderboard
def calculate_composite_score(row):
    high_weight = 0.7 * (row["forks_percentile"] + row["contributors_percentile"] + row["closed_prs_percentile"]) / 3
    low_weight = 0.3 * (row["stars_percentile"] + row["watchers_percentile"] + row["open_issues_percentile"] + row["closed_issues_percentile"]) / 4
    return high_weight + low_weight

@st.cache_data
def load_data():
    data = list(collection.find({}))
    df = pd.DataFrame(data)
    
    # Calculate percentiles for each metric
    for metric in ["stars", "forks", "watchers", "contributors", "size", "open_issues", "closed_issues", "open_prs", "closed_prs"]:
        df[f"{metric}_percentile"] = df[metric].rank(pct=True)
    
    # Calculate composite score
    df["composite_score"] = df.apply(calculate_composite_score, axis=1)
    
    return df.sort_values(by="composite_score", ascending=False)

# Load the data
df = load_data()

# Streamlit app starts here
st.title("GSSoC 2024 Interactive Dashboard")

# Tabs for navigation
tab1, tab2, tab3, tab4, tab5 = st.tabs(["Leaderboard", "Top 5 Gainers Today", "Top 5 Gainers This Week", "Overall Leaderboard", "Project Stats"])

# Leaderboard Tab
with tab1:
    st.header("Leaderboard")
    leaderboard_df = df[['repo_name', 'composite_score', 'stars', 'forks', 'watchers', 'contributors', 'closed_prs']].head(10)
    leaderboard_df.reset_index(drop=True, inplace=True)  # Reset index and drop the default one
    st.dataframe(leaderboard_df)


# Top 5 Gainers Today Tab
with tab2:
    st.header("Top 5 Gainers Today")
    metric_option = st.selectbox("Select Metric", ["stars", "forks", "contributors", "watchers", "size"])
    top_gainers_today = calculate_top_gainers(df, metric=metric_option, period="today")
    
    st.subheader(f"Top 5 Repositories for {metric_option.capitalize()} (Today)")
    st.dataframe(top_gainers_today[['repo_name', metric_option, 'gain', 'synthetic_score']])
    
    fig = px.bar(top_gainers_today, x="repo_name", y="synthetic_score", title=f"Top 5 Gainers Today ({metric_option.capitalize()}) - Synthetic Score")
    st.plotly_chart(fig)

# Top 5 Gainers This Week Tab
with tab3:
    st.header("Top 5 Gainers This Week")
    metric_option_week = st.selectbox("Select Metric for Weekly Gainers", ["stars", "forks", "contributors", "watchers", "size"], key="week_metric")
    top_gainers_week = calculate_top_gainers(df, metric=metric_option_week, period="week")
    
    st.subheader(f"Top 5 Repositories for {metric_option_week.capitalize()} (This Week)")
    st.dataframe(top_gainers_week[['repo_name', metric_option_week, 'gain', 'synthetic_score']])
    
    fig = px.bar(top_gainers_week, x="repo_name", y="synthetic_score", title=f"Top 5 Gainers This Week ({metric_option_week.capitalize()}) - Synthetic Score")
    st.plotly_chart(fig)

with tab4:
    st.header("Overall Leaderboard (Since 7th Oct)")
    # view overall leaderboard de duplicated by groupby on repo_name with max date_fetched and sorted by composite_score descending order
    df_n = df.groupby('repo_name').agg({'date_fetched': 'max', 'composite_score': 'max'})
    df_n = df_n.sort_values(by='composite_score', ascending=False).reset_index()
    st.dataframe(df_n[['composite_score', 'repo_name']])
    
    metrics = ['stars', 'forks', 'watchers', 'contributors', 'size', 'open_issues', 'closed_issues', 'open_prs', 'closed_prs']
    
    
    
    for metric in metrics:
        # st.write(df)
        st.subheader(f"Leaderboard for {metric.capitalize()}")

        # Calculate the starting value for each repository
        start_values = df.loc[df.groupby("repo_name")["date_fetched"].idxmin()][["repo_name", metric]].set_index("repo_name")
        st.dataframe(start_values, use_container_width=True)
        
with tab5:
    st.header("Project Statistics")
    selected_project = st.selectbox("Select a project", leaderboard_df['repo_name'].unique())
    project_df = df[df['repo_name'] == selected_project]
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Stars", project_df['stars'].iloc[0])
    col2.metric("Forks", project_df['forks'].iloc[0])
    col3.metric("Contributors", project_df['contributors'].iloc[0])
    
    st.subheader("Trends over Time")
    metrics = ['stars', 'forks', 'watchers', 'contributors', 'size', 'open_issues', 'closed_issues', 'open_prs', 'closed_prs']
    for metric in metrics:
        fig = px.line(project_df, x='date_fetched', y=metric, title=f"{metric.capitalize()} over Time")
        st.plotly_chart(fig)