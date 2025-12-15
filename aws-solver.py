# Aws Waf Solver For injecting Bot
import time
import sys
import os
import certifi
import ssl
ssl._create_default_https_context = ssl._create_unverified_context

# Add the awswaf/python directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'awswaf', 'python'))

from awswaf.aws import AwsWaf
from curl_cffi import requests
from concurrent.futures import ThreadPoolExecutor

def solve():
    session = requests.Session(impersonate="chrome")

    session.headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'accept-language': 'en-US,en;q=0.5',
        'cache-control': 'no-cache',
        #'dnt': '1',
        'pragma': 'no-cache',
        'priority': 'u=0, i',
        'sec-ch-ua': '"Chromium";v="136", "Brave";v="136", "Not.A/Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'sec-fetch-user': '?1',
        'sec-gpc': '1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
    }
    
    # Try multiple websites that commonly use AWS WAF
    test_urls = [
        "https://www.binance.com/",
        "https://www.hiltongarage.co.uk/",
        "https://www.cloudflare.com/",
        "https://www.akamai.com/",
        "https://en.fofa.info/result?qbase64=ImN3cHNydiI%3D"
    ]
    
    for url in test_urls:
        print(f"\n[*] Testing {url} for AWS WAF protection...")
        
        try:
            response = session.get(url, timeout=10)
            print("[*] Headers:", dict(response.headers))
            print(f"[*] Status code: {response.status_code}")
            print(f"[*] Response length: {len(response.text)} characters")
            
            # Check if the response contains AWS WAF challenge
            if "window.gokuProps" in response.text:
                print(f"[+] Found AWS WAF challenge on {url}")
                
                try:
                    goku, host = AwsWaf.extract(response.text)
                    print(f"[+] Extracted WAF parameters from {host}")
                    
                    start = time.time()
                    token = AwsWaf(goku, host, url.split("//")[1].split("/")[0])()
                    end = time.time()

                    session.headers.update({
                        "cookie": "aws-waf-token=" + token
                    })
                    
                    # Test if the token works
                    test_response = session.get(url)
                    solved = len(test_response.text) > 20000
                    
                    if solved:
                        print(f"[+] Successfully solved WAF challenge!")
                        print(f"[+] Token: {token}")
                        print(f"[+] Time taken: {end - start:.2f}s")
                        return
                    else:
                        print(f"[!] Token didn't work, response length: {len(test_response.text)}")
                        
                except (IndexError, KeyError) as e:
                    print(f"[!] Failed to extract WAF parameters: {e}")
                    continue
            else:
                print(f"[!] No AWS WAF protection detected")
                
        except Exception as e:
            print(f"[!] Error testing {url}: {e}")
            continue
    
    print("\n[!] No working AWS WAF challenges found on any tested websites")


if __name__ == "__main__":
    solve()
    