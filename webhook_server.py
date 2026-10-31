# webhook_server.py
from fastapi import FastAPI, Request, HTTPException
import stripe
import os
from database import init_db, add_pro_user

app = FastAPI()
init_db()

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
endpoint_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")

@app.post("/stripe-webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        customer_email = (
            session.get("customer_details", {}).get("email") 
            or session.get("customer_email")
        )
        if customer_email:
            add_pro_user(customer_email)
            print(f"Pro-Zugang freigeschaltet für: {customer_email}")

    return {"status": "success"}
