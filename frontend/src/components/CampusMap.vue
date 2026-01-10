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
  flyTo: Object
});

const emit = defineEmits(['update-max']);

const zoom = ref(15);
const map = ref(null);
let geoJsonLayer = null;

let layersByCode = {}; // Use this for coloring (Guaranteed unique buildings)
let layersByName = {}; // Use this for search zooming

// Colors
const RES_COLORS = ['#FFEDF0', '#FFC9D4', '#FF9FAD', '#FF6384', '#DC143C', '#8B0000'];
const NON_RES_COLORS = ['#F1F7FF', '#D6E6FF', '#B0D0FF', '#7FB5FF', '#4292C6', '#08519C'];

let maxRes = 100;
let maxNonRes = 100;

function getColor(occupancy, category) {
  const cat = (category || 'Unknown').trim(); 
  const occ = occupancy || 0;
  
  const maxVal = (cat === 'Residential') ? maxRes : maxNonRes;
  
  let index = 0;
  if (occ === 0) index = 0;
  else {
    const ratio = occ / maxVal;
    if (ratio > 0.8) index = 5;
    else if (ratio > 0.6) index = 4;
    else if (ratio > 0.4) index = 3;
    else if (ratio > 0.2) index = 2;
    else index = 1;
  }

  if (cat === 'Residential') return RES_COLORS[index];
  if (cat === 'Non-Residential') return NON_RES_COLORS[index];
  return '#737373'; 
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
      
      // Initial Popup
      const initialContent = `
        <div style="font-family: sans-serif; font-size: 14px;">
          <h4 style="margin:0 0 5px;">${name}</h4>
          <div>Occupancy: <strong>0</strong></div>
          <div>Type: ${feature.properties.building_category}</div>
        </div>
      `;
      layer.bindPopup(initialContent);

      // Populate separate lookups
      if (code) layersByCode[code] = layer;
      if (name) layersByName[name] = layer;
    }
  }).addTo(leafletMap);

  updateColors();
}

// 2. Update Colors (Runs Fast)
function updateColors() {
  const data = props.occupancyData || [];

  // A. Reset Max calculations
  maxRes = 10; 
  maxNonRes = 10;
  
  // Create a map of code -> count for O(1) lookup
  const countMap = {};
  data.forEach(d => {
    countMap[d.code] = d.count;
  });

  // Calculate Max first
  // Calculate Max first (Iterate ONLY the codes)
  for (const code in layersByCode) {
    const layer = layersByCode[code];
    const cat = layer.feature.properties._staticCategory;
    const count = countMap[code] || 0; // Default to 0 if missing

    if (cat === 'Residential' && count > maxRes) maxRes = count;
    if (cat === 'Non-Residential' && count > maxNonRes) maxNonRes = count;
  }
  
  emit('update-max', { res: maxRes, nonRes: maxNonRes });

  // B. Apply Colors
  for (const code in layersByCode) {
    const layer = layersByCode[code];
    const count = countMap[code] || 0; // Default to 0
    const cat = layer.feature.properties._staticCategory;
    const name = layer.feature.properties.BLDG_NAME;

    // Fast Style Update
    layer.setStyle({
      fillColor: getColor(count, cat)
    });

    // Update Popup Content
    layer.setPopupContent(`
      <div style="font-family: sans-serif; font-size: 14px;">
        <h4 style="margin:0 0 5px;">${name}</h4>
        <div>Occupancy: <strong>${count}</strong></div>
        <div>Type: ${cat}</div>
      </div>
    `);
  }
}

// Watchers
watch(() => props.geometry, initMapLayer);
watch(() => props.occupancyData, updateColors, { deep: true });

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