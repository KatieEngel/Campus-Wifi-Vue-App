<script setup>
import { ref, onMounted, watch, computed } from 'vue';
import CampusMap from './components/CampusMap.vue';
import OccupancyChart from './components/OccupancyChart.vue';

// State
const dates = ref([]);
const selectedDate = ref('');
const timeValue = ref(720); // Minutes from midnight (12:00 PM default)
const heatmapData = ref(null);
const timelineData = ref([]);
const loading = ref(false);

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

// API Calls
async function fetchMetadata() {
  try {
    const res = await fetch('http://127.0.0.1:8000/metadata');
    const data = await res.json();
    dates.value = data.dates;
    if(dates.value.length > 0) selectedDate.value = dates.value[0];
  } catch (e) {
    console.error("Backend offline?", e);
  }
  
}

async function updateDashboard() {
  if (!selectedDate.value) return;
  loading.value = true;
  
  const { h, m } = minsToTime(timeValue.value);
  
  try {
    // 1. Fetch Map Data
    const mapRes = await fetch(
      `http://127.0.0.1:8000/heatmap?date=${selectedDate.value}&hour=${h}&minute=${m}`
    );
    const jsonData = await mapRes.json();
    // --- DEBUG LOG ---
    console.log("App.vue received data:", jsonData); 
    // -----------------
    heatmapData.value = jsonData;

    // 2. Fetch Timeline Data (Only needs to happen when Date changes, but safe to call here)
    const chartRes = await fetch(
      `http://127.0.0.1:8000/timeline?date=${selectedDate.value}`
    );
    timelineData.value = await chartRes.json();

  } catch (e) {
    console.error(e);
  } finally {
    loading.value = false;
  }
}

// Create a unique key that changes whenever Date OR Time changes
const mapRenderKey = computed(() => {
  return `${selectedDate.value}-${timeValue.value}`;
});

// Watchers
watch(timeValue, updateDashboard);
watch(selectedDate, updateDashboard);

onMounted(() => {
  fetchMetadata();
});
</script>

<template>
  <div class="dashboard">
    <div class="sidebar">
      <h2>Controls</h2>
      
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
          <CampusMap 
            :geoJsonData="heatmapData" 
            :renderKey="mapRenderKey" 
          />
        </div>
        
        <div class="chart-panel">
          <h3>Occupancy Timeline</h3>
          <div class="chart-wrapper">
             <OccupancyChart 
              :timelineData="timelineData" 
              :selectedTime="formatTimeDisplay(timeValue)"
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

/* Sidebar Inputs */
.control-group { margin-bottom: 20px; }
.control-group label { display: block; margin-bottom: 5px; font-weight: bold; }
select, input[type=range] { width: 100%; }
</style>