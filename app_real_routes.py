import os
import streamlit as st
import googlemaps
import folium
from streamlit_folium import st_folium
from ortools.constraint_solver import pywrapcp, routing_enums_pb2
from dotenv import load_dotenv
import time

# Charger les variables d'environnement
load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")

# Vérifier si la clé API est présente
if not API_KEY:
    st.error("❌ Clé API Google Maps manquante dans le fichier .env")
    st.stop()

# Initialiser le client Google Maps
try:
    gmaps = googlemaps.Client(key=API_KEY)
except Exception as e:
    st.error(f"❌ Erreur lors de l'initialisation de Google Maps: {e}")
    st.stop()

st.set_page_config(page_title="POC Route Optimizer", layout="wide")

st.title("🚚 Tire Pickup Route Optimizer (POC)")
st.markdown("**Optimisation avec vraies routes Google Maps**")

# Initialiser le session state
if 'optimization_done' not in st.session_state:
    st.session_state.optimization_done = False
if 'results' not in st.session_state:
    st.session_state.results = None

# Interface utilisateur
with st.container():
    col1, col2 = st.columns([2, 1])
    
    with col1:
        depot_address = st.text_input("Adresse dépôt", "Houston, TX")
    
    with col2:
        n = st.number_input("Nombre de stops", 1, 10, 3)

# Saisie des stops
st.subheader("📍 Stops du jour")
stops = []
for i in range(n):
    with st.container():
        col1, col2 = st.columns([3, 1])
        with col1:
            addr = st.text_input(f"Adresse stop {i+1}", key=f"addr_{i}")
        with col2:
            qty = st.number_input(f"Nb pneus", 0, 500, 50, key=f"qty_{i}")
        if addr:
            stops.append({"address": addr, "qty": qty})

# Boutons d'action
st.markdown("---")
col1, col2, col3 = st.columns([1, 1, 2])

with col1:
    optimize_clicked = st.button("🚀 Optimiser les routes", type="primary", use_container_width=True)

with col2:
    reset_clicked = st.button("🔄 Nouvelle optimisation", use_container_width=True)

with col3:
    st.write("")  # Espace vide

# Logique d'optimisation
if optimize_clicked and stops:
    st.session_state.optimization_done = True
    
    try:
        # Géocodage avec Google Maps
        with st.spinner("🗺️ Géocodage des adresses..."):
            # Géocoder le dépôt
            depot_geocode = gmaps.geocode(depot_address)
            if not depot_geocode:
                st.error(f"❌ Adresse dépôt introuvable: {depot_address}")
                st.stop()
            
            depot_latlon = (
                depot_geocode[0]["geometry"]["location"]["lat"],
                depot_geocode[0]["geometry"]["location"]["lng"]
            )
            
            # Géocoder les stops
            coords = [depot_latlon]
            for i, s in enumerate(stops):
                geocode_result = gmaps.geocode(s["address"])
                if not geocode_result:
                    st.error(f"❌ Adresse introuvable: {s['address']}")
                    st.stop()
                
                lat = geocode_result[0]["geometry"]["location"]["lat"]
                lng = geocode_result[0]["geometry"]["location"]["lng"]
                s["latlon"] = (lat, lng)
                coords.append(s["latlon"])
                
                # Petite pause pour éviter de dépasser les limites de l'API
                time.sleep(0.1)

        # Matrice de distances avec Google Maps
        with st.spinner("📊 Calcul de la matrice de distances..."):
            origins = coords
            destinations = coords
            
            # Utiliser l'API Distance Matrix de Google
            matrix_result = gmaps.distance_matrix(
                origins=origins,
                destinations=destinations,
                mode="driving",
                units="metric",
                region="us"
            )
            
            # Extraire les distances en minutes
            n_points = len(coords)
            dist_matrix = []
            for i, row in enumerate(matrix_result["rows"]):
                dist_row = []
                for j, element in enumerate(row["elements"]):
                    if element["status"] == "OK":
                        # Utiliser la durée en minutes
                        duration_minutes = element["duration"]["value"] // 60
                        dist_row.append(duration_minutes)
                    else:
                        # Si pas de route trouvée, utiliser une grande valeur
                        dist_row.append(9999)
                dist_matrix.append(dist_row)

        # Optimisation OR-Tools
        with st.spinner("🧮 Optimisation en cours..."):
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
            # Récupérer la route optimisée
            index = routing.Start(0)
            plan = []
            while not routing.IsEnd(index):
                node = manager.IndexToNode(index)
                plan.append(node)
                index = solution.Value(routing.NextVar(index))
            plan.append(manager.IndexToNode(index))

            # Obtenir les vraies routes avec Google Directions API
            with st.spinner("🛣️ Calcul des routes détaillées..."):
                route_coords = []
                route_polylines = []
                
                for i in range(len(plan) - 1):
                    start_idx = plan[i]
                    end_idx = plan[i + 1]
                    
                    start_coord = coords[start_idx]
                    end_coord = coords[end_idx]
                    
                    # Obtenir la route détaillée
                    directions_result = gmaps.directions(
                        origin=start_coord,
                        destination=end_coord,
                        mode="driving",
                        avoid=["tolls", "ferries"]
                    )
                    
                    if directions_result:
                        # Extraire les points de la polyline
                        polyline = directions_result[0]["overview_polyline"]["points"]
                        route_polylines.append(polyline)
                        
                        # Décoder la polyline pour obtenir les coordonnées
                        import polyline as pl
                        decoded_coords = pl.decode(polyline)
                        route_coords.extend(decoded_coords)
                        
                        # Petite pause pour éviter de dépasser les limites de l'API
                        time.sleep(0.1)

            # Sauvegarder les résultats
            st.session_state.results = {
                'plan': plan,
                'stops': stops,
                'depot_address': depot_address,
                'depot_latlon': depot_latlon,
                'dist_matrix': dist_matrix,
                'coords': coords,
                'route_coords': route_coords,
                'route_polylines': route_polylines
            }
            
            st.success("✅ Route optimisée trouvée avec les vraies routes Google Maps !")
        else:
            st.error("❌ Aucune solution trouvée")

    except Exception as e:
        st.error(f"❌ Erreur lors de l'optimisation: {e}")
        st.write("Détails de l'erreur:", str(e))

