#!/bin/bash
echo "Installing dependencies..."
pip install flask reportlab pillow --break-system-packages -q
echo ""
echo "Starting HR Management System..."
echo "Open: http://localhost:5000"
echo "Login: admin / admin123"
python app.py
