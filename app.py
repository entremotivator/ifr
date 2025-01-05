import streamlit as st
import requests
import base64

# Configuration
N8N_DOMAIN = "agentonline-u29564.vm.elestio.app"
N8N_AUTH_USER = "root"
N8N_AUTH_PASSWORD = "8QRlr4ex-IomJ-4njKSVSX"

# Encode authentication details in Base64 for Basic Auth
auth_header = base64.b64encode(f"{N8N_AUTH_USER}:{N8N_AUTH_PASSWORD}".encode()).decode()

# Function to test connection to n8n
def test_n8n_connection():
    url = f"https://{N8N_DOMAIN}/healthz"
    headers = {"Authorization": f"Basic {auth_header}"}
    try:
        response = requests.get(url, headers=headers, verify=False)
        if response.status_code == 200:
            return True
        else:
            st.error(f"Error connecting to n8n: {response.status_code}")
            return False
    except Exception as e:
        st.error(f"Connection failed: {e}")
        return False

# Streamlit App
st.set_page_config(page_title="n8n Integration", layout="wide")
st.title("n8n Integration with Full Authentication")

# Test connection
if test_n8n_connection():
    st.success("Connected to n8n successfully!")
    # Embed n8n interface in iframe
    st.markdown(
        f"""
        <iframe src="https://{N8N_DOMAIN}" width="100%" height="800px" frameborder="0"></iframe>
        """,
        unsafe_allow_html=True
    )
else:
    st.error("Could not connect to n8n. Please check your credentials or n8n instance.")

# Note for security
st.info("Ensure the n8n instance is properly secured and only accessible to authorized users.")
