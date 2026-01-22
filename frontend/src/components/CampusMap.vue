<script setup>
import { ref, onMounted, watch, nextTick } from 'vue';
import "leaflet/dist/leaflet.css";
import { LMap, LTileLayer } from "@vue-leaflet/vue-leaflet";
import L from 'leaflet';

// Icons setup
import iconRetinaUrl from 'leaflet/dist/images/marker-icon-2x.png';
import iconUrl from 'leaflet/dist/images/marker-icon.png';
import shadowUrl from 'leaflet/dist/images/marker-shadow.png';
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({ iconRetinaUrl, iconUrl, shadowUrl });

const props = defineProps({
  geometry: Object,       // The shapes (Loaded Once)
  occupancyData: Array,   // The numbers (Loaded Often)
  flyTo: Object,
  globalMinRes: { type: Number, default: 0 },        // Fixed global min (2nd percentile) for Residential
  globalMaxRes: { type: Number, default: 100 },     // Fixed global max (98th percentile) for Residential
  globalMinNonRes: { type: Number, default: 0 },    // Fixed global min (2nd percentile) for Non-Residential
  globalMaxNonRes: { type: Number, default: 100 },  // Fixed global max (98th percentile) for Non-Residential
  selectedDate: String   // Current selected date for time series
});

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

const emit = defineEmits(['update-max']);

const zoom = ref(15);
const map = ref(null);
let geoJsonLayer = null;

let layersByCode = {}; // Use this for coloring (Guaranteed unique buildings)
let layersByName = {}; // Use this for search zooming

// Color stops for continuous interpolation (from light to dark)
const RES_COLORS = ['#FFEDF0', '#FFC9D4', '#FF9FAD', '#FF6384', '#DC143C', '#8B0000'];
const NON_RES_COLORS = ['#F1F7FF', '#D6E6FF', '#B0D0FF', '#7FB5FF', '#4292C6', '#08519C'];

// Helper: Convert hex to RGB
function hexToRgb(hex) {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return result ? {
    r: parseInt(result[1], 16),
    g: parseInt(result[2], 16),
    b: parseInt(result[3], 16)
  } : null;
}

// Helper: Convert RGB to hex
function rgbToHex(r, g, b) {
  return "#" + [r, g, b].map(x => {
    const hex = Math.round(x).toString(16);
    return hex.length === 1 ? "0" + hex : hex;
  }).join("");
}

// Helper: Linear interpolation between two colors
function interpolateColor(color1, color2, factor) {
  const rgb1 = hexToRgb(color1);
  const rgb2 = hexToRgb(color2);
  if (!rgb1 || !rgb2) return color1;
  
  return rgbToHex(
    rgb1.r + (rgb2.r - rgb1.r) * factor,
    rgb1.g + (rgb2.g - rgb1.g) * factor,
    rgb1.b + (rgb2.b - rgb1.b) * factor
  );
}

// Continuous color mapping function
function getColor(occupancy, category) {
  const cat = (category || 'Unknown').trim(); 
  const occ = occupancy || 0;
  
  // Use fixed global quantile-based min/max values from props (consistent across all time periods)
  const minVal = (cat === 'Residential') ? props.globalMinRes : props.globalMinNonRes;
  const maxVal = (cat === 'Residential') ? props.globalMaxRes : props.globalMaxNonRes;
  const range = maxVal - minVal;
  
  if (occ === 0) {
    // Zero occupancy always uses the lightest color
    if (cat === 'Residential') return RES_COLORS[0];
    if (cat === 'Non-Residential') return NON_RES_COLORS[0];
    return '#737373';
  }
  
  // Clamp occupancy to quantile range and calculate ratio (0 to 1)
  // Values below min map to 0, values above max map to 1
  const clampedOcc = Math.max(minVal, Math.min(occ, maxVal));
  const ratio = range > 0 ? (clampedOcc - minVal) / range : 0;
  
  // Select color palette
  const colors = (cat === 'Residential') ? RES_COLORS : 
                 (cat === 'Non-Residential') ? NON_RES_COLORS : 
                 ['#FAFAFA', '#E0E0E0', '#BDBDBD', '#9E9E9E', '#616161', '#212121'];
  
  // Map ratio to color stops (0.0 to 1.0 maps to indices 0 to colors.length-1)
  const scaledRatio = ratio * (colors.length - 1);
  const lowerIndex = Math.floor(scaledRatio);
  const upperIndex = Math.min(lowerIndex + 1, colors.length - 1);
  const localFactor = scaledRatio - lowerIndex;
  
  // Interpolate between the two nearest color stops
  return interpolateColor(colors[lowerIndex], colors[upperIndex], localFactor);
}

