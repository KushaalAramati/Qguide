"""Credit/billing configuration shared by the API and the Streamlit app."""

CREDITS_PER_RUN = 5        # cost of one full design run
SIGNUP_BONUS = 25          # free trial credits on account creation

CREDIT_PACKAGES = [
    {"name": "Starter", "credits": 50, "price": 9, "sub": "~10 design runs"},
    {"name": "Pro", "credits": 250, "price": 39, "sub": "~50 runs · best value", "popular": True},
    {"name": "Team", "credits": 1000, "price": 129, "sub": "~200 runs"},
]
