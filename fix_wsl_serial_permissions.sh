#!/bin/bash
# Script to fix serial port permissions on WSL

echo "Fixing serial port permissions for WSL..."
echo ""

# Check if user is in dialout group
if groups $USER | grep -q '\bdialout\b'; then
    echo "User $USER is already in the dialout group."
else
    echo "Adding user $USER to the dialout group..."
    sudo usermod -a -G dialout $USER
    echo "User added to dialout group."
    echo ""
    echo "IMPORTANT: You need to log out and log back in for the changes to take effect."
    echo "Or run: newgrp dialout"
fi

echo ""
echo "Testing serial port access..."

# Try to access common COM ports
for i in 3 7; do
    if [ -e "/dev/ttyS$i" ]; then
        echo -n "Testing /dev/ttyS$i (COM$i): "
        if [ -r "/dev/ttyS$i" ] && [ -w "/dev/ttyS$i" ]; then
            echo "Accessible"
        else
            echo "Not accessible (permission denied)"
        fi
    fi
done

echo ""
echo "If ports are still not accessible, try:"
echo "1. Log out and log back in"
echo "2. Run: newgrp dialout"
echo "3. Restart your WSL instance"