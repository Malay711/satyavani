#!/bin/bash

set -e

echo "🚀 Setting up Voice Integrity Backend..."

# Create directories
mkdir -p data/uploads
mkdir -p monitoring
mkdir -p ml/models

# Download free datasets
echo "📥 Downloading ASVspoof 2019 dataset..."
python datasets/download_asv.py

echo "📥 Downloading WaveFake dataset..."
python datasets/download_wavefake.py

# Start services
echo "🐳 Starting Docker Compose..."
docker-compose up -d

# Wait for services
echo "⏳ Waiting for services to be ready..."
sleep 15

# Initialize database
echo "🗄️  Initializing database..."
docker-compose exec -T postgres psql -U voice_user -d voice_integrity -f /docker-entrypoint-initdb.d/init.sql

# Create demo user
echo "👤 Creating demo account..."
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@voiceintegrity.local","password":"demo123456"}'

echo "✅ Setup complete!"
echo ""
echo "🌐 Service URLs:"
echo "  API:        http://localhost:8000"
echo "  MinIO:      http://localhost:9001 (minioadmin/minioadmin123)"
echo "  Postgres:   localhost:5432"
echo "  Redis:      localhost:6379"
echo "  Prometheus: http://localhost:9090"
echo "  Grafana:    http://localhost:3000 (admin/admin123)"
echo ""
echo "📝 Demo credentials:"
echo "  Email:    demo@voiceintegrity.local"
echo "  Password: demo123456"