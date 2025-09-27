import streamlit as st
import folium
from streamlit_folium import st_folium
from ortools.constraint_solver import pywrapcp, routing_enums_pb2
import math
import random

# Configuration de la page
st.set_page_config(
    page_title="POC Route Optimizer", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS pour éviter les rechargements
st.markdown("""
<style>
    .stApp {
        max-width: 100%;
    }
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

st.title("🚚 Tire Pickup Route Optimizer (POC)")
st.markdown("Démo simple avec adresses mock et optimisation OR-Tools")

# Adresses mock pour Houston avec coordonnées réalistes
MOCK_ADDRESSES = {
    "Houston, TX": (29.7604, -95.3698),
    "3721 Mt Pleasant St, Houston, TX 77021, USA": (29.7604, -95.3698),
    "253 Van Molan St, Houston, TX 77022, USA": (29.7589, -95.3598),
    "26410 Cottage Cypress Ln, Cypress, TX 77433, USA": (29.7619, -95.3798),
    "3906 Artdale St, Houston, TX 77063, USA": (29.7629, -95.3498),
    "1234 Main St, Houston, TX": (29.7639, -95.3398),
    "5678 Oak Ave, Houston, TX": (29.7649, -95.3298),
    "9012 Pine St, Houston, TX": (29.7659, -95.3198),
    "3456 Elm St, Houston, TX": (29.7669, -95.3098),
    "7890 Maple Dr, Houston, TX": (29.7679, -95.2998),
}

# Initialiser le session state
if 'optimization_done' not in st.session_state:
    st.session_state.optimization_done = False
if 'results' not in st.session_state:
    st.session_state.results = None
if 'stops_data' not in st.session_state:
    st.session_state.stops_data = []

# Fonction pour calculer la distance entre deux points
def calculate_distance(lat1, lon1, lat2, lon2):
    """Calcule la distance en kilomètres entre deux points GPS"""
    R = 6371  # Rayon de la Terre en km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2) * math.sin(dlat/2) + 
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
         math.sin(dlon/2) * math.sin(dlon/2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

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
    st.session_state.stops_data = stops.copy()
    
    try:
        # Géocodage
        if depot_address in MOCK_ADDRESSES:
            depot_latlon = MOCK_ADDRESSES[depot_address]
        else:
            depot_latlon = MOCK_ADDRESSES["Houston, TX"]
        
        coords = [depot_latlon]
        for s in stops:
            if s["address"] in MOCK_ADDRESSES:
                s["latlon"] = MOCK_ADDRESSES[s["address"]]
            else:
                # Coordonnées aléatoires autour de Houston
                lat = 29.7604 + random.uniform(-0.02, 0.02)
                lng = -95.3698 + random.uniform(-0.02, 0.02)
                s["latlon"] = (lat, lng)
            coords.append(s["latlon"])

        # Matrice de distances réaliste
        n_points = len(coords)
        dist_matrix = []
        for i in range(n_points):
            row = []
            for j in range(n_points):
                if i == j:
                    row.append(0)
                else:
                    lat1, lng1 = coords[i]
                    lat2, lng2 = coords[j]
                    distance_km = calculate_distance(lat1, lng1, lat2, lng2)
                    # Convertir en minutes (vitesse moyenne 30 km/h en ville)
                    time_minutes = int(distance_km * 2)
                    row.append(time_minutes)
            dist_matrix.append(row)

        # Optimisation OR-Tools
        manager = pywrapcp.RoutingIndexManager(n_points, 1, 0)
        routing = pywrapcp.RoutingModel(manager)

        def distance_callback(from_index, to_index):
            return dist_matrix[manager.IndexToNode(from_index)][manager.IndexToNode(to_index)]

        transit_cb = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_cb)

        search_params = pywrapcp.DefaultRoutingSearchParameters()
        search_params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        search_params.time_limit.FromSeconds(5)

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

            # Sauvegarder les résultats
            st.session_state.results = {
                'plan': plan,
                'stops': stops,
                'depot_address': depot_address,
                'depot_latlon': depot_latlon,
                'dist_matrix': dist_matrix,
                'coords': coords
            }
        else:
            st.error("❌ Aucune solution trouvée")

    except Exception as e:
        st.error(f"❌ Erreur: {e}")

# Reset
if reset_clicked:
    st.session_state.optimization_done = False
    st.session_state.results = None
    st.session_state.stops_data = []
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

    st.success("✅ Route optimisée trouvée !")
    
    # Résultats textuels
    st.subheader("📋 Ordre des stops optimisé")
    total_distance = 0
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

    # Carte interactive
    st.subheader("🗺️ Carte de la route optimisée")
    
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
    
    # Tracer la route optimisée
    route_coords = [coords[idx] for idx in plan] + [coords[0]]  # Retour au dépôt
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
    st.write("**Adresses prédéfinies:**")
    for addr in list(MOCK_ADDRESSES.keys())[:5]:
        st.write(f"• {addr}")
    st.write("... et 5 autres adresses aléatoires autour de Houston")
    
    st.write("\n**Comment utiliser:**")
    st.write("1. Saisissez les adresses des stops")
    st.write("2. Cliquez sur 'Optimiser les routes'")
    st.write("3. Consultez la route optimisée sur la carte")
    st.write("4. Cliquez sur 'Nouvelle optimisation' pour recommencer")
