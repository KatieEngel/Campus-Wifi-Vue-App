<script setup>
// 1. Define the exact same colors from your Map logic
const RES_COLORS = ['#FFEDF0', '#FFC9D4', '#FF9FAD', '#FF6384', '#DC143C', '#8B0000'];
const NON_RES_COLORS = ['#F1F7FF', '#D6E6FF', '#B0D0FF', '#7FB5FF', '#4292C6', '#08519C'];
// Define a simple gray scale for Unknown
const UNK_COLORS = ['#FAFAFA', '#E0E0E0', '#BDBDBD', '#9E9E9E', '#616161', '#212121'];

// 2. Define the text labels matching your getColor thresholds
const RANGES = ["0", "1 - 5", "6 - 15", "16 - 30", "31 - 50", "50+"];
</script>

<template>
  <div class="legend-container">
    <h4>Map Legend</h4>
    <div class="legend-grid">
      
      <div class="legend-col">
        <h5>Residential</h5>
        <div v-for="(color, index) in RES_COLORS" :key="'res-'+index" class="legend-item">
          <span class="color-box" :style="{ backgroundColor: color }"></span>
          <span class="label">{{ RANGES[index] }}</span>
        </div>
      </div>

      <div class="legend-col">
        <h5>Non-Residential</h5>
        <div v-for="(color, index) in NON_RES_COLORS" :key="'non-'+index" class="legend-item">
          <span class="color-box" :style="{ backgroundColor: color }"></span>
          <span class="label">{{ RANGES[index] }}</span>
        </div>
      </div>

      <div class="legend-col">
        <h5>Unknown</h5>
        <div v-for="(color, index) in UNK_COLORS" :key="'unk-'+index" class="legend-item">
          <span class="color-box" :style="{ backgroundColor: color }"></span>
          <span class="label">{{ RANGES[index] }}</span>
        </div>
      </div>

    </div>
  </div>
</template>

<style scoped>
.legend-container {
  padding: 15px;
  border-top: 1px solid #eee; /* Divider line */
  background: white;
}

h4 {
  margin: 0 0 10px 0;
  font-size: 14px;
  color: #333;
}

.legend-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr; /* 3 equal columns */
  gap: 15px;
}

h5 {
  margin: 0 0 8px 0;
  font-size: 12px;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.legend-item {
  display: flex;
  align-items: center;
  margin-bottom: 4px;
}

.color-box {
  width: 16px;
  height: 16px;
  margin-right: 8px;
  border: 1px solid #ddd;
  border-radius: 2px;
}

.label {
  font-size: 12px;
  color: #444;
}
</style>