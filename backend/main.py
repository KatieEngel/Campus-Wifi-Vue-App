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
from fastapi.exceptions import RequestValidationError
from fastapi.requests import Request
from fastapi.responses import JSONResponse

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
    "dates": [],      # List of available dates
    "global_min_res": 0,      # Global min (2nd percentile) for Residential (fixed scale)
    "global_max_res": 0,     # Global max (98th percentile) for Residential (fixed scale)
    "global_min_non_res": 0, # Global min (2nd percentile) for Non-Residential (fixed scale)
    "global_max_non_res": 0  # Global max (98th percentile) for Non-Residential (fixed scale)
}

def classify_building_type(bldg_type):
    """Helper to categorize buildings"""
    if pd.isna(bldg_type): return 'Unknown'
    bldg_type_lower = str(bldg_type).lower()
    if any(keyword in bldg_type_lower for keyword in ['residence', 'dormitory', 'housing', 'greek']):
        return 'Residential'
    else:
        return 'Non-Residential'

id_bridge = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Loading Data...")
    
    # 1. Load Parquet Data (Keep existing logic)
    try:
        if PARQUET_FILE.exists():
            df = pd.read_parquet(PARQUET_FILE)
            
            # Clean Parquet IDs to be pure numbers (matches your ETL)
            # Remove decimals and leading zeros
            df['BLDG_CODE'] = df['BLDG_CODE'].astype(str).str.replace(r'\.0$', '', regex=True)
            df['BLDG_CODE'] = df['BLDG_CODE'].str.lstrip('0') 
            
            df['time_bin'] = pd.to_datetime(df['time_bin'])
            df['date_str'] = df['time_bin'].dt.strftime('%Y-%m-%d')
            df['hour'] = df['time_bin'].dt.hour
            df['minute'] = df['time_bin'].dt.minute
            df = df[df['date_str'] != "2025-04-13"]
            
            db["data"] = df
            db["dates"] = sorted(df['date_str'].unique().tolist())
            
            # Calculate global quantile-based min/max for each category (FIXED SCALE)
            # Using 2nd and 98th percentiles to avoid outlier skewing
            # This ensures color mapping is consistent across all time periods
            if 'building_category' in df.columns and 'occupancy' in df.columns:
                res_data = df[df['building_category'] == 'Residential']['occupancy']
                non_res_data = df[df['building_category'] == 'Non-Residential']['occupancy']
                
                # Calculate quantiles
                res_min = res_data.quantile(0.02)
                res_max = res_data.quantile(0.98)
                non_res_min = non_res_data.quantile(0.02)
                non_res_max = non_res_data.quantile(0.98)
                
                db["global_min_res"] = int(res_min) if not pd.isna(res_min) else 0
                db["global_max_res"] = int(res_max) if not pd.isna(res_max) else 100
                db["global_min_non_res"] = int(non_res_min) if not pd.isna(non_res_min) else 0
                db["global_max_non_res"] = int(non_res_max) if not pd.isna(non_res_max) else 100
                
                print(f"   ✅ Global quantile ranges (2nd-98th percentile):")
                print(f"      Residential: {db['global_min_res']} - {db['global_max_res']}")
                print(f"      Non-Residential: {db['global_min_non_res']} - {db['global_max_non_res']}")
            else:
                # Fallback if categories not in data
                db["global_min_res"] = 0
                db["global_max_res"] = 100
                db["global_min_non_res"] = 0
                db["global_max_non_res"] = 100
            
            print(f"   ✅ Loaded {len(df)} occupancy records.")
        else:
            print(f"   ❌ Error: Parquet not found")
            db["data"] = None
    except Exception as e:
        print(f"   ❌ Parquet Error: {e}")

    # 2. Load GeoJSON & Build Bridge
    try:
        if GEOJSON_FILE.exists():
            with open(GEOJSON_FILE, 'r') as f:
                geojson_data = json.load(f)
            
            campus_gdf = gpd.GeoDataFrame.from_features(geojson_data["features"])
            
            try:
                campus_gdf.set_crs("EPSG:4326", inplace=True)
            except Exception:
                pass

            # --- BUILD THE BRIDGE (The Fix) ---
            # We iterate through every building in the Map.
            # We calculate what its "Clean ID" would be (digits only).
            # We map the Clean ID to the Real ID.
            if 'BLDG_CODE' in campus_gdf.columns:
                # Ensure Real ID is string
                campus_gdf['BLDG_CODE'] = campus_gdf['BLDG_CODE'].astype(str)
                
                for real_id in campus_gdf['BLDG_CODE'].unique():
                    # Calculate "Clean ID" using the same logic as the Parquet data
                    # 1. Extract digits
                    import re
                    match = re.search(r'(\d+)', real_id)
                    if match:
                        clean_id = match.group(1).lstrip('0')
                        
                        # Add to bridge
                        if clean_id not in id_bridge:
                            id_bridge[clean_id] = []
                        id_bridge[clean_id].append(real_id)
            
            # Note: We DO NOT overwrite BLDG_CODE in the GDF anymore.
            # We keep '191N' as '191N' so the frontend map stays unique.
            
            # Map categories
            if 'BLDG_TYPE' in campus_gdf.columns:
                campus_gdf['building_category'] = campus_gdf['BLDG_TYPE'].apply(classify_building_type)
            else:
                campus_gdf['building_category'] = "Unknown"
                
            db["campus"] = campus_gdf
            print(f"   ✅ Loaded {len(campus_gdf)} buildings. Bridge size: {len(id_bridge)}")
        else:
             print(f"   ❌ Error: GeoJSON not found")
            
    except Exception as e:
        print(f"   ❌ GeoJSON Error: {e}")
        
    yield
    db["data"] = None
    db["campus"] = None

