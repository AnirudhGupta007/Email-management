import streamlit as st
import requests
import pandas as pd

# FastAPI Backend URL
BASE_URL = "http://localhost:8000"

st.set_page_config(page_title="Email Response AI Dashboard", layout="wide")
st.title("📩 AI Email Response Assistant")

# Input Section
st.sidebar.header("Compose Email")
sender_email = st.sidebar.text_input("Your Email")  # 🔹 New Sender Email Field
subject = st.sidebar.text_input("Subject")
email_body = st.sidebar.text_area("Email Content")
tone = st.sidebar.selectbox("Select Tone", ["formal", "friendly", "apologetic"])

if st.sidebar.button("Generate Response"):
    with st.spinner("Generating AI Response..."):
        response = requests.post(f"{BASE_URL}/generate_response/", json={
            "subject": subject, 
            "email_body": email_body, 
            "tone": tone
        })
        if response.status_code == 200:
            data = response.json()
            st.session_state["email_id"] = data["email_id"]
            st.session_state["ai_response"] = data["ai_response"]
            st.success("Response Generated!")
            st.write("### AI Response:")
            st.write(data["ai_response"])
        else:
            st.error("Failed to generate response")

# Email Sending Section
if "ai_response" in st.session_state:
    st.write("### Send Email")
    recipient_email = st.text_input("Recipient Email")  # 🔹 Enter recipient's email
    if st.button("Send Email"):
        email_data = {
            "recipient_email": recipient_email,
            "subject": subject
        }
        response = requests.post(f"{BASE_URL}/send_email/", json=email_data)
        if response.status_code == 200:
            st.success("Email Sent Successfully!")
        else:
            st.error("Failed to send email")

# Feedback Section
if "email_id" in st.session_state:
    st.write("### Provide Feedback")
    rating = st.slider("Rate AI Response", 1, 5, 3)
    comment = st.text_area("Comments (Optional)")
    if st.button("Submit Feedback"):
        feedback_data = {"email_id": st.session_state["email_id"], "rating": rating, "comment": comment}
        response = requests.post(f"{BASE_URL}/submit_feedback/", json=feedback_data)
        if response.status_code == 200:
            st.success("Feedback Submitted!")
        else:
            st.error("Failed to submit feedback")

# Feedback Analytics
st.sidebar.header("Feedback Analytics")
if st.sidebar.button("Show Analytics"):
    response = requests.get(f"{BASE_URL}/feedback_stats/")
    if response.status_code == 200:
        stats = response.json()
        st.sidebar.write(f"**Average Rating:** {stats['average_rating']}")
        st.sidebar.write(f"**Total Feedback Count:** {stats['total_feedback']}")
    else:
        st.sidebar.error("Failed to retrieve analytics")
