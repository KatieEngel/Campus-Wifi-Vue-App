from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import geopandas as gpd
import pandas as pd
import json
import jellyfish
from pathlib import Path
from typing import List, Optional

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


# Helper function
def fuzzy_matching(building_name: str):
    df = app.state.gdf
    df['match_score'] = df[NAME_COL].apply(
        lambda x: jellyfish.damerau_levenshtein_distance(building_name.lower(), x.lower())
    )
    
    # 2. Sort by the score (smallest distance first) and take top 3
    top_matches = df.sort_values(by='match_score', ascending=True).head(3)

    return top_matches


# endpoint: bldg_name -> bldg_code
@app.get("/get-code/{building_name}")
async def get_code_from_name(building_name: str):
    df = app.state.gdf
    
    # Test 1: try to find EXACT match
    # find rows where the name matches (case-insensitive)
    # .str.lower() for case insensitivity
    result = df[df[NAME_COL].str.lower() == building_name.lower()]

    if not result.empty:
        return {"name": result.iloc[0][NAME_COL], "code": result.iloc[0][CODE_COL]}
    
    # Test 2: Substring Match (The Fix) ---
    # Good for: "Library" -> Matches "Gilbert Memorial Library"
    # We look for rows where the Name contains the Input
    substring_matches = df[df[NAME_COL].str.lower().str.contains(building_name, regex=False)]
    
    if not substring_matches.empty:
        # Optimization: If multiple buildings contain "Library", 
        # usually the shortest one is the most generic/correct one, 
        # or you just pick the first one.
        # Let's pick the one with the shortest name to avoid "The Library of Science" if "Library" exists.
        best_match = substring_matches.loc[substring_matches[NAME_COL].str.len().idxmin()]
        
        return {
            "name": best_match[NAME_COL], 
            "code": best_match[CODE_COL],
            "note": f"Found via substring search. Did you mean '{best_match[NAME_COL]}'?"
        }
    
    # Test 3: Fuzzy Match (Fallback) ---
    # Good for: "Libary" (Typos)
    fuzzy_result = fuzzy_matching(building_name)
    
    if not fuzzy_result.empty:
        best_match = fuzzy_result.iloc[0]
        return {
            "name": best_match[NAME_COL], 
            "code": best_match[CODE_COL],
            "note": f"Exact match not found. Did you mean '{best_match[NAME_COL]}'?"
        }
    
    # if nothing was returned, then we couldn't find anything
    raise HTTPException(status_code=404, detail="Building not found")

# endpoint: bldg_code -> bldg_name
@app.get("/get-name/{building_code}")
async def get_name_from_code(building_code: str):
    df = app.state.gdf
    
    # Test 1: find rows where the code matches EXACTLY
    result = df[df[CODE_COL].str.lower() == building_code.lower()]
    
    if not result.empty:
        return {"name": result.iloc[0][NAME_COL], "code": result.iloc[0][CODE_COL]}
    
    # Test 2: Zero Padding
    # User typed "77". We try turning it into "077" (standard 3-digit code)
    # .zfill(3) turns "7" -> "007", "77" -> "077"
    padded_input = building_code.zfill(3)
    
    # Only run this check if the padded version is actually different from what they typed
    if padded_input != building_code:
        result = df[df[CODE_COL] == padded_input]
        
        if not result.empty:
            best_match = result.iloc[0]
            return {
                "name": best_match[NAME_COL], 
                "code": best_match[CODE_COL],
                "note": f"Match found by adding leading zeros. Did you mean '{best_match[CODE_COL]}'?"
            }
    
    # Test 3: Substring Match (The Fix) ---
    # Good for: "Library" -> Matches "Gilbert Memorial Library"
    # We look for rows where the Name contains the Input
    substring_matches = df[df[CODE_COL].str.lower().str.contains(building_code.lower(), regex=False)]
    
    if not substring_matches.empty:
        # Optimization: If multiple buildings contain "Library", 
        # usually the shortest one is the most generic/correct one, 
        # or you just pick the first one.
        # Let's pick the one with the shortest name to avoid "The Library of Science" if "Library" exists.
        best_match = substring_matches.loc[substring_matches[CODE_COL].str.len().idxmin()]
        
        return {
            "name": best_match[NAME_COL], 
            "code": best_match[CODE_COL],
            "note": f"Found via substring search. Did you mean '{best_match[CODE_COL]}'?"
        }

    # if nothing was returned, then we couldn't find anything
    raise HTTPException(status_code=404, detail="Building not found")