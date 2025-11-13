#!/bin/bash

# Simple startup script for the Equity Research application

echo "🚀 Starting Equity Research Application..."
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "⚠️  Virtual environment not found. Creating one..."
    python -m venv venv
    echo "✅ Virtual environment created"
fi

# Activate virtual environment
echo "📦 Activating virtual environment..."
source venv/bin/activate

# Install/update dependencies
echo "📥 Installing dependencies..."
pip install -q -r requirements.txt

# Create data directory if it doesn't exist
mkdir -p data

# Run Streamlit
echo ""
echo "✨ Launching Streamlit application..."
echo "   Navigate to: http://localhost:8501"
echo ""
streamlit run app.py
