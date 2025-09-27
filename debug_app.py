import streamlit as st

st.set_page_config(page_title="Debug App", layout="wide")

st.title("🔍 Debug Application")

st.write("Cette page devrait rester visible...")

# Test simple
name = st.text_input("Votre nom", "Test")
st.write(f"Bonjour {name} !")

if st.button("Test Button"):
    st.success("Bouton cliqué !")

st.write("Si vous voyez ceci, l'app fonctionne correctement.")
