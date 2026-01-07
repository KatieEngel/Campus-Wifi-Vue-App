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

      <CampusMap 
        :geoJsonData="heatmapData" 
        :renderKey="mapRenderKey" 
      />
      
      <div class="graphs-placeholder">
        <h3>Occupancy Timeline</h3>
        <OccupancyChart 
          :timelineData="timelineData" 
          :selectedTime="formatTimeDisplay(timeValue)"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.dashboard {
  display: flex;
  height: 100vh;
  font-family: Arial, sans-serif;
}

.sidebar {
  width: 300px;
  background-color: #f8f9fa;
  padding: 20px;
  border-right: 1px solid #ddd;
}

.main-content {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
}

.control-group {
  margin-bottom: 20px;
}

.control-group label {
  display: block;
  font-weight: bold;
  margin-bottom: 5px;
}

input[type=range], select {
  width: 100%;
}

.graphs-placeholder {
  margin-top: 20px;
  padding: 20px;
  background: #f0f0f0;
  border-radius: 8px;
  text-align: center;
  color: #666;
}
</style>