app = FastAPI(lifespan=lifespan)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # This prints the exact error to the Render logs
    print(f"❌ VALIDATION ERROR at {request.url}: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": str(exc)},
    )

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
    """Returns available dates, building categories, and global quantile-based min/max occupancy values"""
    if db["campus"] is None: return {"error": "Data not loaded"}
    
    return {
        "dates": db["dates"],
        "categories": list(db["campus"]['building_category'].unique()),
        "global_min_res": db["global_min_res"],
        "global_max_res": db["global_max_res"],
        "global_min_non_res": db["global_min_non_res"],
        "global_max_non_res": db["global_max_non_res"]
    }

# Static Geometry Endpoint (Called ONCE)
@app.get("/geometry")
def get_campus_geometry():
    """Returns the building shapes (GeoJSON) without occupancy data."""
    if db["campus"] is None:
        raise HTTPException(status_code=500, detail="Data not loaded")
    
    # Return raw GeoJSON. The browser will cache this.
    return json.loads(db["campus"].to_json())

# Update Occupancy Endpoint to use the Bridge
@app.get("/occupancy")
def get_occupancy(date: str, hour: str, minute: str):
    try:
        h = int(float(hour))
        m = int(float(minute))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid format")

    df = db["data"]
    if df is None: raise HTTPException(status_code=500, detail="Data not loaded")
    
    # Filter
    mask = ((df['date_str'] == date) & (df['hour'] == h) & (df['minute'] == m))
    subset = df[mask]
    
    result = []
    
    for _, row in subset.iterrows():
        data_id = row[CODE_COL] # This is the "Clean ID" (e.g. "191")
        count = int(row['occupancy'] if 'occupancy' in row else row.get('device_count', 0))
        
        # LOOKUP: Which Map IDs correspond to this Data ID?
        # If "191" is in the bridge, we get ["191N", "191S"]
        if data_id in id_bridge:
            real_ids = id_bridge[data_id]
            for real_id in real_ids:
                result.append({
                    "code": real_id, # Send "191N" to frontend
                    "count": count   # Send 50
                })
        else:
            # Fallback: Just send the ID as is (maybe it matches exactly)
            result.append({"code": data_id, "count": count})
        
    return result

@app.get("/timeline")
def get_timeline(date: str):
    df = db["data"]
    if df is None: raise HTTPException(status_code=500, detail="Data not loaded")

    daily_data = df[df['date_str'] == date].copy()
    if daily_data.empty: return []

    df_cat = daily_data.groupby(['time_bin', 'building_category'])['occupancy'].sum().reset_index()
    df_total = daily_data.groupby('time_bin')['occupancy'].sum().reset_index()
    df_total['building_category'] = 'Total'
    
    combined = pd.concat([df_cat, df_total])
    
    result = []
    for _, row in combined.iterrows():
        # Ensure timestamp is a string
        t_str = row['time_bin'].strftime('%H:%M')
        result.append({
            "time": t_str,
            "category": row['building_category'],
            "occupancy": int(row['occupancy'])
        })
        
    return result

@app.get("/building-timeseries")
def get_building_timeseries(date: str, code: str):
    """Returns time series occupancy for a specific building on a given date"""
    df = db["data"]
    if df is None: raise HTTPException(status_code=500, detail="Data not loaded")
    
    # Convert building code to clean ID (handle bridge mapping)
    # The code from frontend might be "191N" but data has "191"
    import re
    match = re.search(r'(\d+)', str(code))
    clean_id = match.group(1).lstrip('0') if match else code
    
    # Filter by date and building code
    daily_data = df[df['date_str'] == date].copy()
    if daily_data.empty: return []
    
    building_data = daily_data[daily_data[CODE_COL] == clean_id].copy()
    if building_data.empty: return []
    
    # Sort by time
    building_data = building_data.sort_values('time_bin')
    
    result = []
    for _, row in building_data.iterrows():
        t_str = row['time_bin'].strftime('%H:%M')
        result.append({
            "time": t_str,
            "occupancy": int(row['occupancy'] if 'occupancy' in row else row.get('device_count', 0))
        })
    
    return result

