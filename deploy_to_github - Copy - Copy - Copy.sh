#!/bin/bash

# Mo Solar Technologies - GitHub Deployment Script
# Repository: ioproxxy/Itara

echo "🚀 Starting GitHub deployment for Mo Solar Technologies..."

# Check if git is initialized
if [ ! -d ".git" ]; then
    echo "📦 Initializing Git repository..."
    git init
else
    echo "✅ Git repository already exists"
fi

# Remove any existing remote origin
echo "🔄 Removing existing remote origin (if any)..."
git remote remove origin 2>/dev/null || true

# Add remote origin for ioproxxy/Itara
echo "🔗 Adding remote origin: https://github.com/ioproxxy/Itara.git"
git remote add origin https://github.com/ioproxxy/Itara.git

# Add all files
echo "📁 Adding all files to git..."
git add .

# Commit changes
echo "💾 Committing changes..."
git commit -m "Mo Solar Technologies e-commerce platform

- Complete Flask application with PostgreSQL database
- Product catalog with real solar products
- Shopping cart and checkout functionality
- Local payment methods (M-Pesa, Credit Cards)
- User authentication and admin features
- Responsive design with Tailwind CSS"

# Set main branch and push
echo "⬆️ Pushing to GitHub..."
git branch -M main
git push -u origin main

echo "✅ Deployment complete!"
echo "🌐 Your repository is now available at: https://github.com/ioproxxy/Itara"
echo "📖 Check the README.md for deployment instructions"