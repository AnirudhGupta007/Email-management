import time
import logging
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from pymongo import MongoClient
from textblob import TextBlob
from langchain_huggingface import HuggingFaceEndpoint
from fastapi.responses import JSONResponse
from datetime import datetime
import certifi
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import config  

# Setup logging
logging.basicConfig(filename="app.log", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = FastAPI()

# Connect to MongoDB (Fixing SSL Certificate issue)
client = MongoClient(config.MONGO_URI, tlsCAFile=certifi.where())
db = client["email_response_db"]
collection = db["emails"]
feedback_collection = db["feedback"]  # Collection for storing feedback

# Load Hugging Face AI Model
llm = HuggingFaceEndpoint(
    repo_id="mistralai/Mistral-7B-Instruct-v0.1",
    huggingfacehub_api_token=config.HUGGINGFACE_API_KEY
)

# Define Available Tones
TONE_OPTIONS = {
    "formal": "Write a professional and well-structured response.",
    "friendly": "Write a warm, casual, and friendly response.",
    "apologetic": "Write a polite and apologetic response."
}

# Request Model
class EmailQuery(BaseModel):
    subject: str
    email_body: str
    tone: str  

class Feedback(BaseModel):
    email_id: str
    rating: int
    comment: str = ""

@app.post("/generate_response/")
def generate_response(query: EmailQuery):
    try:
        start_time = time.time()

        # Validate tone input
        tone_instruction = TONE_OPTIONS.get(query.tone.lower(), None)
        if tone_instruction is None:
            logging.warning(f"⚠️ Invalid tone received: {query.tone}, defaulting to 'formal'")
            tone_instruction = TONE_OPTIONS["formal"]

        # Perform sentiment analysis
        sentiment_score = TextBlob(query.email_body).sentiment.polarity
        sentiment = (
            "positive" if sentiment_score > 0.1 else
            "negative" if sentiment_score < -0.1 else
            "neutral"
        )

        # AI Response Generation
        prompt = f"{tone_instruction}\nEmail Content:\n{query.email_body}"
        
        try:
            ai_response = llm.invoke(prompt)
        except Exception as api_error:
            logging.error(f"❌ Hugging Face API Error: {api_error}")
            return JSONResponse(status_code=500, content={"error": "AI response generation failed. Try again later."})

        response_time = round(time.time() - start_time, 2)

        # Store Data in MongoDB with timestamp
        data = {
            "subject": query.subject,
            "email_body": query.email_body,
            "ai_response": ai_response,
            "response_time": response_time,
            "accuracy": 4,
            "sentiment": sentiment,
            "created_at": datetime.utcnow()
        }
        inserted = collection.insert_one(data)

        logging.info(f"✅ Email processed | Subject: {query.subject} | Sentiment: {sentiment} | Response Time: {response_time}s")

        return {
            "email_id": str(inserted.inserted_id),
            "ai_response": ai_response,
            "response_time": response_time,
            "accuracy": 4,
            "sentiment": sentiment
        }

    except Exception as e:
        logging.error(f"❌ Error occurred: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/submit_feedback/")
def submit_feedback(feedback: Feedback):
    """Stores user feedback for AI responses."""
    try:
        feedback_data = {
            "email_id": feedback.email_id,
            "rating": feedback.rating,
            "comment": feedback.comment,
            "submitted_at": datetime.utcnow()
        }
        feedback_collection.insert_one(feedback_data)
        logging.info(f"✅ Feedback submitted for email_id: {feedback.email_id}")
        return {"message": "Feedback submitted successfully!"}
    except Exception as e:
        logging.error(f"❌ Error storing feedback: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/feedback_stats/")
def feedback_stats():
    """Retrieves feedback analytics including average rating and total feedback count."""
    try:
        feedbacks = list(feedback_collection.find({}, {"_id": 0, "rating": 1}))
        if not feedbacks:
            return {"average_rating": 0, "total_feedback": 0}

        avg_rating = sum(f["rating"] for f in feedbacks) / len(feedbacks)
        return {"average_rating": round(avg_rating, 2), "total_feedback": len(feedbacks)}
    except Exception as e:
        logging.error(f"❌ Error fetching feedback stats: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/")
def home():
    return {"message": "FastAPI Email Response Generator is running!"}

@app.post("/send_email/")
def send_email(background_tasks: BackgroundTasks, recipient_email: str, subject: str):
    """
    Sends an email with the AI-generated response.
    """
    email_data = collection.find_one({"subject": subject}, sort=[("_id", -1)])

    if not email_data or "ai_response" not in email_data:
        return JSONResponse(status_code=404, content={"error": "No AI response found for this subject."})

    ai_response = email_data["ai_response"]
    sender_email = config.SMTP_EMAIL
    sender_password = config.SMTP_PASSWORD

    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = recipient_email
    message["Subject"] = f"Re: {subject}"
    message.attach(MIMEText(ai_response, "plain"))

    def send():
        try:
            server = smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT, timeout=10)
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipient_email, message.as_string())
            server.quit()

            collection.update_one({"subject": subject}, {"$set": {"email_sent": True, "email_sent_at": datetime.utcnow()}})
            logging.info(f"✅ Email sent successfully to {recipient_email}")
        except smtplib.SMTPException as smtp_error:
            logging.error(f"❌ Email sending failed: {str(smtp_error)}")

    background_tasks.add_task(send)
    return {"status": "Email is being sent in the background!"}


