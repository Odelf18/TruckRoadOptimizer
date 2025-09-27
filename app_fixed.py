import os
import streamlit as st
import googlemaps
import folium
from streamlit_folium import st_folium
from ortools.constraint_solver import pywrapcp, routing_enums_pb2
from dotenv import load_dotenv

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
st.markdown("Démo simple avec adresses mock et optimisation OR-Tools")

# --- Définir le dépôt
depot_address = st.text_input("Adresse dépôt (par défaut Houston)", "Houston, TX")

# --- Input stops
st.subheader("Stops du jour")
n = st.number_input("Nombre de stops", 1, 10, 3)

stops = []
for i in range(n):
    addr = st.text_input(f"Adresse stop {i+1}", key=f"addr_{i}")
    qty = st.number_input(f"Nb pneus (stop {i+1})", 0, 500, 50, key=f"qty_{i}")
    if addr:
        stops.append({"address": addr, "qty": qty})

if st.button("Optimiser les routes 🚀") and stops:
    try:
        with st.spinner("Géocodage en cours..."):
            # Géocodage
            depot = gmaps.geocode(depot_address)[0]["geometry"]["location"]
            depot_latlon = (depot["lat"], depot["lng"])

            coords = [depot_latlon]
            for s in stops:
                g = gmaps.geocode(s["address"])
                if not g:
                    st.error(f"Adresse introuvable: {s['address']}")
                    st.stop()
                loc = g[0]["geometry"]["location"]
                s["latlon"] = (loc["lat"], loc["lng"])
                coords.append(s["latlon"])

        with st.spinner("Calcul de la matrice de distances..."):
            # Distance matrix
            origins = coords
            destinations = coords
            matrix = gmaps.distance_matrix(
                origins, destinations, mode="driving", region="us"
            )
            n_points = len(coords)
            dist_matrix = [
                [elem["duration"]["value"] // 60 for elem in row["elements"]]
                for row in matrix["rows"]
            ]

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
            st.error("Pas de solution trouvée")
        else:
            st.success("Solution trouvée ✅")

            # Récupérer la route
            index = routing.Start(0)
            plan = []
            while not routing.IsEnd(index):
                node = manager.IndexToNode(index)
                plan.append(node)
                index = solution.Value(routing.NextVar(index))
            plan.append(manager.IndexToNode(index))

            # Afficher les résultats
            st.write("Ordre des stops :")
            for idx in plan:
                if idx == 0:
                    st.write("➡️ Dépôt:", depot_address)
                else:
                    s = stops[idx-1]
                    st.write(f"➡️ Stop {idx}: {s['address']} ({s['qty']} pneus)")

            # Carte Folium
            m = folium.Map(location=depot_latlon, zoom_start=10)
            folium.Marker(depot_latlon, icon=folium.Icon(color="red"), popup="Dépôt").add_to(m)

            for i, idx in enumerate(plan):
                if idx != 0:
                    folium.Marker(
                        stops[idx-1]["latlon"],
                        popup=f"Stop {i}: {stops[idx-1]['address']} ({stops[idx-1]['qty']} pneus)",
                        icon=folium.Icon(color="blue")
                    ).add_to(m)

            # tracer polylines simplifiées
            path = [depot_latlon] + [stops[idx-1]["latlon"] for idx in plan if idx != 0] + [depot_latlon]
            folium.PolyLine(path, color="blue", weight=2.5).add_to(m)

            st_folium(m, width=800, height=500)

    except Exception as e:
        st.error(f"❌ Erreur lors de l'optimisation: {e}")
        st.write("Détails de l'erreur:", str(e))
