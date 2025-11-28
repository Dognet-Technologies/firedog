#!/bin/bash

# Test script to verify gruppo field handling in API
# Tests creation and retrieval of targets with different gruppo values

API_BASE="http://localhost:8000/api"

echo "=== Testing Gruppo Field in Target API ==="
echo ""

# Test 1: Create target with standard gruppo
echo "Test 1: Creating target with gruppo='web'"
curl -X POST "$API_BASE/targets/" \
  -H "Content-Type: application/json" \
  -d '{
    "ip_address": "192.168.100.100",
    "hostname": "test-web-server",
    "description": "Test web server",
    "gruppo": "web"
  }' 2>/dev/null | jq '.'

echo ""
echo "---"
echo ""

# Test 2: Create target with custom gruppo
echo "Test 2: Creating target with gruppo='custom' and gruppo_custom='IoT Devices'"
curl -X POST "$API_BASE/targets/" \
  -H "Content-Type: application/json" \
  -d '{
    "ip_address": "192.168.100.101",
    "hostname": "test-iot-device",
    "description": "Test IoT device",
    "gruppo": "custom",
    "gruppo_custom": "IoT Devices"
  }' 2>/dev/null | jq '.'

echo ""
echo "---"
echo ""

# Test 3: List all targets and check gruppo fields
echo "Test 3: Listing all targets to verify gruppo fields"
curl "$API_BASE/targets/" 2>/dev/null | jq '.results[] | {id, ip_address, gruppo, gruppo_custom, gruppo_display}'

echo ""
echo "---"
echo ""

# Test 4: Get detailed view of a target
echo "Test 4: Getting detailed view of last created target"
LAST_ID=$(curl "$API_BASE/targets/" 2>/dev/null | jq '.results[-1].id')
if [ "$LAST_ID" != "null" ]; then
  curl "$API_BASE/targets/$LAST_ID/" 2>/dev/null | jq '{id, ip_address, hostname, gruppo, gruppo_custom, gruppo_display}'
fi

echo ""
echo "=== Test Complete ==="
