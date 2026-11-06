# PartyCohesion

Neutral, data-first view of U.S. Congressional voting patterns and party cohesion.

**Primary source**: [Voteview](https://voteview.com/) (Lewis, Poole, Rosenthal, Boche, Rudkin & Sonnet).

## Features

- **Overview** — Party unity rates, ideology distributions, cohesion proxy, and party trends across Congresses 110–119
- **Member Explorer** — Search any member, view party unity %, ideology score, and their unity rate across every Congress they served in
- **Key Votes** — Party unity by Congress, plus high-profile vote series (funding bills, Cabinet confirmations, biggest party breaks) showing each party's split and every member who voted against their party
- **Methodology** — Clear definitions of party unity, DW-NOMINATE, and the cohesion proxy
- **About** — Project purpose and independence statement

## Quick Start (Local)

```bash
cd partycohesion
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Open the URL shown in the terminal (usually http://localhost:8501).

## Refresh the Data

From the project root:

```bash
python scripts/refresh_data.py
```

This downloads the latest Voteview member file and the House and Senate roll-call vote files for Congresses 110–119, then rebuilds `data/members_processed.csv` and `data/unity_summary.csv`. It also rebuilds the key vote series in `data/key_votes.csv` and `data/key_vote_defectors.csv`. Raw downloads are cached in `data/raw/` (git-ignored). Commit the updated CSVs and Streamlit Cloud redeploys automatically.

## Add Your Own Key Votes

To add a hand-picked series (for example, signature legislation), add rows to `data/key_votes_custom.csv`:

```csv
series,congress,chamber,rollnumber,note
Signature Legislation,119,House,123,Final passage
```

The roll call number is shown in the **Roll Call** column on the Key Votes page. Then run `python scripts/refresh_data.py` and commit the updated data files.

## Deploy to Streamlit Community Cloud (Free)

1. Create a public GitHub repository and push this entire folder.
2. Go to [https://share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
3. Click **New app**.
4. Select your repository, branch (`main`), and main file path: `app.py`.
5. Click **Deploy**.

The live app is at **https://partycohesion.streamlit.app**.

You can embed it elsewhere by appending `?embed=true` to the URL.

### Suggested GitHub steps

```bash
cd partycohesion
git init
git add .
git commit -m "Initial PartyCohesion Streamlit app"
# Create a new empty repo on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/partycohesion.git
git branch -M main
git push -u origin main
```

Then follow the Streamlit Cloud steps above.

## Data Notes

- **Ideology**: DW-NOMINATE Dimension 1 (negative ≈ more liberal, positive ≈ more conservative).
- **Party unity %**: For each Congress and chamber, a party-unity vote is a roll call where a majority of voting Democrats opposed a majority of voting Republicans. A member's rate is the share of those votes (Yea/Nay only) on which they sided with their own party's majority. Only Democrats and Republicans are scored.
- **Cohesion proxy**: Within each Congress + chamber + party, members are ranked by absolute distance from the party median on Dimension 1. Score of 100 = closest to the party median; lower scores = further toward the ideological wing.
- Coverage: House and Senate, Congresses 110–119.

## Project Principles

1. Primary sources over interpretation
2. Minimal editorial language
3. Transparent methodology
4. No opaque partisan scorecards
5. Expandable to additional data domains later

## License / Attribution

Educational and non-commercial use is fine.  
Please credit **Voteview** for the underlying scores and **PartyCohesion** for the presentation if you reuse charts or the application structure.
