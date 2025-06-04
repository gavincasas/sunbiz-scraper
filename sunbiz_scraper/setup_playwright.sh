#!/bin/bash

# Install Playwright and browsers
echo "Installing Playwright and browsers..."
pip install playwright==1.40.0
python -m playwright install firefox

# Create a script to ensure browsers are installed during deployment
cat > /home/ubuntu/sunbiz_scraper/install_browsers.sh << 'EOF'
#!/bin/bash
python -m playwright install firefox
EOF

# Make the script executable
chmod +x /home/ubuntu/sunbiz_scraper/install_browsers.sh

echo "Playwright and Firefox browser installed successfully."
