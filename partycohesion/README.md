# PartyCohesion

Neutral, data-first view of U.S. Congressional voting patterns and party cohesion.

**Primary source**: [Voteview](https://voteview.com/) (Lewis, Poole, Rosenthal, Boche, Rudkin & Sonnet).

## Features

- **Overview** — Ideology distributions, cohesion proxy, and party median trends across Congresses 110–119
- **Member Explorer** — Search any member, view ideology score + cohesion proxy, see them in context of their party
- **Key Votes** — Framework for high-profile vote series (structure ready; full roll-call linkage next)
- **Methodology** — Clear definitions of DW-NOMINATE and the cohesion proxy
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

This downloads the latest Voteview member ideology file and rebuilds `data/members_processed.csv`. Restart the Streamlit app afterward.

## Deploy to Streamlit Community Cloud (Free)

1. Create a public GitHub repository and push this entire folder.
2. Go to [https://share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
3. Click **New app**.
4. Select your repository, branch (`main`), and main file path: `app.py`.
5. Click **Deploy**.

Your app will be live at a URL like `https://partycohesion-xxxx.streamlit.app`.

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
- **Cohesion proxy**: Within each Congress + chamber + party, members are ranked by absolute distance from the party median on Dimension 1. Score of 100 = closest to the party median; lower scores = further toward the ideological wing. This is a transparent proxy. Classic party-unity percentages (% of votes with the party majority) will be added when full roll-call matrices are processed.
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
