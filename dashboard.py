import streamlit as st
import pymongo
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
# aedvjvtest code shouldn't be merged

MONGO_URI = st.secrets["MONGO_URI"]

# Set up MongoDB connection
client = pymongo.MongoClient(MONGO_URI)
db = client["gssoc"]
collection = db["repo_stats"]

@st.cache_data
def load_data():
    data = list(collection.find({}))
    df = pd.DataFrame(data)
    return df


def calculate_gains(df, period='overall'):
    metrics = ["stars", "forks", "watchers", "contributors", "closed_prs"]
   
    # Set reference date to October 7th of the current year
    reference_date = datetime(datetime.now().year, 10, 7)
   
    # Calculate days since reference date for each entry
    df['days_since_reference'] = (df['date_fetched'] - reference_date).dt.days
   
    if period == 'overall':
        latest_df = df.sort_values('days_since_reference').groupby('repo_name').last()
        earliest_df = df.sort_values('days_since_reference').groupby('repo_name').first()
        for metric in metrics:
            latest_df[f"{metric}_gain"] = latest_df[metric] - earliest_df[metric]
    elif period == 'daily':
        latest_df = df.sort_values('days_since_reference').groupby('repo_name').last()
        one_day_ago_df = df[df['days_since_reference'] == latest_df['days_since_reference'].max() - 1].groupby('repo_name').last()
        for metric in metrics:
            latest_df[f"{metric}_daily_gain"] = latest_df[metric] - one_day_ago_df[metric]
    elif period == 'weekly':
        latest_df = df.sort_values('days_since_reference').groupby('repo_name').last()
        week_ago_df = df[df['days_since_reference'] >= latest_df['days_since_reference'].max() - 7].groupby('repo_name').first()
        for metric in metrics:
            latest_df[f"{metric}_weekly_gain"] = latest_df[metric] - week_ago_df[metric]
   
    return latest_df.reset_index()


def calculate_composite_score(df):
    metrics = ["forks", "contributors", "closed_prs", "stars", "watchers"]
    for metric in metrics:
        df[f"{metric}_gain_percentile"] = df[f"{metric}_gain"].rank(pct=True)
   
    high_weight = 0.7 * (df["forks_gain_percentile"] + df["contributors_gain_percentile"] + df["closed_prs_gain_percentile"]) / 3
    low_weight = 0.3 * (df["stars_gain_percentile"] + df["watchers_gain_percentile"]) / 2
    return high_weight + low_weight


def display_leaderboard(df, period):
    if period == 'Overall':
        df['composite_score'] = calculate_composite_score(df)
        display_df = df[['repo_name', 'composite_score'] + [f"{m}_gain" for m in ["stars", "forks", "watchers", "contributors", "closed_prs"]]].sort_values('composite_score', ascending=False).head(10).reset_index()
        fig = px.bar(display_df, x="repo_name", y="composite_score", title="Top 10 Overall")
    else:
        gain_suffix = "_daily_gain" if period == "Day" else "_weekly_gain"
        gain_cols = [f"{m}{gain_suffix}" for m in ["stars", "forks", "watchers", "contributors", "closed_prs"]]
        display_df = df[['repo_name'] + gain_cols].sort_values(f"stars{gain_suffix}", ascending=False).head(10).reset_index()
        fig = px.bar(display_df, x="repo_name", y=f"stars{gain_suffix}", title=f"Top 10 Star Gainers ({period})")
   
    st.dataframe(display_df)
    st.plotly_chart(fig)


def display_repo_timeline(df, repo_name):
    project_df = df[df['repo_name'] == repo_name].sort_values('date_fetched')
   
    st.subheader("Current Stats")
    col1, col2, col3 = st.columns(3)
    col1.metric("Stars", project_df['stars'].iloc[-1])
    col2.metric("Forks", project_df['forks'].iloc[-1])
    col3.metric("Contributors", project_df['contributors'].iloc[-1])
   
    st.subheader("Trends over Time")
    metrics = ['stars', 'forks', 'watchers', 'contributors', 'open_issues', 'closed_issues', 'open_prs', 'closed_prs']
    for metric in metrics:
        fig = px.line(project_df, x='date_fetched', y=metric, title=f"{metric.capitalize()} over Time")
        st.plotly_chart(fig)


def compare_repos(df, repos):
    metrics = ['stars', 'forks', 'watchers', 'contributors', 'closed_prs']
    latest_data = df.sort_values('date_fetched').groupby('repo_name').last().reset_index()
   
    data = []
    for repo in repos:
        repo_data = latest_data[latest_data['repo_name'] == repo]
        if not repo_data.empty:
            data.append([repo] + [repo_data[metric].values[0] for metric in metrics])
   
    fig = go.Figure()
    for d in data:
        fig.add_trace(go.Scatterpolar(
            r=d[1:],
            theta=metrics,
            fill='toself',
            name=d[0]
        ))
   
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, max([max(d[1:]) for d in data])]
            )),
        showlegend=True,
        title="Repository Comparison"
    )
   
    st.plotly_chart(fig)


def main():
    st.set_page_config(page_title="GSSoC 2024 Dashboard", page_icon="GS_logo_White.svg", layout="wide")
    st.markdown("<br>", unsafe_allow_html=True)
    st.image("GS_logo_White.svg", width=500)   
    raw_df = load_data()
   
    tab1, tab2, tab3 = st.tabs(["## Leaderboard", "## Per Repo Timeline", "## Compare Repos"])
   
    with tab1:
        st.header("Leaderboard")
        period = st.radio("Select period", ["Overall", "Day", "Week"], horizontal=True)
        if period == "Overall":
            df = calculate_gains(raw_df, 'overall')
        elif period == "Day":
            df = calculate_gains(raw_df, 'daily')
        else:
            df = calculate_gains(raw_df, 'weekly')
        display_leaderboard(df, period)
   
    with tab2:
        st.header("Per Repo Timeline")
        selected_project = st.selectbox("Select a project", raw_df['repo_name'].unique())
        display_repo_timeline(raw_df, selected_project)
   
    with tab3:
        st.header("Compare Repos")
        repos = st.multiselect("Select repositories to compare", raw_df['repo_name'].unique())
        if repos:
            compare_repos(raw_df, repos)


if __name__ == "__main__":
    main()
