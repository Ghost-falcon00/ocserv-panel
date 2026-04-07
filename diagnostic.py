import asyncio
import socket

COMMON_SUBDOMAINS = [
    "", "www", "api", "graph", "mqtt", "chat", "edge-chat", "edge", 
    "b.i", "i", "scontent", "cdn", "m", "developer"
]

async def resolve_domain(domain):
    ips = set()
    loop = asyncio.get_event_loop()
    try:
        info = await loop.run_in_executor(None, socket.getaddrinfo, domain, None)
        for item in info:
            ips.add(item[4][0])
    except Exception as e:
        print(f"Failed to resolve {domain}: {e}")
    return ips

async def test_instagram():
    root_domain = "instagram.com"
    target_ips = set()
    print(f"Starting resolution for: {root_domain}")
    
    for sub in COMMON_SUBDOMAINS:
        target = f"{sub}.{root_domain}" if sub else root_domain
        print(f"Resolving: {target}...")
        resolved = await resolve_domain(target)
        if resolved:
            print(f" => Found: {resolved}")
        target_ips.update(resolved)
        
    print(f"\nTotal IPs found: {len(target_ips)}")

if __name__ == "__main__":
    asyncio.run(test_instagram())
