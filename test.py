from curl_cffi import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime

def test_crous():
    """Test CROUS API and return results"""
    API_URL = "https://trouverunlogement.lescrous.fr/api/fr/search/41"
    
    # Test payload
    payload = {
        "idTool": 41,
        "need_aggregation": True,
        "page": 1,
        "pageSize": 24,
        "sector": None,
        "occupationModes": [],
        "location": [
            {"lon": 1.9954155920674, "lat": 49.095452162534826},
            {"lon": 2.7246331213642754, "lat": 48.33343022631068}
        ],
        "residence": None,
        "precision": 4,
        "equipment": [],
        "price": {"max": 10000000},
        "area": {"min": 0},
        "toolMechanism": "residual"
    }

    try:
        print("\n🔍 Testing CROUS API...")
        response = requests.post(API_URL, json=payload)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', {})
            items = results.get('items', [])
            total = results.get('total', {}).get('value', 0)
            
            print(f"✅ Found {total} total accommodations")
            print("\nFirst 3 results:")
            for item in items[:3]:
                print(f"\n🏠 {item.get('label', 'Unknown')}")
                print(f"📍 {item.get('residence', {}).get('label', 'Unknown')}")
                print(f"Available: {'✅' if item.get('available') else '❌'}")
        else:
            print(f"❌ API request failed")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")

def test_studefi():
    """Test Studefi website scraping and return results"""
    STUDEFI_URL = "https://www.studefi.fr/main.php"
    
    try:
        print("\n🔍 Testing Studefi website...")
        response = requests.get(STUDEFI_URL, impersonate="chrome")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            elements = soup.find_all("div", class_="col-sm-6 list-res-elem")
            
            available_count = 0
            print("\nAvailable residences:")
            
            for elem in elements:
                img_tag = elem.find("img", class_="dispoRes")
                if img_tag and "non_disponibles" not in img_tag.get("src", ""):
                    name_tag = elem.find("div", class_="list-res-link").find("a")
                    name = name_tag.get_text(strip=True)
                    link = name_tag.get("href", "")
                    available_count += 1
                    print(f"\n🏢 {name}")
                    print(f"🔗 https://www.studefi.fr/{link}")
                else:
                    name_tag = elem.find("div", class_="list-res-link").find("a")
                    name = name_tag.get_text(strip=True)
                    print(f"\n🏢 {name} (not available)")
            
            print(f"\nFound {available_count} available residences")
        else:
            print("❌ Website request failed")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    print(f"🤖 Starting tests at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # test_crous()
    print("\n" + "=" * 50)
    test_studefi()
    print("\n" + "=" * 50)
    print("✨ Tests completed")
