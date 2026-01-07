<script setup>
import { computed } from 'vue';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
} from 'chart.js';
import { Line } from 'vue-chartjs';

// Register ChartJS components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

const props = defineProps({
  timelineData: {
    type: Array,
    default: () => []
  },
  selectedTime: String // Expected format: "13:30" (24-hour)
});

// --- CUSTOM PLUGIN: Vertical Line ---
// This draws the red dashed line
const verticalLinePlugin = {
  id: 'verticalLine',
  afterDatasetsDraw(chart, args, options) {
    const { ctx, chartArea: { top, bottom }, scales: { x } } = chart;
    
    // 1. Get the X-axis coordinate for the selected time
    // x.getPixelForValue finds the pixel position of the label "13:30"
    const xPixel = x.getPixelForValue(props.selectedTime);

    // Only draw if the time exists on the axis
    if (xPixel !== undefined && !isNaN(xPixel)) {
      ctx.save();
      ctx.beginPath();
      ctx.lineWidth = 2;
      ctx.strokeStyle = '#FF0000'; // Red
      ctx.setLineDash([6, 6]);     // Dashed pattern
      ctx.moveTo(xPixel, top);
      ctx.lineTo(xPixel, bottom);
      ctx.stroke();
      ctx.restore();
    }
  }
};

// Process data for Chart.js
const chartData = computed(() => {
  if (!props.timelineData.length) return { labels: [], datasets: [] };

  // 1. Get unique time labels (X-axis)
  // We assume data is sorted by time
  const labels = [...new Set(props.timelineData.map(item => item.time))];

  // 2. Helper to filter by category
  const getDataset = (category, color) => {
    return {
      label: category,
      borderColor: color,
      backgroundColor: color,
      data: labels.map(time => {
        const found = props.timelineData.find(d => d.time === time && d.category === category);
        return found ? found.occupancy : 0;
      }),
      tension: 0.3, // Smooth curves
      pointRadius: 0 // Hide dots for cleaner look (optional)
    };
  };

  return {
    labels,
    datasets: [
      getDataset('Total', '#000000'),
      getDataset('Residential', '#DC143C'),
      getDataset('Non-Residential', '#4292C6'),
      getDataset('Unknown', '#737373'),
    ]
  };
});

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,

  layout: {
    padding: {
      left: 0,
      right: 80, // Prevents lines from hitting the right edge
      top: 20,
      bottom: 70
    }
  },

  plugins: {
    legend: { position: 'bottom' },
    tooltip: { mode: 'index', intersect: false },
    verticalLine: {}
  },
  scales: {
    x: {
      grid: { display: false }
    },
    y: {
      beginAtZero: true
    }
  }
};
</script>

<template>
  <div class="chart-container">
    <Line 
      v-if="timelineData.length" 
      :data="chartData" 
      :options="chartOptions"
      :plugins="[verticalLinePlugin]" 
    />
    <div v-else class="no-data">No timeline data available for this date</div>
  </div>
</template>

<style scoped>
.chart-container {
  height: 100%;
  width: 100%;
}
.no-data {
  text-align: center;
  padding: 50px;
  color: #888;
}
</style>