# configuring column names
NAME_COL = "BLDG_NAME" 
CODE_COL = "BLDG_CODE"

# --- NEW: Custom Colloquialisms Dictionary ---
# Keys must be lowercase for case-insensitive matching
CUSTOM_ALIASES = {
    "culc": "Clough Building",
    "clough": "Clough Building",
    "crc": "Campus Recreation Center",
    "mrdc": "Manufacturing Related Disciplines Complex",
    "coc": "College of Computing",
    "klaus": "Klaus Advanced Computing Building",
    "scheller": "Management Building",
    "student center": "John Lewis Student Center",
    "library": "Gilbert Memorial Library",
    "price": "Gilbert Memorial Library",
    "pg": "Gilbert Memorial Library"
}


def find_building_match(query: str, df: gpd.GeoDataFrame):
    """
    Returns a tuple: (MatchType, ResultData)
    MatchType: "exact", "suggestion", or "none"
    """
    query_str = str(query).strip()
    query_lower = query_str.lower()

    # --- 0: MANUAL OVERRIDES (The "Colloquialism" Fix) ---
    # Check if the user typed a known abbreviation like "CULC"
    if query_lower in CUSTOM_ALIASES:
        target_name = CUSTOM_ALIASES[query_lower]
        # Find the row that matches this target name exactly
        # We use .str.contains in case the official name in DB is slightly longer
        alias_match = df[df[NAME_COL].astype(str).str.contains(target_name, case=False, regex=False)]
        
        if not alias_match.empty:
            # Return the first match found
            return "exact", alias_match.iloc[0]
    
    # --- 1. CODE MATCHING (Digits) ---
    if query_str.isdigit():
        # Reject codes longer than 3 digits immediately
        if len(query_str) > 3:
            return "none", []
            
        # Exact or Padded Match (e.g. "77" -> "077")
        padded_code = query_str.zfill(3)
        code_match = df[df[CODE_COL].astype(str) == padded_code]
        
        if not code_match.empty:
            return "exact", code_match.iloc[0]
        
        # If it's a 3-digit number but doesn't exist, don't try to fuzzy match names. 
        # "999" shouldn't match "Building 9" unless you really want it to.
        return "none", []

    # --- 2. NAME MATCHING (Strings) ---
    
    # 2a. Exact Match
    exact_match = df[df[NAME_COL].astype(str).str.lower() == query_lower]
    if not exact_match.empty:
        return "exact", exact_match.iloc[0]

    # 2b. Substring Match (High Confidence)
    # e.g. "Skiles" matches "Skiles Classroom Building"
    substring_matches = df[df[NAME_COL].astype(str).str.lower().str.contains(query_lower, regex=False)]
    if not substring_matches.empty:
        # Pick shortest name (most precise)
        best_idx = substring_matches[NAME_COL].astype(str).str.len().idxmin()
        return "exact", substring_matches.loc[best_idx]

    # 2c. Fuzzy Match (The "Did you mean?" Logic)
    df = df.copy()
    df['match_score'] = df[NAME_COL].astype(str).apply(
        lambda x: jellyfish.jaro_winkler_similarity(query_lower, x.lower())
    )
    
    # Sort by score (Highest first)
    sorted_matches = df.sort_values(by='match_score', ascending=False)
    best_match = sorted_matches.iloc[0]
    best_score = best_match['match_score']
    
    # THRESHOLDS:
    # > 0.90: Almost perfect match (Small typo: "Skilles" -> "Skiles") -> Auto Zoom
    # 0.60 - 0.90: Ambiguous or "Gibberish-ish" -> Return Suggestions
    # < 0.60: Total gibberish -> No Match
    
    if best_score >= 0.90:
        return "exact", best_match
    
    if best_score >= 0.60:
        # Return Top 3 for "Did you mean?"
        top_3 = sorted_matches.head(3)
        return "suggestion", top_3
        
    return "none", []

@app.get("/search")
def search_building(q: str):
    if db["campus"] is None:
        raise HTTPException(status_code=500, detail="Data not loaded")
    
    campus = db["campus"]
    match_type, result = find_building_match(q, campus)
    
    if match_type == "exact":
        # Auto-Zoom
        centroid = result.geometry.centroid
        return {
            "type": "exact",
            "data": {
                "name": result[NAME_COL],
                "code": result[CODE_COL],
                "lat": centroid.y,
                "lon": centroid.x
            }
        }
        
    elif match_type == "suggestion":
        # Return list of options
        suggestions = []
        for _, row in result.iterrows():
            suggestions.append({
                "name": row[NAME_COL],
                "code": row[CODE_COL]
            })
        return {
            "type": "suggestions",
            "message": f"No exact match for '{q}'. Did you mean:",
            "data": suggestions
        }
        
    else:
        raise HTTPException(status_code=404, detail="No building match found.")