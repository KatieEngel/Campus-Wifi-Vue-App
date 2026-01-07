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
  selectedTime: String // e.g. "12:00" for the vertical line
});

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
      tension: 0.3 // Smooth curves
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
  plugins: {
    legend: { position: 'bottom' },
    tooltip: { mode: 'index', intersect: false }
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
    <Line v-if="timelineData.length" :data="chartData" :options="chartOptions" />
    <div v-else class="no-data">No timeline data available for this date</div>
  </div>
</template>

<style scoped>
.chart-container {
  height: 400px;
  width: 100%;
}
.no-data {
  text-align: center;
  padding: 50px;
  color: #888;
}
</style>