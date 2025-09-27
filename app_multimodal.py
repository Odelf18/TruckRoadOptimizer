import os
import streamlit as st
import googlemaps
import folium
from streamlit_folium import st_folium
from ortools.constraint_solver import pywrapcp, routing_enums_pb2
from dotenv import load_dotenv
import time
import datetime

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

st.set_page_config(page_title="Multimodal Route Optimizer", layout="wide")

st.title("🚚 Multimodal Tire Pickup Route Optimizer")
st.markdown("**Optimize routes with 1-3 vehicles, capacity constraints, and working hours**")

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

# Vehicle and time constraints
st.subheader("🚛 Vehicle & Time Constraints")
col1, col2, col3, col4 = st.columns(4)

with col1:
    max_vehicles = st.number_input("**Max Vehicles Available**", 1, 3, 3, help="Maximum number of vehicles")
with col2:
    max_tires_per_vehicle = st.number_input("**Max Tires per Vehicle**", 50, 500, 300, help="Maximum tire capacity per vehicle")
with col3:
    base_loading_time = st.number_input("**Base Loading Time (min)**", 0, 60, 10, help="Fixed loading time per stop")
with col4:
    tire_loading_time = st.number_input("**Loading Time per Tire (min)**", 0.0, 2.0, 0.3, step=0.1, help="Additional time per tire")

# Working hours
col1, col2 = st.columns(2)
with col1:
    start_hour = st.time_input("**Work Start Time**", datetime.time(7, 0), help="Vehicle availability start time")
with col2:
    end_hour = st.time_input("**Work End Time**", datetime.time(17, 0), help="Vehicle availability end time")

# Convert to minutes from midnight
work_start_minutes = start_hour.hour * 60 + start_hour.minute
work_end_minutes = end_hour.hour * 60 + end_hour.minute
work_duration_minutes = work_end_minutes - work_start_minutes

st.info(f"📅 **Working Hours:** {start_hour.strftime('%I:%M %p')} - {end_hour.strftime('%I:%M %p')} ({work_duration_minutes} minutes)")

# Compact interface
col1, col2 = st.columns([3, 1])

with col1:
    depot_address = st.text_input("**Depot Address**", "Houston, TX")

with col2:
    n = st.number_input("**Number of Stops**", 1, 50, 5)

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
        # Show loading time for this stop
        loading_time = base_loading_time + (qty * tire_loading_time)
        st.metric("Loading", f"{loading_time:.1f} min")
    
    if addr:
        stops.append({"address": addr, "qty": qty})

# Check constraints
total_tires = sum(s['qty'] for s in stops)
min_vehicles_needed = (total_tires + max_tires_per_vehicle - 1) // max_tires_per_vehicle

if total_tires > max_vehicles * max_tires_per_vehicle:
    st.error(f"❌ Total tires ({total_tires}) exceeds total capacity ({max_vehicles * max_tires_per_vehicle}). Reduce stops or increase capacity.")
