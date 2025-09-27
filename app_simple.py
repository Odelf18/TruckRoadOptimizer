import streamlit as st
import folium
from streamlit_folium import st_folium

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
    st.success("Simulation d'optimisation (sans API Google Maps)")
    
    # Coordonnées mock pour Houston
    depot_latlon = (29.7604, -95.3698)  # Houston, TX
    
    # Coordonnées mock pour les stops
    mock_coords = [
        (29.7604, -95.3698),  # Houston centre
        (29.7589, -95.3598),  # Stop 1
        (29.7619, -95.3798),  # Stop 2
        (29.7629, -95.3498),  # Stop 3
    ]
    
    # Afficher les résultats
    st.write("Ordre des stops (simulation) :")
    st.write("➡️ Dépôt:", depot_address)
    for i, s in enumerate(stops):
        st.write(f"➡️ Stop {i+1}: {s['address']} ({s['qty']} pneus)")

    # Carte Folium
    m = folium.Map(location=depot_latlon, zoom_start=10)
    folium.Marker(depot_latlon, icon=folium.Icon(color="red"), popup="Dépôt").add_to(m)

    for i, s in enumerate(stops):
        if i < len(mock_coords) - 1:
            folium.Marker(
                mock_coords[i+1],
                popup=f"Stop {i+1}: {s['address']} ({s['qty']} pneus)",
                icon=folium.Icon(color="blue")
            ).add_to(m)

    # tracer polylines simplifiées
    path = [depot_latlon] + mock_coords[1:len(stops)+1] + [depot_latlon]
    folium.PolyLine(path, color="blue", weight=2.5).add_to(m)

    st_folium(m, width=800, height=500)
