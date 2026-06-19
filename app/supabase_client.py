from supabase import create_client
import streamlit as st

supabase = create_client(
    st.secrets["supabase"]["url"],
    st.secrets["supabase"]["key"]
)

supabase_admin = create_client(
    st.secrets["supabase"]["url"],
    st.secrets["supabase"]["service_key_role"]
)