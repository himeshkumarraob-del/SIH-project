"""
GIS Map Builder Module for Thermal Anomaly Detections.

Constructs an interactive Folium map visualization of FIRMS detections and clusters
across India with abnormality level stratification, marker clustering, boundary layers,
and rich popup metadata.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union
import json
import pandas as pd
import folium
from folium.plugins import Fullscreen, MarkerCluster, FeatureGroupSubGroup

from src.logging_setup import get_logger

logger = get_logger("gis.map_builder")

# Standard required columns for mapping thermal events
REQUIRED_COLUMNS = [
    "latitude",
    "longitude",
    "cluster_id",
    "abnormality_level",
    "anomaly_score",
    "persistence_category",
    "anomaly_characterization",
    "explanation",
    "acq_date",
    "frp",
    "bright_ti4",
    "satellite",
]

COLOR_MAP = {
    "HIGH": "#d9534f",       # Red
    "ELEVATED": "#f0ad4e",   # Orange
    "NORMAL": "#5cb85c",     # Green
}

MARKER_COLOR_MAP = {
    "HIGH": "red",
    "ELEVATED": "orange",
    "NORMAL": "green",
}

def build_india_map(
    events_df: pd.DataFrame,
    output_path: Union[str, Path],
    geojson_path: Optional[Union[str, Path]] = None,
) -> Path:
    """
    Build an interactive Folium HTML map of thermal events across India.

    Parameters
    ----------
    events_df : pd.DataFrame
        DataFrame containing detection & anomaly details.
    output_path : Union[str, Path]
        Path where the generated HTML file will be saved.
    geojson_path : Optional[Union[str, Path]]
        Path to India boundary GeoJSON. If None, defaults to data/external/india_boundary.geojson.

    Returns
    -------
    Path
        Path object pointing to the created HTML file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Validate required columns
    missing = [col for col in REQUIRED_COLUMNS if col not in events_df.columns]
    if missing:
        raise ValueError(f"Missing required columns for map building: {missing}")

    # 2. Filter valid coordinates
    clean_df = events_df.copy()
    clean_df = clean_df.dropna(subset=["latitude", "longitude"])
    clean_df = clean_df[
        (clean_df["latitude"] >= -90) & (clean_df["latitude"] <= 90) &
        (clean_df["longitude"] >= -180) & (clean_df["longitude"] <= 180)
    ]

    if clean_df.empty:
        logger.warning("No valid coordinate records to render on map.")

    # 3. Initialize Base Map centered over India
    india_center = [20.5937, 78.9629]
    m = folium.Map(
        location=india_center,
        zoom_start=5,
        tiles="OpenStreetMap",
        control_scale=True,
        scrollWheelZoom=True,
        dragging=True,
    )

    # Add Fullscreen Control
    Fullscreen(position="topright").add_to(m)

    # 4. Add India Boundary GeoJSON Layer if present
    if geojson_path is None:
        geojson_path = Path("data/external/india_boundary.geojson")
    else:
        geojson_path = Path(geojson_path)

    if geojson_path.exists():
        try:
            with open(geojson_path, "r", encoding="utf-8") as f:
                boundary_data = json.load(f)
            
            folium.GeoJson(
                boundary_data,
                name="India Boundary",
                style_function=lambda x: {
                    "fillColor": "#00000000",
                    "color": "#2c3e50",
                    "weight": 2,
                    "dashArray": "3, 3",
                },
            ).add_to(m)
            logger.info("Loaded India boundary GeoJSON onto map.")
        except Exception as exc:
            logger.warning(f"Failed to load GeoJSON from {geojson_path}: {exc}")

    # 5. Marker Cluster Parent Layer
    mc_parent = MarkerCluster(name="All Detections Cluster", show=True).add_to(m)

    # Subgroups for Abnormality Levels to allow filtering via LayerControl
    fg_high = FeatureGroupSubGroup(mc_parent, name="HIGH Anomalies (Red)")
    fg_elevated = FeatureGroupSubGroup(mc_parent, name="ELEVATED Anomalies (Orange)")
    fg_normal = FeatureGroupSubGroup(mc_parent, name="NORMAL Events (Green)")

    m.add_child(fg_high)
    m.add_child(fg_elevated)
    m.add_child(fg_normal)

    # 6. Add Markers to Subgroups
    for _, row in clean_df.iterrows():
        level = str(row.get("abnormality_level", "NORMAL")).upper()
        marker_color = MARKER_COLOR_MAP.get(level, "blue")

        # HTML Popup Content
        popup_html = f"""
        <div style="font-family: Arial, sans-serif; font-size: 12px; min-width: 200px;">
            <h4 style="margin: 0 0 5px 0; color: {COLOR_MAP.get(level, '#333')};">
                Cluster ID: {row['cluster_id']} ({level})
            </h4>
            <hr style="margin: 5px 0; border: 0; border-top: 1px solid #ccc;"/>
            <b>Score:</b> {row['anomaly_score']}<br/>
            <b>Persistence:</b> {row['persistence_category']}<br/>
            <b>Characterization:</b> {row['anomaly_characterization']}<br/>
            <b>Explanation:</b> {row['explanation']}<br/>
            <b>Date:</b> {row['acq_date']}<br/>
            <b>FRP:</b> {row['frp']} MW<br/>
            <b>TI4 Temp:</b> {row['bright_ti4']} K<br/>
            <b>Satellite:</b> {row['satellite']}<br/>
        </div>
        """

        marker = folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=6 if level == "HIGH" else (5 if level == "ELEVATED" else 4),
            popup=folium.Popup(popup_html, max_width=300),
            color=COLOR_MAP.get(level, "#333"),
            fill=True,
            fill_color=COLOR_MAP.get(level, "#333"),
            fill_opacity=0.8,
        )

        if level == "HIGH":
            marker.add_to(fg_high)
        elif level == "ELEVATED":
            marker.add_to(fg_elevated)
        else:
            marker.add_to(fg_normal)

    # 7. Add Layer Control
    folium.LayerControl(collapsed=False).add_to(m)

    # 8. Floating Legend
    legend_html = """
    <div style="
        position: fixed; 
        bottom: 30px; left: 30px; width: 190px; height: 135px; 
        border:2px solid grey; z-index:9999; font-size:12px;
        background-color:white; opacity: 0.9; padding: 10px;
        border-radius: 5px; font-family: sans-serif;
    ">
    <b>Thermal Abnormality</b><br>
    <i style="background:#d9534f; width:12px; height:12px; float:left; margin-right:8px; border-radius:50%;"></i> HIGH Anomaly<br>
    <i style="background:#f0ad4e; width:12px; height:12px; float:left; margin-right:8px; border-radius:50%;"></i> ELEVATED Event<br>
    <i style="background:#5cb85c; width:12px; height:12px; float:left; margin-right:8px; border-radius:50%;"></i> NORMAL Event<br>
    <hr style="margin:5px 0;">
    <small>Total Events: {}</small>
    </div>
    """.format(len(clean_df))

    m.get_root().html.add_child(folium.Element(legend_html))

    # 9. Save Map
    m.save(str(output_path))
    logger.info(f"Saved interactive GIS map to {output_path}")

    return output_path
