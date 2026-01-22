<script setup>
import { ref, onMounted, watch, computed } from 'vue';
import CampusMap from './components/CampusMap.vue';
import OccupancyChart from './components/OccupancyChart.vue';
import MapLegend from './components/MapLegend.vue';

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

// State
const dates = ref([]);
const selectedDate = ref('');
const timeValue = ref(720); // Minutes from midnight (12:00 PM default)

// Data State
const geometryData = ref(null);   // Static Shapes
const occupancyData = ref([]);    // Dynamic Numbers
const timelineData = ref([]);

// Fixed color scale min/max values (set once from metadata, using quantiles)
const globalMinRes = ref(0);
const globalMaxRes = ref(100);
const globalMinNonRes = ref(0);
const globalMaxNonRes = ref(100);

const loading = ref(false);

// Map/Search State
const searchQuery = ref("");
const mapTarget = ref(null);
const searchSuggestions = ref([]);
const showSuggestions = ref(false);
const currentMinRes = ref(0);
const currentMaxRes = ref(100);
const currentMinNonRes = ref(0);
const currentMaxNonRes = ref(100);

// Helper to convert slider (0-1440) to Hour/Minute
function minsToTime(val) {
  const h = Math.floor(val / 60);
  const m = val % 60;
  // Round to nearest 10
  const m_rounded = Math.floor(m / 10) * 10;
  return { h, m: m_rounded };
}

// Helper to display time string
function formatTimeDisplay(val) {
  const { h, m } = minsToTime(val);
  const ampm = h >= 12 ? 'PM' : 'AM';
  const h12 = h % 12 || 12;
  const mStr = m.toString().padStart(2, '0');
  return `${h12}:${mStr} ${ampm}`;
}

// Helper to get 24-hour format for the Chart matching (e.g., "13:30")
function formatTime24(val) {
  const { h, m } = minsToTime(val);
  const hStr = h.toString().padStart(2, '0');
  const mStr = m.toString().padStart(2, '0');
  return `${hStr}:${mStr}`;
}

function handleMaxUpdate(payload) {
  currentMaxRes.value = payload.maxRes;
  currentMaxNonRes.value = payload.maxNonRes;
  currentMinRes.value = payload.minRes;
  currentMinNonRes.value = payload.minNonRes;
}

// API Calls
async function fetchMetadata() {
  try {
    const res = await fetch(`${API_URL}/metadata`);
    const data = await res.json();
    if (data.dates) {
      dates.value = data.dates;
      if (!selectedDate.value) selectedDate.value = dates.value[0];
    }
    // Set fixed global quantile-based min/max values for consistent color scaling
    if (data.global_min_res !== undefined) globalMinRes.value = data.global_min_res;
    if (data.global_max_res !== undefined) globalMaxRes.value = data.global_max_res;
    if (data.global_min_non_res !== undefined) globalMinNonRes.value = data.global_min_non_res;
    if (data.global_max_non_res !== undefined) globalMaxNonRes.value = data.global_max_non_res;
  } catch (e) { console.error(e); }
}

// Fetch Geometry (Run Once)
async function fetchGeometry() {
  try {
    console.log("Fetching static geometry...");
    const res = await fetch(`${API_URL}/geometry`);
    geometryData.value = await res.json();
  } catch (e) { console.error("Geo Load Fail", e); }
}

// 2. Update Dynamic Data (Run Often)
async function updateDashboard() {
  if (!selectedDate.value) return;
  loading.value = true;
  
  const { h, m } = minsToTime(timeValue.value);
  
  try {
    // A. Fetch Map Numbers (Lightweight)
    const occRes = await fetch(`${API_URL}/occupancy?date=${selectedDate.value}&hour=${h}&minute=${m}`);
    if (occRes.ok) occupancyData.value = await occRes.json();

    // B. Fetch Timeline (Only needs to run if Date changes, but safe to run here)
    // We can optimize this to only run when 'date' changes if we wanted.
    const chartRes = await fetch(`${API_URL}/timeline?date=${selectedDate.value}`);
    if (chartRes.ok) timelineData.value = await chartRes.json();

  } catch (e) {
    console.error(e);
  } finally {
    loading.value = false;
  }
}

