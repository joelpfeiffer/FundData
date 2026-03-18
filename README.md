# Zwitserleven Funds Full Project

## Install
pip install -r requirements.txt

## Run pipeline
python pipeline/runner.py

## Run dashboard
streamlit run app/dashboard.py

## Run API
uvicorn api.api:app --reload
