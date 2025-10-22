import streamlit as st
import streamlit.components.v1 as components
# --- MODIFIED IMPORT ---
# We now also import the new geocoding functions
from data_processing import (
    load_data, 
    clean_data, 
    year_slider, 
    create_map, 
    geocode_address, 
    reverse_geocode_coords
)
# --- END MODIFICATION ---
import os

#-------------------------------
#---------Custom Styling--------
#-------------------------------
st.markdown("""
    <style>
    html, body {
        background-color: #F1EBDE !important;
        color: black !important;
    }
    [data-testid="stAppViewContainer"], [data-testid="stAppViewBlockContainer"] {
        background-color: #F1EBDE !important;
    }
    header[data-testid="stHeader"] {
        background-color: #F1EBDE !important;
    }
    .st-emotion-cache-1avcm0n {
        background-color: #F1EBDE !important;
    }
    </style>
""", unsafe_allow_html=True)

#-------------------------------
#--------- Main Page -----------
#-------------------------------

st.markdown("""
    <h1 style='
        color: black;
        font-size: 3em;
        font-weight: bold;
    '>Robberies near or in metro stations in Mexico City</h1>
""", unsafe_allow_html=True)

st.markdown("""
    <p style='color:black; font-size:1.1em;'>
        This map shows the amount of robberies registered in a single year. To change the year
        selected you can use the slider below.
    </p>
""", unsafe_allow_html=True)

#-------------------------------
#-------- Load & Clean ---------
#-------------------------------
# This is cached, so it only runs once
df_raw, _, _ = load_data()

if df_raw is not None:
    df_clean = clean_data(df_raw)

    #-------------------------------
    #-------- Year Slider ----------
    #-------------------------------
    selected_year = year_slider(df_clean)

    #-------------------------------
    #-------- Map Creation ---------
    #-------------------------------
    st.markdown(f"""
        <h3 style='color:black;'>Year selected: {selected_year}</h3>
    """, unsafe_allow_html=True)
    
    # Note: create_map() now returns HTML, which can't be made interactive.
    # See "Next Steps" in my chat response for how to improve this.
    create_map(selected_year)

else:
    st.error("Failed to load crime data. Please check file paths and try again.")
    st.stop() # Stop the app if data fails to load

st.divider()

# --- NEW SECTION: Geocoding Tools ---

st.markdown("""
    <h2 style='color: black; font-weight: bold;'>Geocoding Tools</h2>
""", unsafe_allow_html=True)

# --- 1. Geocoding (Address -> Coords) ---
st.markdown("<h3 style='color: black;'>Find Coordinates from Address</h3>", unsafe_allow_html=True)
st.markdown("Enter an address in Mexico City to find its latitude and longitude. (e.g., *Palacio de Bellas Artes, Mexico City*)")

address_input = st.text_input("Enter Address:")
if st.button("Find Coordinates"):
    if address_input:
        with st.spinner(f"Geocoding '{address_input}'... (This takes a moment due to rate limits)"):
            lat, lon = geocode_address(address_input)
            if lat and lon:
                st.success(f"Coordinates Found: `{lat}, {lon}`")
                
                # Create a simple map centered on the new location
                m = folium.Map(location=[lat, lon], zoom_start=15)
                folium.Marker([lat, lon], popup=address_input).add_to(m)
                components.html(m._repr_html_(), height=300)
                
            else:
                st.error("Address not found or geocoding failed.")
    else:
        st.warning("Please enter an address.")


# --- 2. Reverse Geocoding (Coords -> Address) ---
st.markdown("<h3 style='color: black;'>Find Address from Coordinates</h3>", unsafe_allow_html=True)
st.markdown("Enter coordinates to find the nearest address. (e.g., Lat: `19.4352`, Lon: `-99.1412`)")

col1, col2 = st.columns(2)
with col1:
    lat_input = st.number_input("Latitude:", format="%.6f", value=19.435200)
with col2:
    lon_input = st.number_input("Longitude:", format="%.6f", value=-99.141200)

if st.button("Find Address"):
    with st.spinner(f"Finding address for `({lat_input}, {lon_input})`..."):
        address_output = reverse_geocode_coords(lat_input, lon_input)
        if address_output:
            st.success(f"Address Found: {address_output}")
        else:
            st.error("Could not find an address for those coordinates.")