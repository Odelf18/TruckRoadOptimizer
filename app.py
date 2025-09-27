import os
import streamlit as st
import googlemaps
import folium
from streamlit_folium import st_folium
from ortools.constraint_solver import pywrapcp, routing_enums_pb2
from dotenv import load_dotenv
import time
import datetime
import json
import random

# Load environment variables
load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")

# Helper function to calculate distance between two points
def calculate_distance(coord1, coord2):
    """Calculate straight-line distance between two coordinates in km"""
    from math import radians, cos, sin, asin, sqrt
    
    lat1, lon1 = coord1
    lat2, lon2 = coord2
    
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    
    # Radius of earth in kilometers
    r = 6371
    return c * r

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

# Load mock addresses
@st.cache_data
def load_mock_addresses():
    try:
        with open('addresses.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        st.error("❌ addresses.json file not found")
        return []
    except json.JSONDecodeError:
        st.error("❌ Invalid JSON in addresses.json")
        return []

mock_addresses = load_mock_addresses()

# Initialize session state
if 'optimization_done' not in st.session_state:
    st.session_state.optimization_done = False
if 'results' not in st.session_state:
    st.session_state.results = None
if 'mock_mode' not in st.session_state:
    st.session_state.mock_mode = False

# Function to get address suggestions
def get_address_suggestions(query):
    """Get address suggestions via Google Places API"""
    if len(query) < 3:
        return []
    
    try:
        places_result = gmaps.places_autocomplete(
            input_text=query,
            types='address',
            language='en'
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
    base_loading_time = st.number_input("**Base Loading Time (min)**", 0, 60, 1, help="Fixed loading time per stop")
with col4:
    tire_loading_time = st.number_input("**Loading Time per Tire (min)**", 0.0, 2.0, 0.1, step=0.1, help="Additional time per tire")

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

st.info(f"📅 **Working Hours:** {start_hour.strftime('%I:%M %p')} - {end_hour.strftime('%I:%M %p')} ({work_duration_minutes} minutes per vehicle)")

# Mock data section
st.subheader("🎲 Mock Data Generator")
col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    st.write("**Generate test data from addresses.json**")
with col2:
    if st.button("🎲 Generate Mock Data", help="Fill stops with random addresses from addresses.json"):
        if mock_addresses:
            st.session_state.mock_mode = True
            st.rerun()
        else:
            st.error("No mock addresses available")
with col3:
    if st.button("🔄 Clear Mock Data", help="Clear all generated data"):
        st.session_state.mock_mode = False
        st.rerun()

# Interface
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
        
        # If in mock mode, pre-fill with random address
        if st.session_state.mock_mode and mock_addresses:
            if addr_key not in st.session_state or not st.session_state[addr_key]:
                random_addr = random.choice(mock_addresses)
                st.session_state[addr_key] = random_addr['address']
        
        addr = st.text_input(f"Stop {i+1} Address", key=addr_key, placeholder="Type 3+ characters...")
        
        # Show suggestions (simplified to avoid session state issues)
        if addr and len(addr) >= 3:
            suggestions = get_address_suggestions(addr)
            if suggestions:
                st.write("**Suggestions:**")
                for j, suggestion in enumerate(suggestions[:3]):  # Show only top 3
                    st.write(f"• {suggestion}")
    
    with col2:
        qty_key = f"qty_{i}"
        
        # If in mock mode, pre-fill with random quantity
        if st.session_state.mock_mode:
            if qty_key not in st.session_state or not st.session_state[qty_key]:
                st.session_state[qty_key] = random.randint(15, 20)
        
        qty = st.number_input(f"Tires", 0, 500, 50, key=qty_key)
    
    with col3:
        # Show loading time for this stop
        loading_time = base_loading_time + (qty * tire_loading_time)
        st.metric("Loading", f"{loading_time:.1f} min")
    
    if addr:
        stops.append({"address": addr, "qty": qty})

# Show mock data info
if st.session_state.mock_mode and mock_addresses:
    st.info(f"🎲 **Mock Mode Active** - Using {len(mock_addresses)} addresses from addresses.json")

# Check constraints
total_tires = sum(s['qty'] for s in stops)
min_vehicles_needed = (total_tires + max_tires_per_vehicle - 1) // max_tires_per_vehicle

if total_tires > max_vehicles * max_tires_per_vehicle:
    st.error(f"❌ Total tires ({total_tires}) exceeds total capacity ({max_vehicles * max_tires_per_vehicle}). Reduce stops or increase capacity.")
elif min_vehicles_needed > max_vehicles:
    st.warning(f"⚠️ Need at least {min_vehicles_needed} vehicles for {total_tires} tires, but only {max_vehicles} available.")

# Action buttons
col1, col2, col3, col4 = st.columns([1, 1, 1, 3])
with col1:
    optimize_clicked = st.button("🚀 Optimize Routes", type="primary", use_container_width=True)
with col2:
    test_async_clicked = st.button("🧪 Test Async", use_container_width=True, help="Test 1, 2, 3 vehicles in parallel")
with col3:
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

        # Distance matrix using Google Maps API with batching to avoid limits
        with st.spinner("📊 Calculating distance matrix with Google Maps..."):
            n_points = len(coords)
            dist_matrix = [[0 for _ in range(n_points)] for _ in range(n_points)]
            
            # Validate coordinates (silent validation)
            for i, coord in enumerate(coords):
                if not isinstance(coord, (tuple, list)) or len(coord) != 2:
                    st.error(f"❌ Invalid coordinate {i}: {coord}")
                    st.stop()
                lat, lng = coord
                if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
                    st.error(f"❌ Invalid lat/lng {i}: ({lat}, {lng})")
                    st.stop()
            
            # Google Maps Distance Matrix API limit is 25 elements per request
            # We need to make multiple requests for larger matrices
            batch_size = 5  # 5x5 = 25 elements max per request
            
            for i in range(0, n_points, batch_size):
                for j in range(0, n_points, batch_size):
                    # Get batch of origins and destinations
                    origins_batch = coords[i:i+batch_size]
                    destinations_batch = coords[j:j+batch_size]
                    
                    try:
                        matrix_result = gmaps.distance_matrix(
                            origins=origins_batch,
                            destinations=destinations_batch,
                            mode="driving",
                            units="metric",
                            region="us"
                        )
                        
                        # Fill the distance matrix with results
                        for row_idx, row in enumerate(matrix_result["rows"]):
                            for col_idx, element in enumerate(row["elements"]):
                                if element["status"] == "OK":
                                    duration_minutes = element["duration"]["value"] / 60
                                    dist_matrix[i + row_idx][j + col_idx] = duration_minutes
                                else:
                                    # Fallback to straight-line distance if API fails
                                    straight_dist = calculate_distance(coords[i + row_idx], coords[j + col_idx])
                                    estimated_time = (straight_dist * 1.5) / 30 * 60  # Rough estimate
                                    dist_matrix[i + row_idx][j + col_idx] = estimated_time
                        
                        # Small delay to avoid rate limiting
                        time.sleep(0.1)
                        
                    except Exception as e:
                        st.warning(f"⚠️ API error for batch {i}-{j}: {e}")
                        # Fill with fallback estimates
                        for row_idx in range(len(origins_batch)):
                            for col_idx in range(len(destinations_batch)):
                                if i + row_idx != j + col_idx:  # Not diagonal
                                    straight_dist = calculate_distance(coords[i + row_idx], coords[j + col_idx])
                                    estimated_time = (straight_dist * 1.5) / 30 * 60
                                    dist_matrix[i + row_idx][j + col_idx] = estimated_time
            
            # Final validation of distance matrix (silent)
            matrix_issues = []
            
            for i in range(n_points):
                for j in range(n_points):
                    val = dist_matrix[i][j]
                    if val < 0:
                        matrix_issues.append(f"Negative distance ({i},{j})={val}")
                    elif val != val:  # NaN
                        matrix_issues.append(f"NaN distance ({i},{j})={val}")
                    elif i != j and val == 0:
                        matrix_issues.append(f"Zero distance ({i},{j})={val}")
                    elif val > 10000:
                        matrix_issues.append(f"Very large distance ({i},{j})={val}")
            
            if matrix_issues:
                st.warning(f"⚠️ Matrix issues found: {matrix_issues[:5]}")
                # Fix common issues
                for i in range(n_points):
                    for j in range(n_points):
                        if dist_matrix[i][j] < 0 or dist_matrix[i][j] != dist_matrix[i][j]:  # NaN
                            dist_matrix[i][j] = 0.1
                        elif i != j and dist_matrix[i][j] == 0:
                            dist_matrix[i][j] = 0.1
                        elif dist_matrix[i][j] > 10000:
                            dist_matrix[i][j] = 10000
            
            st.success("✅ Distance matrix calculated using Google Maps API")

        # Calculate minimum vehicles needed based on capacity
        total_tires = sum(s['qty'] for s in stops)
        min_vehicles_capacity = (total_tires + max_tires_per_vehicle - 1) // max_tires_per_vehicle
        
        st.write(f"📊 **Analysis:** Need {min_vehicles_capacity} vehicles minimum for capacity, {max_vehicles} available")

        # Multimodal optimization - try from minimum needed to max available
        with st.spinner("🧮 Optimizing with multiple vehicles..."):
            best_solution = None
            best_vehicles = None
            best_time = float('inf')
            best_routes = None
            
            # Start with minimum vehicles needed, up to max available
            for num_vehicles in range(min_vehicles_capacity, max_vehicles + 1):
                with st.expander(f"🔍 Testing {num_vehicles} vehicle(s)", expanded=True):
                    st.write(f"**Testing configuration with {num_vehicles} vehicle(s)...**")
                
                try:
                    manager = pywrapcp.RoutingIndexManager(n_points, num_vehicles, 0)
                    routing = pywrapcp.RoutingModel(manager)

                    def distance_callback(from_index, to_index):
                        from_node = manager.IndexToNode(from_index)
                        to_node = manager.IndexToNode(to_index)
                        distance = dist_matrix[from_node][to_node]
                        
                        # Ensure distance is valid and not too large
                        if distance < 0:
                            distance = 0.1
                        elif distance > 10000:  # More than 166 hours
                            distance = 10000
                        elif distance != distance:  # NaN check
                            distance = 0.1
                            
                        return int(distance * 1000)  # Convert to integer (OR-Tools prefers integers)

                    transit_cb = routing.RegisterTransitCallback(distance_callback)
                    routing.SetArcCostEvaluatorOfAllVehicles(transit_cb)

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
                    
                    # Ajouter des contraintes de temps pour forcer la redistribution
                    def time_callback(from_index, to_index):
                        from_node = manager.IndexToNode(from_index)
                        to_node = manager.IndexToNode(to_index)
                        travel_time = dist_matrix[from_node][to_node]
                        
                        # Ajouter le temps de chargement si on va vers un arrêt
                        if to_node != 0:  # Pas le dépôt
                            loading_time = base_loading_time + (stops[to_node-1]['qty'] * tire_loading_time)
                            return int((travel_time + loading_time) * 1000)
                        return int(travel_time * 1000)
                    
                    time_cb = routing.RegisterTransitCallback(time_callback)
                    routing.AddDimension(
                        time_cb,
                        work_duration_minutes * 1000,  # Slack maximum (600 min)
                        work_duration_minutes * 1000,  # Capacité maximale (600 min)
                        False,  # start cumul to zero
                        'Time'
                    )
                    
                    # Contrainte : chaque véhicule doit respecter les heures de travail
                    time_dimension = routing.GetDimensionOrDie('Time')
                    for vehicle_id in range(num_vehicles):
                        time_dimension.CumulVar(routing.End(vehicle_id)).SetMax(work_duration_minutes * 1000)
                    
                    # Silent constraint validation
                    total_tires = sum(s['qty'] for s in stops)
                    
                    search_params = pywrapcp.DefaultRoutingSearchParameters()
                    search_params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
                    search_params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
                    search_params.time_limit.FromSeconds(60)

                    # Silent matrix validation and fixing
                    for i in range(n_points):
                        for j in range(n_points):
                            if i != j and dist_matrix[i][j] == 0:
                                dist_matrix[i][j] = 0.1  # 0.1 minute minimum
                    
                    # Try to solve
                    try:
                        solution = routing.SolveWithParameters(search_params)
                        
                        if solution:
                            # Calculate total time for this solution
                            vehicle_times = []
                            vehicle_routes = []
                        
                            for vehicle_id in range(num_vehicles):
                                index = routing.Start(vehicle_id)
                                route = []
                                
                                # Utiliser la dimension Time pour obtenir le temps exact
                                time_dimension = routing.GetDimensionOrDie('Time')
                                vehicle_time = solution.Value(time_dimension.CumulVar(routing.End(vehicle_id))) / 1000.0
                                
                                while not routing.IsEnd(index):
                                    node = manager.IndexToNode(index)
                                    route.append(node)
                                    next_index = solution.Value(routing.NextVar(index))
                                    index = next_index
                                
                                route.append(manager.IndexToNode(index))  # Add end depot
                                vehicle_times.append(vehicle_time)
                                vehicle_routes.append(route)
                        
                            max_vehicle_time = max(vehicle_times)
                            st.write(f"✅ {num_vehicles} vehicle(s): Max time = {max_vehicle_time:.1f} min")
                            
                            # Check if any vehicle exceeds working hours (each vehicle has its own 600 min)
                            vehicles_over_limit = [i for i, time in enumerate(vehicle_times) if time > work_duration_minutes]
                            
                            if vehicles_over_limit:
                                st.write(f"⚠️ {num_vehicles} vehicle(s): {len(vehicles_over_limit)} vehicle(s) exceed working hours")
                                for v in vehicles_over_limit:
                                    st.write(f"   - Vehicle {v+1}: {vehicle_times[v]:.1f} min > {work_duration_minutes} min")
                            else:
                                # All vehicles are within working hours
                                if max_vehicle_time < best_time:
                                    best_time = max_vehicle_time
                                    best_solution = solution
                                    best_vehicles = num_vehicles
                                    best_routing = routing
                                    best_manager = manager
                                    best_routes = vehicle_routes
                                    st.write(f"🎯 New best solution: {num_vehicles} vehicles in {max_vehicle_time:.1f} min")
                        else:
                            st.write(f"❌ {num_vehicles} vehicle(s): No solution found")
                            
                    except Exception as solve_error:
                        st.write(f"❌ {num_vehicles} vehicle(s): No solution found")
                        continue
                        
                except Exception as e:
                    st.write(f"❌ {num_vehicles} vehicle(s): Setup error")
                    continue

        if best_solution:
            # Get optimized routes for all vehicles
            vehicle_routes = best_routes
            vehicle_coords = []
            
            for route in vehicle_routes:
                route_coords = [depot_latlon]
                for node in route[1:-1]:  # Skip depot at start and end
                    route_coords.append(stops[node-1]["latlon"])
                route_coords.append(depot_latlon)  # Return to depot
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
            st.error("❌ No solution found - try reducing stops, increasing capacity, or extending working hours")

    except Exception as e:
        st.error(f"❌ Optimization error: {e}")

# Async test logic
if test_async_clicked and stops:
    st.session_state.optimization_done = True
    
    try:
        # Geocoding (same as normal optimization)
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

        # Distance matrix (same as normal optimization)
        with st.spinner("📊 Calculating distance matrix..."):
            n_points = len(coords)
            dist_matrix = [[0 for _ in range(n_points)] for _ in range(n_points)]
            
            # Use simplified distance calculation for async test
            for i in range(n_points):
                for j in range(n_points):
                    if i != j:
                        dist_matrix[i][j] = calculate_distance(coords[i], coords[j]) * 1.5 / 30 * 60  # Convert to minutes
                    else:
                        dist_matrix[i][j] = 0
            
            # Fix zero distances
            for i in range(n_points):
                for j in range(n_points):
                    if i != j and dist_matrix[i][j] == 0:
                        dist_matrix[i][j] = 0.1

        # Async test function
        def test_vehicle_count(num_vehicles):
            try:
                manager = pywrapcp.RoutingIndexManager(n_points, num_vehicles, 0)
                routing = pywrapcp.RoutingModel(manager)

                def distance_callback(from_index, to_index):
                    from_node = manager.IndexToNode(from_index)
                    to_node = manager.IndexToNode(to_index)
                    distance = dist_matrix[from_node][to_node]
                    
                    if distance < 0:
                        distance = 0.1
                    elif distance > 10000:
                        distance = 10000
                    elif distance != distance:  # NaN
                        distance = 0.1
                        
                    return int(distance * 1000)

                transit_cb = routing.RegisterTransitCallback(distance_callback)
                routing.SetArcCostEvaluatorOfAllVehicles(transit_cb)

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
                    0,
                    [max_tires_per_vehicle] * num_vehicles,
                    True,
                    'Capacity'
                )
                
                # Ajouter les mêmes contraintes de temps que l'optimisation principale
                def time_callback(from_index, to_index):
                    from_node = manager.IndexToNode(from_index)
                    to_node = manager.IndexToNode(to_index)
                    travel_time = dist_matrix[from_node][to_node]
                    
                    if to_node != 0:  # Pas le dépôt
                        loading_time = base_loading_time + (stops[to_node-1]['qty'] * tire_loading_time)
                        return int((travel_time + loading_time) * 1000)
                    return int(travel_time * 1000)
                
                time_cb = routing.RegisterTransitCallback(time_callback)
                routing.AddDimension(
                    time_cb,
                    work_duration_minutes * 1000,
                    work_duration_minutes * 1000,
                    False,
                    'Time'
                )
                
                # Contrainte : chaque véhicule doit respecter les heures de travail
                time_dimension = routing.GetDimensionOrDie('Time')
                for vehicle_id in range(num_vehicles):
                    time_dimension.CumulVar(routing.End(vehicle_id)).SetMax(work_duration_minutes * 1000)

                search_params = pywrapcp.DefaultRoutingSearchParameters()
                search_params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
                search_params.time_limit.FromSeconds(10)

                solution = routing.SolveWithParameters(search_params)

                if solution:
                    # Calculate solution metrics
                    vehicle_times = []
                    vehicle_routes = []
                    
                    for vehicle_id in range(num_vehicles):
                        index = routing.Start(vehicle_id)
                        route = []
                        
                        # Utiliser la dimension Time pour obtenir le temps exact
                        time_dimension = routing.GetDimensionOrDie('Time')
                        vehicle_time = solution.Value(time_dimension.CumulVar(routing.End(vehicle_id))) / 1000.0
                        
                        while not routing.IsEnd(index):
                            node = manager.IndexToNode(index)
                            route.append(node)
                            next_index = solution.Value(routing.NextVar(index))
                            index = next_index
                        
                        route.append(manager.IndexToNode(index))
                        vehicle_times.append(vehicle_time)
                        vehicle_routes.append(route)
                    
                    max_vehicle_time = max(vehicle_times) if vehicle_times else 0
                    # Check if any vehicle exceeds working hours (each vehicle has its own 600 min)
                    vehicles_over_limit = [i for i, time in enumerate(vehicle_times) if time > work_duration_minutes]
                    all_vehicles_within_limit = len(vehicles_over_limit) == 0
                    
                    return {
                        'success': True,
                        'vehicles': num_vehicles,
                        'max_time': max_vehicle_time,
                        'fits_work_hours': all_vehicles_within_limit,
                        'vehicles_over_limit': vehicles_over_limit,
                        'vehicle_times': vehicle_times,
                        'routes': vehicle_routes
                    }
                else:
                    return {
                        'success': False,
                        'vehicles': num_vehicles,
                        'error': 'No solution found'
                    }
                    
            except Exception as e:
                return {
                    'success': False,
                    'vehicles': num_vehicles,
                    'error': str(e)
                }

        # Run async tests
        with st.spinner("🧪 Testing 1, 2, 3 vehicles in parallel..."):
            import concurrent.futures
            import threading
            
            results = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(test_vehicle_count, i) for i in range(1, 4)]
                
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    results.append(result)
            
            # Sort results by vehicle count
            results.sort(key=lambda x: x['vehicles'])
            
            # Display results
            st.subheader("🧪 Async Test Results")
            
            for result in results:
                if result['success']:
                    if result['fits_work_hours']:
                        st.write(f"✅ **{result['vehicles']} vehicle(s):** {result['max_time']:.1f} min (all vehicles within work hours)")
                    else:
                        st.write(f"⚠️ **{result['vehicles']} vehicle(s):** {result['max_time']:.1f} min (some vehicles exceed work hours)")
                        # Show details for each vehicle
                        for i, time in enumerate(result['vehicle_times']):
                            if i in result['vehicles_over_limit']:
                                st.write(f"   - Vehicle {i+1}: {time:.1f} min ❌ (exceeds {work_duration_minutes} min)")
                            else:
                                st.write(f"   - Vehicle {i+1}: {time:.1f} min ✅")
                else:
                    st.write(f"❌ **{result['vehicles']} vehicle(s):** {result['error']}")
            
            # Find best solution
            valid_results = [r for r in results if r['success'] and r['fits_work_hours']]
            if valid_results:
                best_result = min(valid_results, key=lambda x: x['vehicles'])
                st.success(f"🎯 **Best solution:** {best_result['vehicles']} vehicle(s) in {best_result['max_time']:.1f} minutes")
                
                # Save best result for display
                st.session_state.results = {
                    'vehicle_routes': best_result['routes'],
                    'vehicle_coords': [],  # Will be calculated if needed
                    'stops': stops,
                    'depot_address': depot_address,
                    'depot_latlon': depot_latlon,
                    'dist_matrix': dist_matrix,
                    'coords': coords,
                    'route_coords': [],
                    'num_vehicles': best_result['vehicles'],
                    'total_time': best_result['max_time'],
                    'max_tires_per_vehicle': max_tires_per_vehicle,
                    'base_loading_time': base_loading_time,
                    'tire_loading_time': tire_loading_time,
                    'work_start': work_start_minutes,
                    'work_end': work_end_minutes
                }
            else:
                st.error("❌ No valid solutions found in async test")

    except Exception as e:
        st.error(f"❌ Async test error: {e}")

