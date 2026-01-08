<script setup>
import { computed } from 'vue';

const props = defineProps({
  maxRes: { type: Number, default: 100 },
  maxNonRes: { type: Number, default: 100 }
});


const RES_COLORS = ['#FFEDF0', '#FFC9D4', '#FF9FAD', '#FF6384', '#DC143C', '#8B0000'];
const NON_RES_COLORS = ['#F1F7FF', '#D6E6FF', '#B0D0FF', '#7FB5FF', '#4292C6', '#08519C'];
const UNK_COLORS = ['#FAFAFA', '#E0E0E0', '#BDBDBD', '#9E9E9E', '#616161', '#212121'];

function generateRanges(maxVal) {
  const steps = [];
  steps.push("0"); // Index 0 is always just 0

  // We have 5 buckets for the remaining value (1 to Max)
  // Buckets: 0-20%, 20-40%, 40-60%, 60-80%, 80-100%
  for (let i = 1; i <= 5; i++) {
    const lowerRatio = (i - 1) * 0.2;
    const upperRatio = i * 0.2;
    
    // Calculate integers
    const start = Math.floor(maxVal * lowerRatio) + 1;
    let end = Math.floor(maxVal * upperRatio);
    
    // Edge case: ensure end is at least start
    if (end < start) end = start;
    
    // Formatting the string
    if (i === 1) {
      // First bucket starts at 1
      steps.push(`1 - ${end}`);
    } else if (i === 5) {
      // Last bucket
      steps.push(`${start} - ${maxVal}`);
    } else {
      steps.push(`${start} - ${end}`);
    }
  }
  return steps;
}

// Reactive Computed Properties
// Whenever props.maxRes changes, this recalculates the labels immediately
const resRanges = computed(() => generateRanges(props.maxRes));
const nonResRanges = computed(() => generateRanges(props.maxNonRes));

// Unknown usually doesn't scale, so we keep it generic or scale to 100
const unkRanges = computed(() => generateRanges(100));
</script>

<template>
  <div class="legend-container">
    <h4>Map Legend (Occupancy)</h4>
    <div class="legend-grid">
      
      <div class="legend-col">
        <h5>Residential</h5>
        <div v-for="(color, index) in RES_COLORS" :key="'res-'+index" class="legend-item">
          <span class="color-box" :style="{ backgroundColor: color }"></span>
          <span class="label">{{ resRanges[index] }}</span>
        </div>
      </div>

      <div class="legend-col">
        <h5>Non-Residential</h5>
        <div v-for="(color, index) in NON_RES_COLORS" :key="'non-'+index" class="legend-item">
          <span class="color-box" :style="{ backgroundColor: color }"></span>
          <span class="label">{{ nonResRanges[index] }}</span>
        </div>
      </div>

      <div class="legend-col">
        <h5>Unknown</h5>
        <div v-for="(color, index) in UNK_COLORS" :key="'unk-'+index" class="legend-item">
          <span class="color-box" :style="{ backgroundColor: color }"></span>
          <span class="label">{{ unkRanges[index] }}</span>
        </div>
      </div>

    </div>
  </div>
</template>

<style scoped>
.legend-container {
  padding: 12px 15px;
  border-top: 1px solid #eee; /* Divider line */
  background: white;
  z-index: 10;
}

h4 {
  margin: 0 0 10px 0;
  font-size: 13px;
  font-weight: 600;
  color: #333;
}

.legend-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr; /* 3 equal columns */
  gap: 15px;
}

h5 {
  margin: 0 0 6px 0;
  font-size: 11px;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 600;
}

.legend-item {
  display: flex;
  align-items: center;
  margin-bottom: 3px;
}

.color-box {
  width: 14px;
  height: 14px;
  margin-right: 8px;
  border: 1px solid #ddd;
  border-radius: 2px;
  flex-shrink: 0;
}

.label {
  font-size: 11px;
  color: #444;
  white-space: nowrap;
}
</style>