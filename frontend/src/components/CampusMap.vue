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

const emit = defineEmits(['update-max']);

const props = defineProps({
  geoJsonData: Object,
  renderKey: String,
  flyTo: Object
});

const zoom = ref(15);
const map = ref(null);
let geoJsonLayer = null;

// --- THE MISSING LINE IS HERE ---
let layerLookup = {}; 
// --------------------------------

// COLOR LOGIC
const RES_COLORS = ['#FFEDF0', '#FFC9D4', '#FF9FAD', '#FF6384', '#DC143C', '#8B0000'];
const NON_RES_COLORS = ['#F1F7FF', '#D6E6FF', '#B0D0FF', '#7FB5FF', '#4292C6', '#08519C'];

// Variables to store current max for the legend/scaling
let maxRes = 100;
let maxNonRes = 100;

function getColor(occupancy, category) {
  const cat = (category || 'Unknown').trim(); 
  const occ = occupancy || 0;
  
  // Determine which max value to use for scaling
  const maxVal = (cat === 'Residential') ? maxRes : maxNonRes;
  
  // Create 5 buckets based on the max value (Dynamic Scaling)
  // Step 0: 0
  // Step 1: 0 to 20% of max
  // Step 2: 20% to 40% ... etc
  let index = 0;
  if (occ === 0) index = 0; // Distinct color for empty
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

function updateLayer() {
  if (!map.value || !map.value.leafletObject || !props.geoJsonData) return;
  const leafletMap = map.value.leafletObject;

  // Remove Old Layer
  if (geoJsonLayer) {
    leafletMap.removeLayer(geoJsonLayer);
  }
  
  // Reset the lookup table for the new layer
  layerLookup = {}; 

  // --- ALCULATE MAX VALUES FOR THIS TIMESTAMP ---
  // We reset them to a minimum of 10 to avoid divide-by-zero on empty days
  maxRes = 10;
  maxNonRes = 10;

  props.geoJsonData.features.forEach(f => {
    const occ = f.properties.occupancy || 0;
    const cat = (f.properties.building_category || 'Unknown').trim();
    
    if (cat === 'Residential') {
      if (occ > maxRes) maxRes = occ;
    } else if (cat === 'Non-Residential') {
      if (occ > maxNonRes) maxNonRes = occ;
    }
  });
  
  emit('update-max', { res: maxRes, nonRes: maxNonRes });

  // Create New Layer MANUALLY
  geoJsonLayer = L.geoJSON(props.geoJsonData, {
    style: (feature) => {
      const occ = feature?.properties?.occupancy || 0;
      const cat = feature?.properties?.building_category;
      
      return {
        fillColor: getColor(occ, cat),
        weight: 1,
        color: '#333',
        opacity: 1,
        fillOpacity: 0.8
      };
    },
    onEachFeature: (feature, layer) => {
      const name = feature.properties.BLDG_NAME;
      
      const popupContent = `
        <div style="font-family: sans-serif; font-size: 14px; min-width: 150px;">
          <h4 style="margin: 0 0 8px 0; color: #333;">${name}</h4>
          <div style="margin-bottom: 4px;">
            <strong>Occupancy:</strong> ${feature.properties.occupancy}
          </div>
          <div>
            <strong>Type:</strong> ${feature.properties.building_category}
          </div>
        </div>
      `;

      layer.bindPopup(popupContent);
      
      // Save this layer to our lookup table
      if (name) {
        layerLookup[name] = layer;
      }
    }
  }).addTo(leafletMap);
}

// Watchers
watch(() => props.renderKey, () => {
  updateLayer();
});

watch(() => map.value, (newVal) => {
  if (newVal) updateLayer();
});

watch(() => props.geoJsonData, (newVal) => {
  if (newVal) updateLayer();
});

watch(() => props.flyTo, (target) => {
  if (target && map.value) {
    const leafletMap = map.value.leafletObject; 
    
    // 1. Fly
    leafletMap.flyTo([target.lat, target.lon], 18, {
      animate: true,
      duration: 1.5 
    });
    
    // 2. Open Popup using the lookup table
    const targetLayer = layerLookup[target.name];
    
    if (targetLayer) {
      setTimeout(() => {
        targetLayer.openPopup();
      }, 500); 
    }
  }
});

onMounted(() => {
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
  height: 100%;
  width: 100%;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #ddd;
  z-index: 1;
}
</style>