import streamlit as st

st.set_page_config(page_title="Test App", layout="wide")

st.title("🚚 Test Application")
st.write("Si vous voyez ceci, Streamlit fonctionne !")

st.subheader("Test des inputs")
name = st.text_input("Votre nom", "Test")
st.write(f"Bonjour {name} !")

if st.button("Cliquer ici"):
    st.success("Le bouton fonctionne !")