// 1. Initialize Map Geometry
function initMapLayer() {
  if (!map.value || !map.value.leafletObject || !props.geometry) return;
  const leafletMap = map.value.leafletObject;

  if (geoJsonLayer) leafletMap.removeLayer(geoJsonLayer);
  
  // Reset Lookups
  layersByCode = {};
  layersByName = {};

  geoJsonLayer = L.geoJSON(props.geometry, {
    style: { fillColor: '#737373', weight: 1, color: '#333', fillOpacity: 0.8 },
    onEachFeature: (feature, layer) => {
      // Key the lookup by CODE, not Name (more reliable)
      const code = feature.properties.BLDG_CODE;
      const name = feature.properties.BLDG_NAME;
      
      // Store static data on the layer for easy access later
      layer.feature.properties._staticCategory = feature.properties.building_category;
      
      // Initial Popup (will be updated with current occupancy in updateColors)
      const initialContent = `
        <div style="font-family: sans-serif; font-size: 14px;">
          <h4 style="margin:0 0 5px;">${name}</h4>
          <div>Occupancy: <strong>0</strong></div>
          <div>Type: ${feature.properties.building_category}</div>
          <div style="margin-top: 8px; font-size: 11px; color: #666;">Click to view time series</div>
        </div>
      `;
      layer.bindPopup(initialContent);

      // Add click handler to fetch and display time series
      layer.on('click', async () => {
        if (!props.selectedDate) return;
        
        // Get current count from the latest occupancy data
        const currentCount = countMap[code] || 0;
        
        // Show loading state
        layer.setPopupContent(`
          <div style="font-family: sans-serif; font-size: 14px;">
            <h4 style="margin:0 0 5px;">${name}</h4>
            <div>Loading time series...</div>
          </div>
        `);
        layer.openPopup();
        
        try {
          const response = await fetch(`${API_URL}/building-timeseries?date=${props.selectedDate}&code=${code}`);
          if (!response.ok) throw new Error('Failed to fetch');
          
          const timeseries = await response.json();
          
          // Create time series visualization
          const popupContent = createTimeSeriesPopup(name, currentCount, feature.properties.building_category, timeseries);
          layer.setPopupContent(popupContent);
        } catch (error) {
          console.error('Error fetching time series:', error);
          layer.setPopupContent(`
            <div style="font-family: sans-serif; font-size: 14px;">
              <h4 style="margin:0 0 5px;">${name}</h4>
              <div>Occupancy: <strong>${currentCount}</strong></div>
              <div>Type: ${feature.properties.building_category}</div>
              <div style="margin-top: 8px; color: #d32f2f; font-size: 12px;">Error loading time series</div>
            </div>
          `);
        }
      });

      // Populate separate lookups
      if (code) layersByCode[code] = layer;
      if (name) layersByName[name] = layer;
    }
  }).addTo(leafletMap);

  updateColors();
}

