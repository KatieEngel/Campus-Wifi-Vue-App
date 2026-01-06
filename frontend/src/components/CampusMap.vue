<script setup>
import { computed } from 'vue';
import "leaflet/dist/leaflet.css";
import { LMap, LTileLayer, LGeoJson } from "@vue-leaflet/vue-leaflet";

const props = defineProps({
  geoJsonData: Object,
});

// --- COLOR LOGIC (Replicating Streamlit Logic) ---
const RES_COLORS = ['#FFEDF0', '#FFC9D4', '#FF9FAD', '#FF6384', '#DC143C', '#8B0000'];
const NON_RES_COLORS = ['#F1F7FF', '#D6E6FF', '#B0D0FF', '#7FB5FF', '#4292C6', '#08519C'];

function getColor(occupancy, category) {
  // Simple bucketing logic to match your Python "6 steps"
  // You can make this more math-heavy if needed
  let index = 0;
  if (occupancy > 50) index = 5;
  else if (occupancy > 30) index = 4;
  else if (occupancy > 15) index = 3;
  else if (occupancy > 5) index = 2;
  else if (occupancy > 0) index = 1;
  
  if (category === 'Residential') return RES_COLORS[index];
  if (category === 'Non-Residential') return NON_RES_COLORS[index];
  return '#737373'; // Unknown
}

const geoJsonOptions = computed(() => {
  return {
    style: (feature) => {
      const occ = feature.properties.occupancy;
      const cat = feature.properties.building_category;
      return {
        fillColor: getColor(occ, cat),
        weight: 1,
        color: 'black',
        fillOpacity: 0.7
      };
    },
    onEachFeature: (feature, layer) => {
      // Tooltip on hover
      layer.bindTooltip(`
        <b>${feature.properties.BLDG_NAME}</b><br>
        Occupancy: ${feature.properties.occupancy}<br>
        Type: ${feature.properties.building_category}
      `);
    }
  };
});
</script>

<template>
  <div class="map-wrapper">
    <l-map ref="map" v-model:zoom="zoom" :center="[33.7756, -84.3963]" :zoom="15">
      <l-tile-layer
        url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
        layer-type="base"
        name="CartoDB Positron"
      ></l-tile-layer>

      <l-geo-json 
        v-if="geoJsonData" 
        :geojson="geoJsonData" 
        :options="geoJsonOptions"
      />
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
}
</style>