# Reset
if reset_clicked:
    st.session_state.optimization_done = False
    st.session_state.results = None
    st.rerun()

# Affichage des résultats
if st.session_state.results and st.session_state.optimization_done:
    results = st.session_state.results
    plan = results['plan']
    stops = results['stops']
    depot_address = results['depot_address']
    depot_latlon = results['depot_latlon']
    dist_matrix = results['dist_matrix']
    coords = results['coords']
    route_coords = results.get('route_coords', [])
    route_polylines = results.get('route_polylines', [])

    # Résultats textuels
    st.subheader("📋 Ordre des stops optimisé")
    total_time = 0
    
    for i, idx in enumerate(plan):
        if idx == 0:
            st.write(f"🏢 **Dépôt:** {depot_address}")
        else:
            s = stops[idx-1]
            st.write(f"📍 **Stop {i}:** {s['address']} ({s['qty']} pneus)")
            if i > 0:
                prev_idx = plan[i-1]
                time_min = dist_matrix[prev_idx][idx]
                total_time += time_min
                st.write(f"   ⏱️ Temps depuis le stop précédent: {time_min} minutes")

    st.write(f"📊 **Temps total de route:** {total_time} minutes")
    st.write(f"📦 **Total pneus à collecter:** {sum(s['qty'] for s in stops)}")

    # Carte interactive avec vraies routes
    st.subheader("🗺️ Carte avec vraies routes Google Maps")
    
    # Créer la carte
    m = folium.Map(
        location=depot_latlon, 
        zoom_start=12,
        tiles='OpenStreetMap'
    )
    
    # Marqueur du dépôt
    folium.Marker(
        depot_latlon, 
        icon=folium.Icon(color="red", icon="warehouse", prefix="fa"), 
        popup="🏢 Dépôt"
    ).add_to(m)
    
    # Marqueurs des stops
    for i, idx in enumerate(plan):
        if idx != 0:
            s = stops[idx-1]
            folium.Marker(
                s["latlon"],
                popup=f"📍 Stop {i}<br>{s['address']}<br>📦 {s['qty']} pneus",
                icon=folium.Icon(color="blue", icon="truck", prefix="fa")
            ).add_to(m)
    
    # Tracer les vraies routes
    if route_coords:
        # Utiliser les coordonnées décodées de Google
        folium.PolyLine(
            route_coords, 
            color="red", 
            weight=4, 
            opacity=0.8,
            popup="Route optimisée (Google Maps)"
        ).add_to(m)
    else:
        # Fallback: ligne droite si pas de routes détaillées
        route_coords = [coords[idx] for idx in plan] + [coords[0]]
        folium.PolyLine(
            route_coords, 
            color="red", 
            weight=4, 
            opacity=0.8,
            popup="Route optimisée"
        ).add_to(m)
    
    # Afficher la carte
    st_folium(m, width=900, height=600)

# Section d'aide
with st.expander("ℹ️ Aide"):
    st.write("**Cette version utilise:**")
    st.write("• ✅ **API Google Maps** pour le géocodage")
    st.write("• ✅ **Distance Matrix API** pour les vraies distances")
    st.write("• ✅ **Directions API** pour les vraies routes")
    st.write("• ✅ **OR-Tools** pour l'optimisation")
    
    st.write("\n**Comment utiliser:**")
    st.write("1. Saisissez les vraies adresses des stops")
    st.write("2. Cliquez sur 'Optimiser les routes'")
    st.write("3. L'application va géocoder et calculer les vraies routes")
    st.write("4. Consultez la route optimisée sur la carte")