# Reset
if reset_clicked:
    st.session_state.optimization_done = False
    st.session_state.results = None
    st.session_state.mock_mode = False
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
    base_loading_time = results.get('base_loading_time', 1)
    tire_loading_time = results.get('tire_loading_time', 0.1)
    work_start = results.get('work_start', 420)  # 7 AM
    work_end = results.get('work_end', 1020)  # 5 PM

    # Results summary
    st.subheader("📋 Optimization Results")
    
    # Calculate vehicle summaries first
    vehicle_summaries = []
    for vehicle_id, route in enumerate(vehicle_routes):
        vehicle_tires = 0
        vehicle_travel_time = 0
        vehicle_loading_time = 0
        
        for i, node in enumerate(route):
            if node != 0:  # Not depot
                s = stops[node-1]
                loading_time = base_loading_time + (s['qty'] * tire_loading_time)
                vehicle_tires += s['qty']
                vehicle_loading_time += loading_time
                
                if i > 0:
                    prev_node = route[i-1]
                    travel_time = dist_matrix[prev_node][node]
                    vehicle_travel_time += travel_time
        
        total_vehicle_time = vehicle_travel_time + vehicle_loading_time
        vehicle_departure_time = datetime.time(work_start // 60, work_start % 60)
        vehicle_return_minutes = int(work_start + total_vehicle_time)
        vehicle_return_time = datetime.time(vehicle_return_minutes // 60, vehicle_return_minutes % 60)
        
        vehicle_summaries.append({
            'id': vehicle_id + 1,
            'tires': vehicle_tires,
            'travel_time': vehicle_travel_time,
            'loading_time': vehicle_loading_time,
            'total_time': total_vehicle_time,
            'departure': vehicle_departure_time,
            'return': vehicle_return_time
        })
    
    # Display vehicle summaries in a clear table
    st.subheader("🚛 Vehicle Summary")
    
    for vehicle in vehicle_summaries:
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        with col1:
            st.write(f"**Vehicle {vehicle['id']}**")
        with col2:
            st.write(f"📦 {vehicle['tires']} tires")
        with col3:
            st.write(f"🚗 {vehicle['travel_time']:.1f} min")
        with col4:
            st.write(f"⏱️ {vehicle['loading_time']:.1f} min")
        with col5:
            st.write(f"🕐 {vehicle['departure'].strftime('%I:%M %p')}")
        with col6:
            st.write(f"🏠 {vehicle['return'].strftime('%I:%M %p')}")
    
    # Overall metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Vehicles Used", num_vehicles)
    with col2:
        st.metric("Max Vehicle Time", f"{total_time:.1f} min")
    with col3:
        total_tires = sum(s['qty'] for s in stops)
        st.metric("Total Tires", total_tires)
    with col4:
        efficiency = (total_tires / (num_vehicles * max_tires_per_vehicle)) * 100
        st.metric("Efficiency", f"{efficiency:.1f}%")

    # Decision analysis
    st.subheader("🧠 Decision Analysis")
    
    # Calculate minimum vehicles needed for capacity
    min_vehicles_capacity = (total_tires + max_tires_per_vehicle - 1) // max_tires_per_vehicle
    
    # Create analysis explanation
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.write("**Why this number of vehicles was chosen:**")
        
        if num_vehicles == 1:
            st.write("✅ **Single vehicle sufficient** - All stops can be completed by one vehicle")
            st.write(f"   • Capacity: {total_tires} tires ≤ {max_tires_per_vehicle} max capacity")
            st.write(f"   • Time: {total_time:.1f} min ≤ {work_duration_minutes} min working hours")
        elif num_vehicles == 2:
            if min_vehicles_capacity == 2:
                st.write("✅ **Two vehicles required** - Capacity constraint")
                st.write(f"   • Capacity: {total_tires} tires > {max_tires_per_vehicle} (needs 2 vehicles)")
                st.write(f"   • Time: {total_time:.1f} min ≤ {work_duration_minutes} min working hours")
            else:
                st.write("✅ **Two vehicles chosen** - Time constraint")
                st.write(f"   • Capacity: {total_tires} tires ≤ {max_tires_per_vehicle * 2} (could fit in 1 vehicle)")
                st.write(f"   • Time: Single vehicle would take > {work_duration_minutes} min")
                st.write(f"   • Two vehicles: {total_time:.1f} min ≤ {work_duration_minutes} min working hours")
        elif num_vehicles == 3:
            if min_vehicles_capacity == 3:
                st.write("✅ **Three vehicles required** - Capacity constraint")
                st.write(f"   • Capacity: {total_tires} tires > {max_tires_per_vehicle * 2} (needs 3 vehicles)")
                st.write(f"   • Time: {total_time:.1f} min ≤ {work_duration_minutes} min working hours")
            else:
                st.write("✅ **Three vehicles chosen** - Time constraint")
                st.write(f"   • Capacity: {total_tires} tires ≤ {max_tires_per_vehicle * 3} (could fit in fewer vehicles)")
                st.write(f"   • Time: Fewer vehicles would take > {work_duration_minutes} min")
                st.write(f"   • Three vehicles: {total_time:.1f} min ≤ {work_duration_minutes} min working hours")
    
    with col2:
        st.write("**Constraints Summary:**")
        st.write(f"• **Total tires:** {total_tires}")
        st.write(f"• **Capacity per vehicle:** {max_tires_per_vehicle}")
        st.write(f"• **Min vehicles needed:** {min_vehicles_capacity}")
        st.write(f"• **Max vehicles available:** {max_vehicles}")
        st.write(f"• **Working hours:** {work_duration_minutes} min")
        st.write(f"• **Solution time:** {total_time:.1f} min")
        st.write(f"• **Includes:** Travel time + Loading time")
        
        # Show what would happen with fewer vehicles
        if num_vehicles > 1:
            st.write("**Alternative analysis:**")
            if num_vehicles == 2:
                st.write("• 1 vehicle: Would exceed capacity or time")
            elif num_vehicles == 3:
                st.write("• 1-2 vehicles: Would exceed capacity or time")

    # Detailed routes for each vehicle
    for vehicle_id, route in enumerate(vehicle_routes):
        st.subheader(f"🚛 Vehicle {vehicle_id + 1} Route")
        
        for i, node in enumerate(route):
            if node == 0:
                st.write(f"🏢 **Depot:** {depot_address}")
            else:
                s = stops[node-1]
                loading_time = base_loading_time + (s['qty'] * tire_loading_time)
                st.write(f"📍 **Stop {i}:** {s['address']} ({s['qty']} tires)")
                st.write(f"   ⏱️ Loading time: {loading_time:.1f} min")
                
                if i > 0:
                    prev_node = route[i-1]
                    travel_time = dist_matrix[prev_node][node]
                    st.write(f"   🚗 Travel time: {travel_time} min")
        
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

        # Route line for this vehicle - use detailed Google Maps routes
        if len(route) > 1:
            # Get detailed route for this vehicle
            vehicle_route_coords = []
            for i in range(len(route) - 1):
                start_node = route[i]
                end_node = route[i + 1]
                
                if start_node == 0:  # From depot
                    start_coord = depot_latlon
                else:
                    start_coord = stops[start_node-1]["latlon"]
                
                if end_node == 0:  # To depot
                    end_coord = depot_latlon
                else:
                    end_coord = stops[end_node-1]["latlon"]
                
                # Get Google Maps directions
                try:
                    directions_result = gmaps.directions(
                        origin=start_coord,
                        destination=end_coord,
                        mode="driving",
                        avoid=["tolls", "ferries"]
                    )
                    
                    if directions_result:
                        import polyline as pl
                        polyline_str = directions_result[0]["overview_polyline"]["points"]
                        decoded_coords = pl.decode(polyline_str)
                        vehicle_route_coords.extend(decoded_coords)
                except Exception as e:
                    # Fallback to straight line if Google Maps fails
                    vehicle_route_coords.extend([start_coord, end_coord])
            
            if vehicle_route_coords:
                folium.PolyLine(
                    vehicle_route_coords, 
                    color=color, 
                    weight=4, 
                    opacity=0.8,
                    popup=f"Vehicle {vehicle_id + 1} Route (Google Maps)"
                ).add_to(m)
            else:
                # Fallback to straight line
                route_coords = [coords[node] for node in route]
                folium.PolyLine(
                    route_coords, 
                    color=color, 
                    weight=4, 
                    opacity=0.8,
                    popup=f"Vehicle {vehicle_id + 1} Route (Straight line)"
                ).add_to(m)

    st_folium(m, width=900, height=600)

# Help section
with st.expander("ℹ️ Help"):
    st.write("**Features:**")
    st.write("• ✅ **Smart vehicle allocation** - Calculates minimum vehicles needed")
    st.write("• ✅ **Time constraint checking** - Ensures routes fit working hours")
    st.write("• ✅ **Mock data generator** - Use addresses.json for quick testing")
    st.write("• ✅ **Capacity constraints** - 300 tires max per vehicle")
    st.write("• ✅ **Loading time calculation** - Base time + time per tire")
    st.write("• ✅ **Google Maps integration** - Real routes and distances")
    
    st.write("\n**Optimization Logic:**")
    st.write("1. Calculates minimum vehicles needed for capacity")
    st.write("2. Tries 1, 2, then 3 vehicles if needed")
    st.write("3. Checks if routes fit within working hours")
    st.write("4. Selects solution with minimum vehicles and time")
    
    st.write(f"\n**Available Mock Addresses:** {len(mock_addresses)} locations in Houston area")
