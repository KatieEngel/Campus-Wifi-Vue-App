# GT Campus Wi-Fi Occupancy Visualization Platform

![Status](https://img.shields.io/badge/Status-Proof_of_Concept-yellow.svg)
![Version](https://img.shields.io/badge/Version-2.0_Vue_Migration-blue.svg)
![Lab](https://img.shields.io/badge/Lab-ASDL_Smart_Campus-003057.svg)

## 📖 Project Overview
The **GT Campus Wi-Fi Occupancy Visualization** is a spatial analytics research tool developed within the **Aerospace Systems Design Laboratory (ASDL)**. Its primary objective is to model and visualize real-time human occupancy patterns across the Georgia Tech campus.

By processing aggregated Wi-Fi network connection logs (1.3M+ records), this tool provides a proxy for human density in 146 campus facilities. This data enables infrastructure managers to identify underutilized spaces, correlate occupancy with energy consumption, and predict peak traffic loads.

### 🏗️ Architectural Evolution
This repository documents the evolution of the tool from a rapid prototype to a scalable web application:
* **v1 (Streamlit Prototype):** Initially built as a monolithic Python script for data validation and quick visual prototyping. While effective for small datasets, it faced performance bottlenecks during interactive re-rendering of large spatial datasets.
* **v2 (Current Architecture):** A complete re-architecture using a decoupled **Client-Server model**. This migration was undertaken to improve rendering performance, enable asynchronous data querying, and provide a extensible foundation for future API integrations.

---

## 🚀 Key Features

### 1. Spatiotemporal Analytics
* **Dynamic Heatmaps:** Visualizes occupancy density using dynamic choropleth scaling relative to building capacity (Residential vs. Non-Residential categorization).
* **Timeline Analysis:** Interactive time-series charts allow users to drill down into specific dates and 10-minute time intervals to observe daily traffic flow.

### 2. High-Performance Microservice Backend
* **FastAPI & GeoPandas:** The backend loads 50MB+ of Parquet and GeoJSON data into memory at startup, serving spatial queries in <15ms.
* **"Smart Search" Algorithm:** A custom fuzzy-matching engine (utilizing Jaro-Winkler distance) resolves user typos and colloquialisms (e.g., mapping *"Culc"* to *"Clough Undergraduate Learning Commons"*), prioritizing exact facility codes first.

### 3. Reactive Frontend
* **Vue.js & Leaflet:** The client-side application manages map state independently of the server, eliminating full-page reloads and allowing for smooth "Fly-To" animations and instant feedback.

---

## 🛠️ System Architecture

The project follows a **Monorepo** structure separating the API and Client logic to support future deployment containers.

```text
gt-wifi-occupancy/
├── backend/               # FastAPI Microservice (Python)
│   ├── main.py            # API Endpoints, Data Loading, & Search Logic
│   ├── requirements.txt   # Python Dependencies
│   └── venv/              # Local Python Environment
│
├── frontend/              # Vue.js Client (Node.js/Vite)
│   ├── src/
│   │   ├── components/    # Reusable UI Components (CampusMap, OccupancyChart, MapLegend)
│   │   └── App.vue        # Main Layout & State Orchestration
│   └── package.json       # Frontend Dependencies
│
├── data/                  # Read-Only Data Store
│   ├── ten_min_occupancy_summary.parquet  # Aggregated Time-series data
│   └── campus_buildings_categories.geojson # Campus Geometry & Metadata
│
└── prototype_v1/          # Archived Streamlit Prototype (Reference)
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
The API will start at http://127.0.0.1:8000 (Documentation available at /docs).

### 3. Frontend Setup (Client)
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