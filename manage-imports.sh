#!/bin/bash

# GödelOS Import Management Script
# Provides easy CLI access to import management endpoints

API_BASE="http://localhost:8000"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_usage() {
    echo -e "${BLUE}🧠 GödelOS Import Management${NC}"
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  active      - List all active imports"
    echo "  cancel <id> - Cancel specific import by ID"
    echo "  cancel-all  - Cancel all active imports"
    echo "  reset-stuck - Reset stuck imports (processing >15min)"
    echo "  kill-all    - Emergency: Cancel all + reset stuck"
    echo "  status      - Show import system status"
    echo ""
    echo "Examples:"
    echo "  $0 active"
    echo "  $0 cancel import_123"
    echo "  $0 cancel-all"
    echo "  $0 kill-all"
}

check_server() {
    if ! curl -s "${API_BASE}/health" > /dev/null 2>&1; then
        echo -e "${RED}❌ Server not responding at ${API_BASE}${NC}"
        echo "Make sure the backend server is running with: ./start-godelos.sh --dev"
        exit 1
    fi
}

get_active_imports() {
    echo -e "${BLUE}📋 Getting active imports...${NC}"
    response=$(curl -s "${API_BASE}/api/knowledge/import/active")
    if [[ $? -eq 0 ]]; then
        echo "$response" | jq -r '.active_imports[] | "ID: \(.import_id) | Status: \(.status) | File: \(.filename) | Progress: \(.progress)%"' 2>/dev/null || echo "$response"
        total=$(echo "$response" | jq -r '.total_count' 2>/dev/null || echo "?")
        echo -e "${GREEN}Total active imports: ${total}${NC}"
    else
        echo -e "${RED}❌ Failed to get active imports${NC}"
    fi
}

cancel_import() {
    local import_id="$1"
    if [[ -z "$import_id" ]]; then
        echo -e "${RED}❌ Import ID required${NC}"
        echo "Usage: $0 cancel <import_id>"
        exit 1
    fi
    
    echo -e "${YELLOW}🛑 Cancelling import: ${import_id}${NC}"
    response=$(curl -s -X DELETE "${API_BASE}/api/knowledge/import/${import_id}")
    
    if [[ $? -eq 0 ]]; then
        status=$(echo "$response" | jq -r '.status' 2>/dev/null)
        if [[ "$status" == "cancelled" ]]; then
            echo -e "${GREEN}✅ Import cancelled successfully${NC}"
        else
            echo -e "${YELLOW}⚠️ Import not found or already completed${NC}"
        fi
        echo "$response" | jq . 2>/dev/null || echo "$response"
    else
        echo -e "${RED}❌ Failed to cancel import${NC}"
    fi
}

cancel_all_imports() {
    echo -e "${YELLOW}🛑 Cancelling ALL active imports...${NC}"
    response=$(curl -s -X DELETE "${API_BASE}/api/knowledge/import/all")
    
    if [[ $? -eq 0 ]]; then
        cancelled=$(echo "$response" | jq -r '.cancelled_count' 2>/dev/null || echo "?")
        echo -e "${GREEN}✅ Cancelled ${cancelled} imports${NC}"
        echo "$response" | jq . 2>/dev/null || echo "$response"
    else
        echo -e "${RED}❌ Failed to cancel all imports${NC}"
    fi
}

reset_stuck_imports() {
    echo -e "${YELLOW}🔄 Resetting stuck imports...${NC}"
    response=$(curl -s -X DELETE "${API_BASE}/api/knowledge/import/stuck")
    
    if [[ $? -eq 0 ]]; then
        reset_count=$(echo "$response" | jq -r '.reset_count' 2>/dev/null || echo "?")
        echo -e "${GREEN}✅ Reset ${reset_count} stuck imports${NC}"
        echo "$response" | jq . 2>/dev/null || echo "$response"
    else
        echo -e "${RED}❌ Failed to reset stuck imports${NC}"
    fi
}

kill_all() {
    echo -e "${RED}🚨 EMERGENCY: Killing all imports and resetting stuck ones...${NC}"
    
    # First cancel all
    echo -e "${YELLOW}Step 1: Cancelling all active imports...${NC}"
    cancel_all_imports
    
    echo ""
    
    # Then reset stuck
    echo -e "${YELLOW}Step 2: Resetting stuck imports...${NC}"
    reset_stuck_imports
    
    echo ""
    echo -e "${GREEN}✅ Emergency import cleanup complete${NC}"
    
    # Show final status
    echo ""
    get_active_imports
}

show_status() {
    echo -e "${BLUE}📊 Import System Status${NC}"
    echo "=================================="
    
    # Check server health
    echo -n "Server Status: "
    if curl -s "${API_BASE}/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Online${NC}"
    else
        echo -e "${RED}❌ Offline${NC}"
        return 1
    fi
    
    echo ""
    
    # Get active imports
    get_active_imports
}

# Main command processing
case "$1" in
    "active"|"list")
        check_server
        get_active_imports
        ;;
    "cancel")
        check_server
        cancel_import "$2"
        ;;
    "cancel-all")
        check_server
        cancel_all_imports
        ;;
    "reset-stuck")
        check_server
        reset_stuck_imports
        ;;
    "kill-all"|"emergency")
        check_server
        kill_all
        ;;
    "status")
        show_status
        ;;
    "")
        print_usage
        ;;
    *)
        echo -e "${RED}❌ Unknown command: $1${NC}"
        echo ""
        print_usage
        exit 1
        ;;
esac