// Search Logic
async function handleSearch() {
  if (!searchQuery.value) return;
  showSuggestions.value = false;
  
  try {
    const res = await fetch(`${API_URL}/search?q=${searchQuery.value}`);
    if (res.status === 404) { alert("No match"); return; }
    
    const data = await res.json();
    if (data.type === 'exact') {
      mapTarget.value = { lat: data.data.lat, lon: data.data.lon, name: data.data.name };
      searchQuery.value = "";
    } else if (data.type === 'suggestions') {
      searchSuggestions.value = data.data;
      showSuggestions.value = true;
    }
  } catch (e) { console.error(e); }
}

function acceptSuggestion(name) {
  searchQuery.value = name;
  handleSearch();
}

// Watchers
watch(selectedDate, updateDashboard);

// Debounce Slider
let timeout = null;
watch(timeValue, () => {
  if (timeout) clearTimeout(timeout);
  timeout = setTimeout(() => {
    updateDashboard();
  }, 100); // 100ms delay is enough to feel instant but save bandwidth
});

onMounted(async () => {
  await fetchMetadata(); // Get dates
  fetchGeometry();       // Get shapes
  updateDashboard();     // Get initial numbers
});
</script>

<template>
  <div class="dashboard">
    <div class="sidebar">
      <h2>Options</h2>

      <div class="control-group search-group">
        <label>Find Building</label>
        <div class="search-row">
          <input 
            v-model="searchQuery" 
            @keyup.enter="handleSearch"
            placeholder="e.g. Library" 
          />
          <button @click="handleSearch">Go</button>
        </div>

        <div v-if="showSuggestions" class="suggestions-box">
          <p>Did you mean?</p>
          <ul>
            <li 
              v-for="s in searchSuggestions" 
              :key="s.code" 
              @click="acceptSuggestion(s.name)"
            >
              {{ s.name }}
            </li>
          </ul>
        </div>
      </div>
      <hr class="divider" />
      
      <div class="control-group">
        <label>Select Date</label>
        <select v-model="selectedDate">
          <option v-for="d in dates" :key="d" :value="d">{{ d }}</option>
        </select>
      </div>

      <div class="control-group">
        <label>Select Time: <b>{{ formatTimeDisplay(timeValue) }}</b></label>
        <input 
          type="range" 
          v-model.number="timeValue" 
          min="0" max="1430" step="10" 
        />
      </div>
      
      <div v-if="loading" class="status">Loading data...</div>
    </div>

    <div class="main-content">
      <div class="header">
        <h1>Campus Occupancy Visualizer</h1>
      </div>

      <div class="viz-container">
        
        <div class="map-panel">
          <div style="flex: 1; min-height: 0;">
             <CampusMap 
              :geometry="geometryData" 
              :occupancyData="occupancyData"
              :flyTo="mapTarget"
              :globalMinRes="globalMinRes"
              :globalMaxRes="globalMaxRes"
              :globalMinNonRes="globalMinNonRes"
              :globalMaxNonRes="globalMaxNonRes"
              :selectedDate="selectedDate"
              @update-max="handleMaxUpdate" 
            />
          </div>
          
          <MapLegend 
            :minRes="currentMinRes"
            :maxRes="currentMaxRes" 
            :minNonRes="currentMinNonRes"
            :maxNonRes="currentMaxNonRes" 
          />
        </div>
        
        <div class="chart-panel">
          <h3>Occupancy Timeline</h3>
          <div class="chart-wrapper">
             <OccupancyChart 
              :timelineData="timelineData" 
              :selectedTime="formatTime24(timeValue)"
            />
          </div>
        </div>

      </div>
    </div>
  </div>
</template>

<style>
:root {
  font-family: Inter, system-ui, Avenir, Helvetica, Arial, sans-serif;
  line-height: 1.5;
  font-weight: 400;
}

