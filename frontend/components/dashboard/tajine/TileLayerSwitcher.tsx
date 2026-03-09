'use client';

import { useEffect, useRef } from 'react';
import { useMap } from 'react-leaflet';
import L from 'leaflet';

export type MapMode = 'standard' | 'satellite' | 'terrain';

// Tile layer configurations
const TILE_CONFIGS: Record<MapMode, { url: string; attribution: string; subdomains?: string }> = {
  standard: {
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; OpenStreetMap contributors',
    subdomains: 'abc',
  },
  satellite: {
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: '&copy; Esri, Maxar, Earthstar Geographics',
  },
  terrain: {
    url: 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
    attribution: '&copy; OpenTopoMap contributors, &copy; OpenStreetMap',
    subdomains: 'abc',
  },
};

interface TileLayerSwitcherProps {
  mode: MapMode;
}

export function TileLayerSwitcher({ mode }: TileLayerSwitcherProps) {
  const map = useMap();
  const layerRef = useRef<L.TileLayer | null>(null);

  useEffect(() => {
    // Remove existing tile layer
    if (layerRef.current) {
      map.removeLayer(layerRef.current);
      layerRef.current = null;
    }

    // Add new tile layer based on mode
    const config = TILE_CONFIGS[mode];
    const options: L.TileLayerOptions = {
      attribution: config.attribution,
    };

    if (config.subdomains) {
      options.subdomains = config.subdomains;
    }

    const newLayer = L.tileLayer(config.url, options);
    newLayer.addTo(map);
    layerRef.current = newLayer;

    // Cleanup on unmount
    return () => {
      if (layerRef.current) {
        map.removeLayer(layerRef.current);
        layerRef.current = null;
      }
    };
  }, [mode, map]);

  return null;
}

export default TileLayerSwitcher;
