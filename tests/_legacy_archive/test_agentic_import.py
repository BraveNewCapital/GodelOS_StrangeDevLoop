#!/usr/bin/env python3

import sys
sys.path.insert(0, '.')

try:
    from backend.api.agentic_daemon_endpoints import router
    print('✅ Agentic daemon endpoints imported successfully')
    print(f'Number of routes: {len(router.routes)}')
    print(f'Router tags: {router.tags}')
    
    # Test specific endpoints
    route_paths = [route.path for route in router.routes]
    print(f'Available endpoints: {len(route_paths)}')
    print('Sample endpoints:')
    for path in route_paths[:5]:
        print(f'  - {path}')
        
except Exception as e:
    print(f'❌ Import failed: {e}')
    import traceback
    traceback.print_exc()