body {
  margin: 0 !important;      /* Force removal of margins */
  padding: 0 !important;     /* Force removal of padding */
  width: 100vw;
  height: 100vh;
  overflow: hidden;          /* Stop scrollbars */
  display: block !important; /* Override any 'flex' defaults on body */
}

#app {
  width: 100%;
  height: 100%;
  margin: 0;
  padding: 0;
  display: block;            /* Ensure the Vue root div behaves */
}
</style>

<style scoped>
.dashboard {
  display: flex;
  height: 100%;
  width: 100%;
  /* 1. Give the "background" a color (light gray usually looks best) */
  background-color: #f0f2f5; 
  /* 2. Add the "breathing room" around the entire app */
  padding: 12px; 
  /* 3. Add a gap between the sidebar and the main content */
  gap: 12px; 
  box-sizing: border-box;
}

.sidebar {
  width: 300px;
  background-color: #ffffff;
  /* Remove the border-right since we now have a physical gap */
  border: 1px solid #e5e7eb; 
  border-radius: 12px; /* Round the corners */
  padding: 20px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  height: 100%;
  /* Optional: Add a subtle shadow to make it pop */
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); 
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  
  /* --- THE FIX: Make this container invisible --- */
  background-color: transparent; 
  border: none;
  box-shadow: none;
  /* ---------------------------------------------- */
  
  /* Keep padding to ensure panels don't touch the screen edge */
  padding: 0; 
  /* We remove padding here because the .dashboard already has padding: 12px */
  /* If you want MORE space, add padding here, e.g., padding-left: 12px; */
  
  height: 100%;
  overflow: hidden;
}

.header {
  margin-bottom: 12px; /* Reduce gap slightly */
  margin-left: 4px;    /* Align text with the panels */
}

/* Optional: Make the header text dark gray instead of black for polish */
.header h1 {
  margin: 0;
  font-size: 1.5rem;
  color: #1f2937;
}

.viz-container {
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  gap: 20px;
  flex: 1;
  min-height: 0;
}

/* Ensure map and chart panels fill their grid slots */
.map-panel, .chart-panel {
  height: 100%;
  width: 100%;
  background: white;
  border-radius: 8px;
  border: 1px solid #eee;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.chart-panel {
  background: white;
  border-radius: 8px;
  border: 1px solid #eee;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  height: 100%;
  
  /* --- THE FIX --- */
  /* Increase padding (was 15px). */
  /* This creates a white gutter between the border and the chart. */
  padding: 32px;
}

.chart-wrapper {
  flex: 1;
  position: relative;
  min-height: 0;
}

.search-row {
  display: flex;
  gap: 5px;
}

.search-row input {
  flex: 1;
}

.search-row button {
  padding: 8px 12px;
  background-color: #3b82f6; /* Blue */
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: bold;
}

.search-row button:hover {
  background-color: #2563eb;
}

.divider {
  border: 0;
  border-top: 1px solid #ddd;
  margin: 20px 0;
}

.suggestions-box {
  margin-top: 10px;
  background: #fff;
  border: 1px solid #ddd;
  border-radius: 4px;
  padding: 10px;
  box-shadow: 0 2px 5px rgba(0,0,0,0.1);
}

.suggestions-box p {
  margin: 0 0 5px 0;
  font-size: 12px;
  color: #666;
  font-weight: bold;
}

.suggestions-box ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.suggestions-box li {
  padding: 6px;
  font-size: 13px;
  cursor: pointer;
  border-bottom: 1px solid #eee;
  color: #2563eb; /* Link blue */
}

.suggestions-box li:hover {
  background-color: #f0f9ff;
}

.suggestions-box li:last-child {
  border-bottom: none;
}

/* Sidebar Inputs */
.control-group { margin-bottom: 20px; }
.control-group label { display: block; margin-bottom: 5px; font-weight: bold; }
select, input[type=range] { width: 100%; }
</style>