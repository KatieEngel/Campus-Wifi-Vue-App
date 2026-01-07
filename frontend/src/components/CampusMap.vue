<script setup>
import { ref, onMounted, watch, nextTick } from 'vue';
import "leaflet/dist/leaflet.css";
import { LMap, LTileLayer } from "@vue-leaflet/vue-leaflet";
import L from 'leaflet';

// --- LEAFLET ICON FIX ---
import iconRetinaUrl from 'leaflet/dist/images/marker-icon-2x.png';
import iconUrl from 'leaflet/dist/images/marker-icon.png';
import shadowUrl from 'leaflet/dist/images/marker-shadow.png';
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl,
  iconUrl,
  shadowUrl,
});

const props = defineProps({
  geoJsonData: Object,
  renderKey: String
});

const zoom = ref(15);
const map = ref(null);
let geoJsonLayer = null;

// COLOR LOGIC
const RES_COLORS = ['#FFEDF0', '#FFC9D4', '#FF9FAD', '#FF6384', '#DC143C', '#8B0000'];
const NON_RES_COLORS = ['#F1F7FF', '#D6E6FF', '#B0D0FF', '#7FB5FF', '#4292C6', '#08519C'];

function getColor(occupancy, category) {
  const cat = (category || 'Unknown').trim(); 
  const occ = occupancy || 0;

  // 2. Determine Intensity Index (0 to 5)
  let index = 0;
  if (occ > 50) index = 5;       // High Occupancy -> Darkest
  else if (occ > 30) index = 4;
  else if (occ > 15) index = 3;
  else if (occ > 5) index = 2;
  else if (occ > 0) index = 1;   // Low Occupancy -> Light
  
  // Pick the Color Palette
  if (cat === 'Residential') return RES_COLORS[index];
  if (cat === 'Non-Residential') return NON_RES_COLORS[index];
  // If you see Gray, it means the category string didn't match Residential/Non-Residential
  return '#737373'; // Unknown
}

function updateLayer() {
  // 1. Safety Check: Map and Data must exist
  if (!map.value || !map.value.leafletObject || !props.geoJsonData) return;

  const leafletMap = map.value.leafletObject;

  // 2. Remove Old Layer (Clean slate)
  if (geoJsonLayer) {
    leafletMap.removeLayer(geoJsonLayer);
  }

  // 3. Create New Layer MANUALLY
  // This bypasses the Vue wrapper issues completely
  geoJsonLayer = L.geoJSON(props.geoJsonData, {
    style: (feature) => {
      const occ = feature?.properties?.occupancy || 0;
      const cat = feature?.properties?.building_category;
      
      // DEBUG: This should absolutely print now
      console.log(`MANUAL STYLE: ${feature?.properties?.BLDG_NAME} -> ${occ}`);

      return {
        fillColor: getColor(occ, cat),
        weight: 1,
        color: '#333',
        opacity: 1,
        fillOpacity: 0.8
      };
    },
    onEachFeature: (feature, layer) => {
      layer.bindTooltip(`
        <strong>${feature.properties.BLDG_NAME}</strong><br>
        Occupancy: ${feature.properties.occupancy}<br>
        Type: ${feature.properties.building_category}
      `);
    }
  }).addTo(leafletMap);
}

// Watch for changes in the key (Time/Date) and re-draw
watch(() => props.renderKey, () => {
  updateLayer();
});

// Watch for initial map load
watch(() => map.value, (newVal) => {
  if (newVal) updateLayer();
});

// Watch for initial data load
watch(() => props.geoJsonData, (newVal) => {
  if (newVal) updateLayer();
});

onMounted(() => {
  // Try to render immediately if data is ready
  nextTick(() => {
    updateLayer();
  });
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
.map-wrapper {
  height: 600px;
  width: 100%;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #ddd;
  z-index: 1;
}
</style>