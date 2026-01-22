<script setup>
import { computed } from 'vue';

const props = defineProps({
  minRes: { type: Number, default: 0 },
  maxRes: { type: Number, default: 100 },
  minNonRes: { type: Number, default: 0 },
  maxNonRes: { type: Number, default: 100 }
});

const RES_COLORS = ['#FFEDF0', '#FFC9D4', '#FF9FAD', '#FF6384', '#DC143C', '#8B0000'];
const NON_RES_COLORS = ['#F1F7FF', '#D6E6FF', '#B0D0FF', '#7FB5FF', '#4292C6', '#08519C'];
const UNK_COLORS = ['#FAFAFA', '#E0E0E0', '#BDBDBD', '#9E9E9E', '#616161', '#212121'];

// Generate CSS gradient for continuous colormap
function generateGradient(colors) {
  const stops = colors.map((color, index) => {
    const percent = (index / (colors.length - 1)) * 100;
    return `${color} ${percent}%`;
  }).join(', ');
  return `linear-gradient(to right, ${stops})`;
}

const resGradient = computed(() => generateGradient(RES_COLORS));
const nonResGradient = computed(() => generateGradient(NON_RES_COLORS));
const unkGradient = computed(() => generateGradient(UNK_COLORS));
</script>

<template>
  <div class="legend-container">
    <h4>Map Legend (Occupancy)</h4>
    <div class="legend-grid">
      
      <div class="legend-col">
        <h5>Residential</h5>
        <div class="gradient-bar" :style="{ background: resGradient }"></div>
        <div class="legend-labels">
          <span class="label-min">{{ minRes }}</span>
          <span class="label-max">{{ maxRes }}</span>
        </div>
        <div class="legend-note">2nd-98th percentile</div>
      </div>

      <div class="legend-col">
        <h5>Non-Residential</h5>
        <div class="gradient-bar" :style="{ background: nonResGradient }"></div>
        <div class="legend-labels">
          <span class="label-min">{{ minNonRes }}</span>
          <span class="label-max">{{ maxNonRes }}</span>
        </div>
        <div class="legend-note">2nd-98th percentile</div>
      </div>

      <div class="legend-col">
        <h5>Unknown</h5>
        <div class="gradient-bar" :style="{ background: unkGradient }"></div>
        <div class="legend-labels">
          <span class="label-min">0</span>
          <span class="label-max">100</span>
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
  margin: 0 0 8px 0;
  font-size: 11px;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 600;
}

.gradient-bar {
  width: 100%;
  height: 20px;
  border: 1px solid #ddd;
  border-radius: 3px;
  margin-bottom: 4px;
}

.legend-labels {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  color: #666;
}

.label-min,
.label-max {
  font-weight: 500;
}

.legend-note {
  font-size: 9px;
  color: #999;
  margin-top: 2px;
  font-style: italic;
}
</style>