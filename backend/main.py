from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import geopandas as gpd
import pandas as pd
import json
import jellyfish
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent
# Adjust these paths to where your actual data files are
DATA_DIR = BASE_DIR.parent / "data" 
PARQUET_FILE = DATA_DIR / "ten_min_occupancy_summary.parquet"
GEOJSON_FILE = DATA_DIR / "campus_buildings_categories.geojson"

# Global storage for data
db = {
    "data": None,     # The massive time-series data
    "campus": None,   # The building shapes
    "dates": []       # List of available dates
}

def classify_building_type(bldg_type):
    """Helper to categorize buildings"""
    if pd.isna(bldg_type): return 'Unknown'
    bldg_type_lower = str(bldg_type).lower()
    if any(keyword in bldg_type_lower for keyword in ['residence', 'dormitory', 'housing', 'greek']):
        return 'Residential'
    else:
        return 'Non-Residential'

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Loading Data... this might take a moment.")
    
    # 1. Load Parquet Data
    if PARQUET_FILE.exists():
        df = pd.read_parquet(PARQUET_FILE)

        df['BLDG_CODE'] = df['BLDG_CODE'].astype(str).str.replace(r'\.0$', '', regex=True)

        # Process dates
        df['time_bin'] = pd.to_datetime(df['time_bin'])
        df['date_str'] = df['time_bin'].dt.strftime('%Y-%m-%d') # String for easy filtering
        df['hour'] = df['time_bin'].dt.hour
        df['minute'] = df['time_bin'].dt.minute
        
        # Remove incomplete day logic (from your streamlit code)
        df = df[df['date_str'] != "2025-04-13"]
        db["data"] = df
        db["dates"] = sorted(df['date_str'].unique().tolist())
        print(f"Loaded {len(df)} occupancy records.")
    else:
        print(f"❌ Error: Parquet file not found at {PARQUET_FILE}")

    # 2. Load GeoJSON Geometry
    if GEOJSON_FILE.exists():
        with open(GEOJSON_FILE, 'r') as f:
            raw_geo = json.load(f)
        campus_gdf = gpd.GeoDataFrame.from_features(raw_geo['features'], crs="EPSG:4326")

        if 'BLDG_CODE' in campus_gdf.columns:
             campus_gdf['BLDG_CODE'] = campus_gdf['BLDG_CODE'].astype(str).str.replace(r'\.0$', '', regex=True)
        
        # Apply Classification
        if 'BLDG_TYPE' in campus_gdf.columns:
            campus_gdf['building_category'] = campus_gdf['BLDG_TYPE'].apply(classify_building_type)
        else:
            campus_gdf['building_category'] = "Unknown"
            
        db["campus"] = campus_gdf
        print(f"   Loaded {len(campus_gdf)} building geometries.")
    else:
        print(f"❌ Error: GeoJSON file not found at {GEOJSON_FILE}")
        
    yield
    db["data"] = None
    db["campus"] = None

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow Vue to connect
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ENDPOINTS ---

@app.get("/metadata")
def get_metadata():
    """Returns available dates and building categories"""
    if db["campus"] is None: return {"error": "Data not loaded"}
    
    return {
        "dates": db["dates"],
        "categories": list(db["campus"]['building_category'].unique())
    }

@app.get("/heatmap")
def get_heatmap(date: str, hour: int, minute: int):
    """
    Returns GeoJSON with occupancy data for a specific time slot.
    """
    df = db["data"]
    campus = db["campus"]
    
    if df is None or campus is None:
        raise HTTPException(status_code=500, detail="Data not loaded")

    # 1. Filter Data
    filtered = df[
        (df['date_str'] == date) & 
        (df['hour'] == hour) & 
        (df['minute'] == minute)
    ]
    
    # 2. Merge with Geometry
    # We do a LEFT join on the Campus map, so buildings with 0 occupancy still show up
    merged = campus.merge(
        filtered[['BLDG_CODE', 'occupancy']], 
        on='BLDG_CODE', 
        how='left'
    )
    
    # Fill NaN with 0
    merged['occupancy'] = merged['occupancy'].fillna(0).astype(int)
    
    # Convert to JSON string then dict
    return json.loads(merged.to_json())

