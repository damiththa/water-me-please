# 🪴 Water Me Please — TRMNL Plant Watering Plugin

A private TRMNL plugin that syncs your plant watering schedule from Airtable to your e-ink display. Only thirsty plants (within 3 days of needing water) are shown, with smart adaptive layouts that scale based on how many plants need attention.

## Features

- 🌿 **Pulls plant data** from Airtable (Plant Name, Last Watered, Next Watering Date)
- 📸 **Smart image priority**: Uses your own uploaded photo from Airtable first, falls back to Wikipedia, then a 🪴 emoji
- 💧 **Thirsty badge**: Only shown when a plant needs watering within 3 days
- 📐 **Adaptive layout**: Automatically adjusts the grid based on how many thirsty plants there are:
  - `0 plants` → Cheerful "All Good!" full-screen message
  - `1–4 plants` → Spacious 2-column layout
  - `5–6 plants` → Standard 3-column layout
  - `7–12 plants` → Compact 4-column layout
  - `13+ plants` → Text-only max density layout
- 🔤 **Alphabetical sorting** of plants
- 🔡 **14 character** recommended max plant name length (ellipsis applied automatically)

## Setup

### 1. Clone the repo & install dependencies

```bash
git clone https://github.com/damiththa/water-me-please.git
cd water-me-please
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure your credentials

```bash
cp .env.example .env
```

Edit `.env` and fill in your:
- `AIRTABLE_API_KEY` — from [airtable.com/create/tokens](https://airtable.com/create/tokens)
- `AIRTABLE_BASE_ID` — starts with `app`
- `AIRTABLE_TABLE_NAME` — e.g. `tbl-development_only`
- `TRMNL_WEBHOOK_URL` — from your TRMNL Private Plugin dashboard

### 3. Set up GitHub Environments (For Automation)
This project uses **GitHub Environments** to separate Development and Production.
1. Go to **Settings -> Environments** in your repo.
2. Create `Development` and `Production`.
3. Add your secrets to each environment. The workflow automatically selects the environment based on the branch (`dev` vs `main`).

### 4. Set up your Airtable table

Your table needs these columns:

| Column | Type | Notes |
|---|---|---|
| `Plant Name` | Single line text | |
| `Last Watered` | Date | YYYY-MM-DD |
| `Next Watering Date` | Date | YYYY-MM-DD (Calculated by script) |
| `Frequency` | Single line text | e.g. "7 days", "2 weeks" |
| `Watered ?` | Checkbox | Check this to reset the cycle |
| `Watered Date Hidden` | Last Modified Time | Scoped to `Watered ?` column |
| `Plant pic` | Attachment | Optional |

### 4. Add the template to TRMNL

Copy the contents of `template.html` into your TRMNL Private Plugin editor and save.

### 5. Run the sync

```bash
source venv/bin/activate
python sync.py
```

Set up a cron job or scheduler to run this daily to keep your display up to date.

## Files

| File | Purpose |
|---|---|
| `sync.py` | Main script — fetches Airtable data and pushes to TRMNL |
| `template.html` | Liquid template for the TRMNL display |
| `mockup_zero.html` | Preview: zero thirsty plants |
| `mockup_spacious.html` | Preview: 1–4 thirsty plants |
| `mockup_compact.html` | Preview: 7–12 thirsty plants |
| `mockup_max.html` | Preview: 13+ thirsty plants |
| `.env.example` | Template for your credentials |
| `requirements.txt` | Python dependencies |
