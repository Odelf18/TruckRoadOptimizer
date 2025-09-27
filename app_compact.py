import os
import streamlit as st
import googlemaps
import folium
from streamlit_folium import st_folium
from ortools.constraint_solver import pywrapcp, routing_enums_pb2
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")

# Check if API key is present
if not API_KEY:
    st.error("❌ Google Maps API key missing in .env file")
    st.stop()

# Initialize Google Maps client
try:
    gmaps = googlemaps.Client(key=API_KEY)
except Exception as e:
    st.error(f"❌ Error initializing Google Maps: {e}")
    st.stop()

st.set_page_config(page_title="Route Optimizer", layout="wide")

st.title("🚚 Tire Pickup Route Optimizer")
st.markdown("**Real-time route optimization with Google Maps**")

# Initialize session state
if 'optimization_done' not in st.session_state:
    st.session_state.optimization_done = False
if 'results' not in st.session_state:
    st.session_state.results = None

# Function to get address suggestions
def get_address_suggestions(query):
    """Get address suggestions via Google Places API"""
    if len(query) < 3:
        return []
    
    try:
        places_result = gmaps.places_autocomplete(
            input_text=query,
            types='address',
            language='en',
            region='us'
        )
        
        suggestions = []
        for place in places_result[:5]:
            suggestions.append(place['description'])
        
        return suggestions
        
    except Exception as e:
        st.error(f"Error fetching suggestions: {e}")
        return []

# Compact interface
col1, col2 = st.columns([3, 1])

with col1:
    depot_address = st.text_input("**Depot Address**", "Houston, TX")

with col2:
    n = st.number_input("**Number of Stops**", 1, 10, 3)

# Compact stops input
st.subheader("📍 Pickup Stops")
stops = []

# Create a more compact layout
for i in range(n):
    col1, col2, col3 = st.columns([4, 1, 1])
    
    with col1:
        addr_key = f"addr_{i}"
        addr = st.text_input(f"Stop {i+1} Address", key=addr_key, placeholder="Type 3+ characters...")
        
        # Show suggestions
        if addr and len(addr) >= 3:
            suggestions = get_address_suggestions(addr)
            if suggestions:
                selected = st.selectbox(
                    "Select address:",
                    options=[""] + suggestions,
                    key=f"select_{i}",
                    help="Choose from suggestions"
                )
                if selected:
                    st.session_state[addr_key] = selected
                    st.rerun()
    
    with col2:
        qty = st.number_input(f"Tires", 0, 500, 50, key=f"qty_{i}")
    
    with col3:
        st.write("")  # Empty space for alignment
    
    if addr:
        stops.append({"address": addr, "qty": qty})

# Action buttons
col1, col2, col3 = st.columns([1, 1, 4])
with col1:
    optimize_clicked = st.button("🚀 Optimize Routes", type="primary", use_container_width=True)
with col2:
    reset_clicked = st.button("🔄 Reset", use_container_width=True)

# Optimization logic
if optimize_clicked and stops:
    st.session_state.optimization_done = True
    
    try:
        # Geocoding
        with st.spinner("🗺️ Geocoding addresses..."):
            depot_geocode = gmaps.geocode(depot_address)
            if not depot_geocode:
                st.error(f"❌ Depot address not found: {depot_address}")
                st.stop()
            
            depot_latlon = (
                depot_geocode[0]["geometry"]["location"]["lat"],
                depot_geocode[0]["geometry"]["location"]["lng"]
            )
            
            coords = [depot_latlon]
            for i, s in enumerate(stops):
                geocode_result = gmaps.geocode(s["address"])
                if not geocode_result:
                    st.error(f"❌ Address not found: {s['address']}")
                    st.stop()
                
                lat = geocode_result[0]["geometry"]["location"]["lat"]
                lng = geocode_result[0]["geometry"]["location"]["lng"]
                s["latlon"] = (lat, lng)
                coords.append(s["latlon"])
                time.sleep(0.1)

        # Distance matrix
        with st.spinner("📊 Calculating distance matrix..."):
            matrix_result = gmaps.distance_matrix(
                origins=coords,
                destinations=coords,
                mode="driving",
                units="metric",
                region="us"
            )
            
            n_points = len(coords)
            dist_matrix = []
            for i, row in enumerate(matrix_result["rows"]):
                dist_row = []
                for j, element in enumerate(row["elements"]):
                    if element["status"] == "OK":
                        duration_minutes = element["duration"]["value"] // 60
                        dist_row.append(duration_minutes)
                    else:
                        dist_row.append(9999)
                dist_matrix.append(dist_row)

        # OR-Tools optimization
        with st.spinner("🧮 Optimizing routes..."):
            manager = pywrapcp.RoutingIndexManager(n_points, 1, 0)
            routing = pywrapcp.RoutingModel(manager)

            def distance_callback(from_index, to_index):
                return dist_matrix[manager.IndexToNode(from_index)][manager.IndexToNode(to_index)]

            transit_cb = routing.RegisterTransitCallback(distance_callback)
            routing.SetArcCostEvaluatorOfAllVehicles(transit_cb)

            search_params = pywrapcp.DefaultRoutingSearchParameters()
            search_params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
            search_params.time_limit.FromSeconds(10)

            solution = routing.SolveWithParameters(search_params)

        if solution:
            # Get optimized route
            index = routing.Start(0)
            plan = []
            while not routing.IsEnd(index):
                node = manager.IndexToNode(index)
                plan.append(node)
                index = solution.Value(routing.NextVar(index))
            plan.append(manager.IndexToNode(index))

            # Get detailed routes
            with st.spinner("🛣️ Calculating detailed routes..."):
                route_coords = []
                
                for i in range(len(plan) - 1):
                    start_coord = coords[plan[i]]
                    end_coord = coords[plan[i + 1]]
                    
                    directions_result = gmaps.directions(
                        origin=start_coord,
                        destination=end_coord,
                        mode="driving",
                        avoid=["tolls", "ferries"]
                    )
                    
                    if directions_result:
                        import polyline as pl
                        polyline = directions_result[0]["overview_polyline"]["points"]
                        decoded_coords = pl.decode(polyline)
                        route_coords.extend(decoded_coords)
                        time.sleep(0.1)

            # Save results
            st.session_state.results = {
                'plan': plan,
                'stops': stops,
                'depot_address': depot_address,
                'depot_latlon': depot_latlon,
                'dist_matrix': dist_matrix,
                'coords': coords,
                'route_coords': route_coords
            }
            
            st.success("✅ Route optimized successfully!")
        else:
            st.error("❌ No solution found")

    except Exception as e:
        st.error(f"❌ Optimization error: {e}")