// Helper function to create time series popup HTML
function createTimeSeriesPopup(name, currentCount, category, timeseries) {
  if (!timeseries || timeseries.length === 0) {
    return `
      <div style="font-family: sans-serif; font-size: 14px;">
        <h4 style="margin:0 0 5px;">${name}</h4>
        <div>Current Occupancy: <strong>${currentCount}</strong></div>
        <div>Type: ${category}</div>
        <div style="margin-top: 8px; color: #666; font-size: 12px;">No time series data available</div>
      </div>
    `;
  }
  
  // Calculate stats
  const occupancies = timeseries.map(t => t.occupancy);
  const maxOcc = Math.max(...occupancies);
  const minOcc = Math.min(...occupancies);
  const avgOcc = Math.round(occupancies.reduce((a, b) => a + b, 0) / occupancies.length);
  const maxTime = timeseries.find(t => t.occupancy === maxOcc)?.time || 'N/A';
  
  // Create simple SVG line chart
  const width = 280;
  const height = 80;
  const padding = 10;
  const chartWidth = width - 2 * padding;
  const chartHeight = height - 2 * padding;
  
  const maxVal = Math.max(maxOcc, 1);
  const points = timeseries.map((t, i) => {
    const x = padding + (i / (timeseries.length - 1)) * chartWidth;
    const y = padding + chartHeight - (t.occupancy / maxVal) * chartHeight;
    return `${x},${y}`;
  }).join(' ');
  
  // Create path for line
  const pathData = timeseries.map((t, i) => {
    const x = padding + (i / (timeseries.length - 1)) * chartWidth;
    const y = padding + chartHeight - (t.occupancy / maxVal) * chartHeight;
    return i === 0 ? `M ${x} ${y}` : `L ${x} ${y}`;
  }).join(' ');
  
  return `
    <div style="font-family: sans-serif; font-size: 13px; max-width: 300px;">
      <h4 style="margin:0 0 8px; font-size: 15px;">${name}</h4>
      <div style="margin-bottom: 8px;">
        <div><strong>Current:</strong> ${currentCount} people</div>
        <div style="font-size: 11px; color: #666; margin-top: 4px;">
          Peak: ${maxOcc} @ ${maxTime} | Avg: ${avgOcc} | Min: ${minOcc}
        </div>
      </div>
      <div style="border-top: 1px solid #eee; padding-top: 8px;">
        <div style="font-size: 11px; color: #666; margin-bottom: 4px;">Occupancy Throughout Day:</div>
        <svg width="${width}" height="${height}" style="border: 1px solid #ddd; border-radius: 4px; background: #f9f9f9;">
          <polyline
            points="${points}"
            fill="none"
            stroke="#4292C6"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
          <text x="${padding}" y="${height - padding + 12}" font-size="9" fill="#666">0</text>
          <text x="${width - padding - 20}" y="${height - padding + 12}" font-size="9" fill="#666">${maxOcc}</text>
        </svg>
      </div>
      <div style="font-size: 11px; color: #666; margin-top: 6px;">Type: ${category}</div>
    </div>
  `;
}

// Store countMap at module level so click handler can access it
let countMap = {};

// 2. Update Colors (Runs Fast)
function updateColors() {
  const data = props.occupancyData || [];
  
  // Create a map of code -> count for O(1) lookup
  countMap = {};
  data.forEach(d => {
    countMap[d.code] = d.count;
  });

  // Use fixed global quantile-based min/max values (no dynamic recalculation)
  // This ensures color scale is consistent across all time periods
  const minRes = props.globalMinRes;
  const maxRes = props.globalMaxRes;
  const minNonRes = props.globalMinNonRes;
  const maxNonRes = props.globalMaxNonRes;
  
  emit('update-max', { 
    minRes: minRes, 
    maxRes: maxRes, 
    minNonRes: minNonRes, 
    maxNonRes: maxNonRes 
  });

  // Apply Colors
  for (const code in layersByCode) {
    const layer = layersByCode[code];
    const count = countMap[code] || 0; // Default to 0
    const cat = layer.feature.properties._staticCategory;
    const name = layer.feature.properties.BLDG_NAME;

    // Fast Style Update
    layer.setStyle({
      fillColor: getColor(count, cat)
    });

    // Update Popup Content (basic view, click to see time series)
    layer.setPopupContent(`
      <div style="font-family: sans-serif; font-size: 14px;">
        <h4 style="margin:0 0 5px;">${name}</h4>
        <div>Occupancy: <strong>${count}</strong></div>
        <div>Type: ${cat}</div>
        <div style="margin-top: 8px; font-size: 11px; color: #666;">Click to view time series</div>
      </div>
    `);
  }
}

// Watchers
watch(() => props.geometry, initMapLayer);
watch(() => props.occupancyData, updateColors, { deep: true });
watch(() => props.selectedDate, () => {
  // When date changes, close all popups to force refresh on next click
  if (geoJsonLayer) {
    Object.values(layersByCode).forEach(layer => {
      if (layer.isPopupOpen()) {
        layer.closePopup();
      }
    });
  }
});

watch(() => props.flyTo, (target) => {
  if (target && map.value) {
    const leafletMap = map.value.leafletObject;
    leafletMap.flyTo([target.lat, target.lon], 18, { animate: true, duration: 1.5 });
    
    // Check both lookups to be safe
    const targetLayer = layersByName[target.name] || layersByCode[target.code];
    if (targetLayer) setTimeout(() => targetLayer.openPopup(), 500);
  }
});

onMounted(() => {
  nextTick(() => { if(props.geometry) initMapLayer(); });
});
</script>

<template>
  <div class="map-wrapper">
    <l-map ref="map" :zoom="zoom" :center="[33.7756, -84.3963]">
      <l-tile-layer
        url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
        layer-type="base"
        name="CartoDB Positron"
      ></l-tile-layer>
    </l-map>
  </div>
</template>

<style scoped>
.map-wrapper { height: 100%; width: 100%; border-radius: 8px; border: 1px solid #ddd; z-index: 1; }
</style>