elif min_vehicles_needed > max_vehicles:
    st.warning(f"⚠️ Need at least {min_vehicles_needed} vehicles for {total_tires} tires, but only {max_vehicles} available.")

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

        # Multimodal optimization
        with st.spinner("🧮 Optimizing with multiple vehicles..."):
            # Try different numbers of vehicles
            best_solution = None
            best_vehicles = None
            best_time = float('inf')
            
            for num_vehicles in range(1, max_vehicles + 1):
                if num_vehicles < min_vehicles_needed:
                    continue
                    
                try:
                    manager = pywrapcp.RoutingIndexManager(n_points, num_vehicles, 0)
                    routing = pywrapcp.RoutingModel(manager)

                    def distance_callback(from_index, to_index):
                        return dist_matrix[manager.IndexToNode(from_index)][manager.IndexToNode(to_index)]

                    transit_cb = routing.RegisterTransitCallback(distance_callback)
                    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback)

                    # Add capacity constraints
                    def demand_callback(from_index):
                        node = manager.IndexToNode(from_index)
                        if node == 0:  # Depot
                            return 0
                        else:
                            return stops[node-1]['qty']

                    demand_cb = routing.RegisterUnaryTransitCallback(demand_callback)
                    routing.AddDimensionWithVehicleCapacity(
                        demand_cb,
                        0,  # null capacity slack
                        [max_tires_per_vehicle] * num_vehicles,  # vehicle maximum capacities
                        True,  # start cumul to zero
                        'Capacity'
                    )

                    # Add time constraints (travel + loading + working hours)
                    def time_callback(from_index, to_index):
                        from_node = manager.IndexToNode(from_index)
                        to_node = manager.IndexToNode(to_index)
                        
                        # Travel time
                        travel_time = dist_matrix[from_node][to_node]
                        
                        # Loading time at destination (if not depot)
                        loading_time = 0
                        if to_node != 0:  # Not depot
                            tire_qty = stops[to_node-1]['qty']
                            loading_time = base_loading_time + (tire_qty * tire_loading_time)
                        
                        return int(travel_time + loading_time)

                    time_cb = routing.RegisterTransitCallback(time_callback)
                    routing.AddDimension(
                        time_cb,
                        0,  # allow waiting time
                        work_duration_minutes,  # maximum time per vehicle (working hours)
                        False,  # don't force start cumul to zero
                        'Time'
                    )

                    # Set time windows for working hours
                    time_dimension = routing.GetDimensionOrDie('Time')
                    for vehicle_id in range(num_vehicles):
                        start_idx = routing.Start(vehicle_id)
                        time_dimension.CumulVar(start_idx).SetRange(work_start_minutes, work_start_minutes)
                        end_idx = routing.End(vehicle_id)
                        time_dimension.CumulVar(end_idx).SetRange(work_start_minutes, work_end_minutes)

                    search_params = pywrapcp.DefaultRoutingSearchParameters()
                    search_params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
                    search_params.time_limit.FromSeconds(30)

                    solution = routing.SolveWithParameters(search_params)
                    
                    if solution:
                        # Calculate total time for this solution
                        total_solution_time = 0
                        for vehicle_id in range(num_vehicles):
                            index = routing.Start(vehicle_id)
                            vehicle_time = 0
                            while not routing.IsEnd(index):
                                node = manager.IndexToNode(index)
                                next_index = solution.Value(routing.NextVar(index))
                                next_node = manager.IndexToNode(next_index)
                                
                                # Add travel time
                                vehicle_time += dist_matrix[node][next_node]
                                
                                # Add loading time at destination
                                if next_node != 0:  # Not depot
                                    tire_qty = stops[next_node-1]['qty']
                                    vehicle_time += base_loading_time + (tire_qty * tire_loading_time)
                                
                                index = next_index
                            
                            total_solution_time = max(total_solution_time, vehicle_time)
                        
                        if total_solution_time < best_time:
                            best_time = total_solution_time
                            best_solution = solution
                            best_vehicles = num_vehicles
                            best_routing = routing
                            best_manager = manager
                            
                except Exception as e:
                    continue

        if best_solution:
            # Get optimized routes for all vehicles
            vehicle_routes = []
            vehicle_coords = []
            
            for vehicle_id in range(best_vehicles):
                index = best_routing.Start(vehicle_id)
                route = []
                route_coords = [depot_latlon]
                
                while not best_routing.IsEnd(index):
                    node = best_manager.IndexToNode(index)
                    route.append(node)
                    if node != 0:  # Not depot
                        route_coords.append(stops[node-1]["latlon"])
                    index = best_solution.Value(best_routing.NextVar(index))
                
                route.append(best_manager.IndexToNode(index))  # Add end depot
                route_coords.append(depot_latlon)  # Return to depot
                
                vehicle_routes.append(route)
                vehicle_coords.append(route_coords)

            # Get detailed routes for visualization
            with st.spinner("🛣️ Calculating detailed routes..."):
                all_route_coords = []
                for route_coords in vehicle_coords:
                    for i in range(len(route_coords) - 1):
                        start_coord = route_coords[i]
                        end_coord = route_coords[i + 1]
                        
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
                            all_route_coords.extend(decoded_coords)
                            time.sleep(0.1)

            # Save results
            st.session_state.results = {
                'vehicle_routes': vehicle_routes,
                'vehicle_coords': vehicle_coords,
                'stops': stops,
                'depot_address': depot_address,
                'depot_latlon': depot_latlon,
                'dist_matrix': dist_matrix,
                'coords': coords,
                'route_coords': all_route_coords,
                'num_vehicles': best_vehicles,
                'total_time': best_time,
                'max_tires_per_vehicle': max_tires_per_vehicle,
                'base_loading_time': base_loading_time,
                'tire_loading_time': tire_loading_time,
                'work_start': work_start_minutes,
                'work_end': work_end_minutes
            }
            
            st.success(f"✅ Optimized with {best_vehicles} vehicle(s) in {best_time:.1f} minutes!")
        else:
            st.error("❌ No solution found - try reducing stops or increasing capacity/time")

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
    vehicle_routes = results['vehicle_routes']
    vehicle_coords = results['vehicle_coords']
    stops = results['stops']
    depot_address = results['depot_address']
    depot_latlon = results['depot_latlon']
    dist_matrix = results['dist_matrix']
    coords = results['coords']
    route_coords = results.get('route_coords', [])
    num_vehicles = results.get('num_vehicles', 1)
    total_time = results.get('total_time', 0)
    max_tires_per_vehicle = results.get('max_tires_per_vehicle', 300)
    base_loading_time = results.get('base_loading_time', 10)
    tire_loading_time = results.get('tire_loading_time', 0.3)
    work_start = results.get('work_start', 420)  # 7 AM
    work_end = results.get('work_end', 1020)  # 5 PM

    # Results summary
    st.subheader("📋 Optimization Results")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Vehicles Used", num_vehicles)
    with col2:
        st.metric("Total Time", f"{total_time:.1f} min")
    with col3:
        total_tires = sum(s['qty'] for s in stops)
        st.metric("Total Tires", total_tires)
    with col4:
        efficiency = (total_tires / (num_vehicles * max_tires_per_vehicle)) * 100
        st.metric("Efficiency", f"{efficiency:.1f}%")

    # Detailed routes for each vehicle
    for vehicle_id, route in enumerate(vehicle_routes):
        st.subheader(f"🚛 Vehicle {vehicle_id + 1} Route")
        
        vehicle_tires = 0
        vehicle_time = 0
        
        for i, node in enumerate(route):
            if node == 0:
                st.write(f"🏢 **Depot:** {depot_address}")
            else:
                s = stops[node-1]
                loading_time = base_loading_time + (s['qty'] * tire_loading_time)
                vehicle_tires += s['qty']
                st.write(f"📍 **Stop {i}:** {s['address']} ({s['qty']} tires)")
                st.write(f"   ⏱️ Loading time: {loading_time:.1f} min")
                
                if i > 0:
                    prev_node = route[i-1]
                    travel_time = dist_matrix[prev_node][node]
                    vehicle_time += travel_time
                    st.write(f"   🚗 Travel time: {travel_time} min")
        
        st.write(f"**Vehicle {vehicle_id + 1} Summary:** {vehicle_tires} tires, {vehicle_time:.1f} min travel time")
        st.markdown("---")

    # Interactive map
    st.subheader("🗺️ Route Map")
    
    m = folium.Map(location=depot_latlon, zoom_start=12, tiles='OpenStreetMap')
    
    # Depot marker
    folium.Marker(
        depot_latlon, 
        icon=folium.Icon(color="red", icon="warehouse", prefix="fa"), 
        popup="🏢 Depot"
    ).add_to(m)
    
    # Vehicle routes with different colors
    colors = ['red', 'blue', 'green', 'purple', 'orange']
    
    for vehicle_id, route in enumerate(vehicle_routes):
        color = colors[vehicle_id % len(colors)]
        
        # Stop markers for this vehicle
        for i, node in enumerate(route):
            if node != 0:  # Not depot
                s = stops[node-1]
                loading_time = base_loading_time + (s['qty'] * tire_loading_time)
                folium.Marker(
                    s["latlon"],
                    popup=f"🚛 Vehicle {vehicle_id + 1}<br>📍 Stop {i}<br>{s['address']}<br>📦 {s['qty']} tires<br>⏱️ {loading_time:.1f} min loading",
                    icon=folium.Icon(color=color, icon="truck", prefix="fa")
                ).add_to(m)
        
        # Route line for this vehicle
        if len(route) > 1:
            route_coords = [coords[node] for node in route]
            folium.PolyLine(
                route_coords, 
                color=color, 
                weight=4, 
                opacity=0.8,
                popup=f"Vehicle {vehicle_id + 1} Route"
            ).add_to(m)
    
    st_folium(m, width=900, height=600)

# Help section
with st.expander("ℹ️ Help"):
    st.write("**Features:**")
    st.write("• ✅ **Multimodal optimization** - Uses 1-3 vehicles optimally")
    st.write("• ✅ **Capacity constraints** - 300 tires max per vehicle")
    st.write("• ✅ **Working hours** - 7AM to 5PM availability")
    st.write("• ✅ **Loading time calculation** - Base time + time per tire")
    st.write("• ✅ **Address autocomplete** - Type 3+ characters")
    st.write("• ✅ **Google Maps integration** - Real routes and distances")
    
    st.write("\n**Optimization Strategy:**")
    st.write("1. Tries 1, 2, then 3 vehicles")
    st.write("2. Finds minimum vehicles needed for capacity")
    st.write("3. Optimizes for shortest total time")
    st.write("4. Respects working hours (7AM-5PM)")
    
    st.write("\n**Loading Time Formula:**")
    st.write(f"Loading Time = {base_loading_time} min + (Number of Tires × {tire_loading_time} min)")
