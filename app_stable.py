import streamlit as st
import folium
from streamlit_folium import st_folium
from ortools.constraint_solver import pywrapcp, routing_enums_pb2
import math
import random

st.set_page_config(page_title="POC Route Optimizer", layout="wide")

st.title("🚚 Tire Pickup Route Optimizer (POC)")
st.markdown("Démo simple avec adresses mock et optimisation OR-Tools")

# Adresses mock pour Houston
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

# --- Définir le dépôt
depot_address = st.text_input("Adresse dépôt", "Houston, TX")

# --- Input stops
st.subheader("Stops du jour")
n = st.number_input("Nombre de stops", 1, 10, 3)

stops = []
for i in range(n):
    col1, col2 = st.columns([3, 1])
    with col1:
        addr = st.text_input(f"Adresse stop {i+1}", key=f"addr_{i}")
    with col2:
        qty = st.number_input(f"Nb pneus", 0, 500, 50, key=f"qty_{i}")
    if addr:
        stops.append({"address": addr, "qty": qty})

# Boutons
col1, col2 = st.columns(2)
with col1:
    if st.button("🚀 Optimiser les routes", type="primary"):
        if stops:
            st.session_state.optimization_done = True
            st.rerun()

with col2:
    if st.button("🔄 Nouvelle optimisation"):
        st.session_state.optimization_done = False
        st.session_state.results = None
        st.rerun()

# Afficher les résultats si l'optimisation est faite
if st.session_state.optimization_done and stops:
    try:
        with st.spinner("Géocodage en cours..."):
            # Utiliser les coordonnées mock
            if depot_address in MOCK_ADDRESSES:
                depot_latlon = MOCK_ADDRESSES[depot_address]
            else:
                depot_latlon = MOCK_ADDRESSES["Houston, TX"]  # Fallback
            
            coords = [depot_latlon]
            for s in stops:
                if s["address"] in MOCK_ADDRESSES:
                    s["latlon"] = MOCK_ADDRESSES[s["address"]]
                else:
                    # Générer des coordonnées aléatoires autour de Houston
                    lat = 29.7604 + random.uniform(-0.01, 0.01)
                    lng = -95.3698 + random.uniform(-0.01, 0.01)
                    s["latlon"] = (lat, lng)
                coords.append(s["latlon"])

        with st.spinner("Calcul de la matrice de distances..."):
            # Matrice de distances mock (en minutes)
            n_points = len(coords)
            dist_matrix = []
            for i in range(n_points):
                row = []
                for j in range(n_points):
                    if i == j:
                        row.append(0)
                    else:
                        # Distance mock basée sur la distance géographique
                        lat1, lng1 = coords[i]
                        lat2, lng2 = coords[j]
                        distance = math.sqrt((lat1-lat2)**2 + (lng1-lng2)**2) * 1000  # Approximation
                        row.append(int(distance))
                dist_matrix.append(row)

        with st.spinner("Optimisation en cours..."):
            # OR-Tools VRP (1 camion par défaut pour POC)
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

        if not solution:
            st.error("❌ Pas de solution trouvée")
        else:
            st.success("✅ Solution trouvée !")

            # Récupérer la route
            index = routing.Start(0)
            plan = []
            while not routing.IsEnd(index):
                node = manager.IndexToNode(index)
                plan.append(node)
                index = solution.Value(routing.NextVar(index))
            plan.append(manager.IndexToNode(index))

            # Sauvegarder les résultats dans session state
            st.session_state.results = {
                'plan': plan,
                'stops': stops,
                'depot_address': depot_address,
                'depot_latlon': depot_latlon,
                'dist_matrix': dist_matrix
            }

    except Exception as e:
        st.error(f"❌ Erreur lors de l'optimisation: {e}")
        st.write("Détails de l'erreur:", str(e))

# Afficher les résultats sauvegardés
if st.session_state.results:
    results = st.session_state.results
    plan = results['plan']
    stops = results['stops']
    depot_address = results['depot_address']
    depot_latlon = results['depot_latlon']
    dist_matrix = results['dist_matrix']

    st.subheader("📋 Ordre des stops optimisé :")
    total_distance = 0
    for i, idx in enumerate(plan):
        if idx == 0:
            st.write(f"🏢 **Dépôt:** {depot_address}")
        else:
            s = stops[idx-1]
            st.write(f"📍 **Stop {i}:** {s['address']} ({s['qty']} pneus)")
            if i > 0:
                prev_idx = plan[i-1]
                distance = dist_matrix[prev_idx][idx]
                total_distance += distance
                st.write(f"   ⏱️ Distance depuis le stop précédent: {distance} minutes")

    st.write(f"📊 **Distance totale:** {total_distance} minutes")

    # Carte Folium
    st.subheader("🗺️ Carte de la route optimisée")
    m = folium.Map(location=depot_latlon, zoom_start=11)
    
    # Marqueur du dépôt
    folium.Marker(
        depot_latlon, 
        icon=folium.Icon(color="red", icon="warehouse"), 
        popup="🏢 Dépôt"
    ).add_to(m)

    # Marqueurs des stops
    for i, idx in enumerate(plan):
        if idx != 0:
            s = stops[idx-1]
            folium.Marker(
                s["latlon"],
                popup=f"📍 Stop {i}: {s['address']}<br>📦 {s['qty']} pneus",
                icon=folium.Icon(color="blue", icon="truck")
            ).add_to(m)

    # Tracer la route optimisée
    path = [depot_latlon] + [stops[idx-1]["latlon"] for idx in plan if idx != 0] + [depot_latlon]
    folium.PolyLine(
        path, 
        color="red", 
        weight=3, 
        opacity=0.8,
        popup="Route optimisée"
    ).add_to(m)

    st_folium(m, width=800, height=500)

# Section d'aide
with st.expander("ℹ️ Aide - Adresses mock disponibles"):
    st.write("**Adresses prédéfinies pour les tests :**")
    for addr, coords in MOCK_ADDRESSES.items():
        st.write(f"• {addr} - {coords}")
    
    st.write("\n**Comment utiliser :**")
    st.write("1. Tapez une adresse dans les champs")
    st.write("2. Si l'adresse n'est pas reconnue, des coordonnées aléatoires seront générées")
    st.write("3. Cliquez sur 'Optimiser les routes' pour voir la solution")
    st.write("4. Les résultats restent affichés jusqu'à la prochaine optimisation")