# Reset
if reset_clicked:
    st.session_state.optimization_done = False
    st.session_state.results = None
    st.rerun()

# Display results
if st.session_state.results and st.session_state.optimization_done:
    results = st.session_state.results
    plan = results['plan']
    stops = results['stops']
    depot_address = results['depot_address']
    depot_latlon = results['depot_latlon']
    dist_matrix = results['dist_matrix']
    coords = results['coords']
    route_coords = results.get('route_coords', [])

    # Results in compact format
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📋 Optimized Route")
        total_time = 0
        total_tires = 0
        
        for i, idx in enumerate(plan):
            if idx == 0:
                st.write(f"🏢 **Depot:** {depot_address}")
            else:
                s = stops[idx-1]
                st.write(f"📍 **Stop {i}:** {s['address']} ({s['qty']} tires)")
                total_tires += s['qty']
                if i > 0:
                    prev_idx = plan[i-1]
                    time_min = dist_matrix[prev_idx][idx]
                    total_time += time_min
                    st.write(f"   ⏱️ Travel time: {time_min} minutes")
    
    with col2:
        st.metric("Total Travel Time", f"{total_time} min")
        st.metric("Total Tires", f"{total_tires}")
        st.metric("Number of Stops", len(stops))

    # Interactive map
    st.subheader("🗺️ Route Map")
    
    m = folium.Map(location=depot_latlon, zoom_start=12, tiles='OpenStreetMap')
    
    # Depot marker
    folium.Marker(
        depot_latlon, 
        icon=folium.Icon(color="red", icon="warehouse", prefix="fa"), 
        popup="🏢 Depot"
    ).add_to(m)
    
    # Stop markers
    for i, idx in enumerate(plan):
        if idx != 0:
            s = stops[idx-1]
            folium.Marker(
                s["latlon"],
                popup=f"📍 Stop {i}<br>{s['address']}<br>📦 {s['qty']} tires",
                icon=folium.Icon(color="blue", icon="truck", prefix="fa")
            ).add_to(m)
    
    # Route line
    if route_coords:
        folium.PolyLine(
            route_coords, 
            color="red", 
            weight=4, 
            opacity=0.8,
            popup="Optimized Route"
        ).add_to(m)
    else:
        route_coords = [coords[idx] for idx in plan] + [coords[0]]
        folium.PolyLine(
            route_coords, 
            color="red", 
            weight=4, 
            opacity=0.8,
            popup="Optimized Route"
        ).add_to(m)
    
    st_folium(m, width=900, height=500)

# Help section
with st.expander("ℹ️ Help"):
    st.write("**Features:**")
    st.write("• ✅ **Address autocomplete** - Type 3+ characters")
    st.write("• ✅ **Google Maps integration** - Real routes and distances")
    st.write("• ✅ **OR-Tools optimization** - Professional route optimization")
    st.write("• ✅ **Interactive map** - Visualize your optimized route")
    
    st.write("\n**How to use:**")
    st.write("1. Enter depot address")
    st.write("2. Add pickup stops (use autocomplete for suggestions)")
    st.write("3. Click 'Optimize Routes'")
    st.write("4. View optimized route on map")
