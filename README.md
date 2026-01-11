# GT Campus Wi-Fi Occupancy Visualization Platform (v2)

![Status](https://img.shields.io/badge/Status-Production-green.svg)
![Stack](https://img.shields.io/badge/Stack-Vue.js_%7C_FastAPI-blue.svg)
![Deployment](https://img.shields.io/badge/Deploy-Netlify_%2B_Render-orange.svg)

## 📖 Project Overview
The **GT Campus Wi-Fi Occupancy Visualization** is a spatial analytics research tool developed within the **Aerospace Systems Design Laboratory (ASDL)**. Its primary objective is to model and visualize human occupancy patterns across the Georgia Tech campus.

By processing over **1.3 million** Wi-Fi connection logs from 146 campus facilities, this data enables infrastructure managers to identify underutilized spaces, correlate occupancy with energy consumption, and predict peak traffic loads.

### 🏗️ Architectural Evolution
This project represents a complete re-engineering of an initial data science prototype into a scalable web application.

* **[View the Legacy Prototype (v1)](./prototype_v1)**: Originally built in **Streamlit**. While effective for data validation, the monolithic architecture required reloading the entire map payload (5MB+) on every interaction, causing significant latency.
* **Current Production (v2)**: Re-architected as a **Decoupled Client-Server Application**. I migrated the frontend to **Vue.js** for non-blocking UI updates and built a **FastAPI** microservice for high-performance spatial querying.

---

## 🚀 Key Engineering Optimizations

### 1. "Static Geometry, Dynamic Data" Architecture
To solve the bandwidth bottlenecks of v1, I implemented a split-loading strategy:
* **The Problem:** Sending complex building shapes (GeoJSON) every time the user moved the time slider caused massive network lag.
* **The Solution:** The heavy geometry is loaded **once** and cached by the client (`/geometry`). When the user scrubs the timeline, the app requests *only* a lightweight JSON list of occupancy integers (`/occupancy`), reducing network payload size by **98%** and making the UI interaction instant.

### 2. The "Bridge" ID Normalization
Integrating disparate datasets (Facility GIS Data vs. Network Logs) resulted in conflicting identifiers (e.g., `051F` vs `51` vs `191N`).
* **Algorithm:** Implemented a backend "Bridge" layer that maps clean integer IDs from the data pipeline to multiple string keys in the geospatial layer. This ensures data integrity even when one facility (e.g., "North Avenue Apts") is represented by multiple distinct polygons on the map.

### 3. Fuzzy Search & Debouncing
* **Smart Search:** Uses **Jaro-Winkler distance** to handle user typos (e.g., mapping *"Culc"* $\to$ *"Clough Undergraduate Learning Commons"*).
* **Debouncing:** The time slider utilizes a 100ms debounce function to prevent API flooding during rapid user interactions.

---

## 🛠️ Technical Architecture

The project follows a **Monorepo** structure:

```text
gt-wifi-occupancy/
├── backend/               # FastAPI Microservice (Python)
│   ├── main.py            # API Endpoints, Bridge Logic, & Search
│   └── requirements.txt   # Data Science Dependencies
│
├── frontend/              # Vue.js Client (Node.js/Vite)
│   ├── src/components/    # Reusable UI (CampusMap, OccupancyChart)
│   └── App.vue            # State Management & Orchestration
│
├── data/                  # Read-Only Data Store
│   ├── ten_min_occupancy_summary.parquet  # Optimized Columnar Data
│   └── campus_buildings_categories.geojson # Spatial Geometry
```

---

## 💻 Setup & Installation

### Prerequisites
* **Python 3.9+**
* **Node.js 18+** (Required for Vue.js frontend)

### 1. Data Configuration
Ensure the following files are present in the `data/` directory before starting:
* `ten_min_occupancy_summary.parquet:` The processed occupancy dataset.

* `campus_buildings_categories.geojson:` The spatial boundaries for GT facilities.

### 2. Backend Setup (API)
The backend handles data processing and search logic.
Open a terminal and navigate to the backend directory:

```bash
cd backend

# Create and activate virtual environment
python -m venv venv

# Windows:
.\venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the development server
fastapi dev main.py
```
The API will start at http://127.0.0.1:8000.

### 3. Frontend Setup (Client)
The frontend handles the Map UI and Charts.
Open a new terminal window and navigate to the frontend directory:

```bash
cd frontend

# Install Node dependencies
npm install

# Start the development client
npm run dev
```
The application will launch in your browser at http://localhost:5173.

---

## 🧠 API Documentation (Search Logic)
The core engineering innovation in v2 is the Search Logic located in backend/main.py. It resolves facility lookups through a step-by-step process.

* **0. Colloquialisms:** Checks if input is a known alias (e.g., "culc" = "Clough Building")
* **1. Exact Code Match:** Checks if input is a known 3-digit Facility ID (e.g., "077").
* **2. Substring Search:** Checks if input is a strict substring of a building name.
* **3. Fuzzy String Matching:** Calculates similarity scores for all 146 buildings.
   * **Score > 0.9:** High confidence; API returns an exact match type and coordinates for auto-zoom.
   * **Score > 0.6:** Low confidence; API returns a suggestion list for the frontend "Did you mean?" dropdown.
   * **Score < 0.6:** Query rejected as invalid.

---

## 👥 Contributors
* **Katie Engel** - Architecture, API, Vue.js Migration, Data Modeling & Analysis
* **Yameen Ahmed** - Data Modeling & Analysis

**Lab:** Aerospace Systems Design Laboratory (ASDL), Georgia Institute of Technology.