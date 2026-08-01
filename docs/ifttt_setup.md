# Flic Button & IFTTT Pro Integration Guide

This guide walks you through connecting your physical **Flic Button** to your **TRMNL Plant Dashboard (`water-me-please`)** using **IFTTT Pro**.

When pressed, the Flic button triggers a GitHub repository dispatch event, which runs `sync.py --water-all` to mark all due plants as watered in Airtable and instantly update your TRMNL e-ink display.

---

## 1. Create a GitHub Personal Access Token (PAT)

1. Go to **GitHub Settings** ➔ **Developer Settings** ➔ **Personal Access Tokens** (Fine-grained or Tokens Classic).
2. Create a token with **`repo`** scope (specifically `contents: write` and `metadata: read`).
3. Copy the token (e.g. `ghp_...`). You will use this in IFTTT.

---

## 2. Configure IFTTT Pro Applet

1. Log into **[IFTTT](https://ifttt.com/)** (Ensure your IFTTT Pro account is active).
2. Click **Create** to make a new Applet.
3. **If This (Trigger)**:
   - Select **Flic** (or Flic 2).
   - Choose your button device.
   - Choose the trigger gesture: **Single Press** (or Double Press / Hold).
4. **Then That (Action)**:
   - Select **Webhooks** ➔ **Make a web request**.
   - **URL**: `https://api.github.com/repos/damiththa/water-me-please/dispatches`
   - **Method**: `POST`
   - **Content Type**: `application/json`
   - **Additional Headers**:
     ```
     Accept: application/vnd.github+json
     Authorization: Bearer YOUR_GITHUB_PAT_HERE
     User-Agent: IFTTT-Flic-Applet
     ```
   - **Body**:
     ```json
     {"event_type": "flic_water_all"}
     ```
5. Click **Finish** and activate the Applet.

---

## 3. How It Works in Operation

1. **Press Flic Button**: Located right next to your TRMNL display.
2. **IFTTT Trigger**: Fires the webhook to GitHub API in ~1 second.
3. **GitHub Action Execution**: GitHub triggers `sync.yml` on the `main` branch.
4. **Airtable Update**: `sync.py` identifies all due/overdue plants, calculates new watering dates, and batch-updates Airtable.
5. **Instant Screen Feedback**: `sync.py` posts the updated payload directly to your TRMNL Webhook URL, refreshing your e-ink screen in 2–5 seconds with the zero-plants state ("All plants happy! 🎉").

---

## 4. Built-In Safeguards

- **Debounce / Duplicate Press**: If pressed when 0 plants are due, the script cleanly logs `No plants currently due for watering` without altering any dates.
- **Error Resiliency**: If Airtable or network calls encounter an error, it logs clean warnings without breaking.