@app.get("/timeline")
def get_timeline(date: str):
    """
    Returns aggregated timeline data for the charts
    """
    df = db["data"]
    if df is None: raise HTTPException(status_code=500, detail="Data not loaded")

    daily_data = df[df['date_str'] == date].copy()
    
    if daily_data.empty: return []

    # Aggregation Logic (Same as Streamlit)
    # 1. By Category
    df_cat = daily_data.groupby(['time_bin', 'building_category'])['occupancy'].sum().reset_index()
    
    # 2. Total
    df_total = daily_data.groupby('time_bin')['occupancy'].sum().reset_index()
    df_total['building_category'] = 'Total'
    
    combined = pd.concat([df_cat, df_total])
    
    # Format for frontend: List of dicts
    result = []
    for _, row in combined.iterrows():
        result.append({
            "time": row['time_bin'].strftime('%H:%M'),
            "category": row['building_category'],
            "occupancy": int(row['occupancy'])
        })
        
    return result

# configuring column names
NAME_COL = "BLDG_NAME" 
CODE_COL = "BLDG_CODE" 


def find_building_match(query: str, df: gpd.GeoDataFrame):
    """
    Unified logic to find a building by Code OR Name.
    Returns the best matching Row (Series) or None.
    """
    query_str = str(query).strip()
    query_lower = query_str.lower()

    # --- STRATEGY 1: CHECK BY CODE ---
    # If the input is short (e.g. "077", "77"), it's likely a code.
    
    # 1a. Exact Code Match
    code_match = df[df[CODE_COL].astype(str).str.lower() == query_lower]
    if not code_match.empty:
        return code_match.iloc[0]

    # 1b. Zero-Padded Code Match (e.g. "77" -> "077")
    if query_str.isdigit():
        padded_code = query_str.zfill(3)
        padded_match = df[df[CODE_COL].astype(str) == padded_code]
        if not padded_match.empty:
            return padded_match.iloc[0]

    # --- STRATEGY 2: CHECK BY NAME ---
    
    # 2a. Exact Name Match
    name_match = df[df[NAME_COL].astype(str).str.lower() == query_lower]
    if not name_match.empty:
        return name_match.iloc[0]

    # 2b. Substring Match (e.g. "Library" -> "Price Gilbert Library")
    # We use regex=False for simple string containment
    substring_matches = df[df[NAME_COL].astype(str).str.lower().str.contains(query_lower, regex=False)]
    
    if not substring_matches.empty:
        # Optimization: Pick the shortest name (usually the most generic/correct one)
        # e.g., prefer "Library" over "Library Extension Building" if possible
        best_idx = substring_matches[NAME_COL].astype(str).str.len().idxmin()
        return substring_matches.loc[best_idx]

    # 2c. Fuzzy Match (Jellyfish)
    # This is your logic for handling typos like "Libary"
    # We calculate score for ALL rows (a bit slow, but fine for <500 buildings)
    df = df.copy() # Work on a copy to avoid warnings
    df['match_score'] = df[NAME_COL].astype(str).apply(
        lambda x: jellyfish.damerau_levenshtein_distance(query_lower, x.lower())
    )
    
    # Sort by score (ascending distance)
    # A distance of 0 is exact, 1 is one typo, etc.
    # We require a reasonably close match (e.g., distance < 5)
    best_fuzzy = df.sort_values(by='match_score', ascending=True).iloc[0]
    
    # Threshold: If the "best" match is still very different, ignore it.
    # (Length difference serves as a rough heuristic)
    if best_fuzzy['match_score'] < 5: 
        return best_fuzzy

    return None

@app.get("/search")
def search_building(q: str):
    """
    Smart Search: Accepts Name OR Code, returns coordinates for Map Zoom.
    """
    if db["campus"] is None:
        raise HTTPException(status_code=500, detail="Data not loaded")
    
    campus = db["campus"]
    
    # Use our unified logic
    match = find_building_match(q, campus)
    
    if match is None:
        raise HTTPException(status_code=404, detail="Building not found")
    
    # Calculate Centroid for the Map Zoom
    centroid = match.geometry.centroid
    
    return {
        "name": match[NAME_COL],
        "code": match[CODE_COL],
        "lat": centroid.y,
        "lon": centroid.x,
        "category": match.get('building_category', 'Unknown')
    }