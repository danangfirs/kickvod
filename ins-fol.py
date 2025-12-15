# Sebuah script untuk automasi unfollowers dari Instagram

import asyncio
import csv
import time
from camoufox.async_api import AsyncCamoufox
from browserforge.fingerprints import Screen

async def scrape_followers(username, password, target_profile):
    async with AsyncCamoufox(humanize=2.0, headless=False) as browser:
        try:
            # Login Instagram
            page = await browser.new_page()
            
            # Set ukuran window browser (sesuaikan dengan layar laptop Anda)
            await page.set_viewport_size({"width": 1366, "height": 768})
            # Atau untuk layar yang lebih besar: {"width": 1920, "height": 1080}
            
            # Opsional: Maximize window
            # await page.evaluate("window.moveTo(0, 0)")
            # await page.evaluate("window.resizeTo(screen.width, screen.height)")
            await page.goto("https://www.instagram.com")
            await page.wait_for_selector('input[name="username"]')
            await page.fill('input[name="username"]', username)
            await page.fill('input[name="password"]', password)
            await page.click('button[type="submit"]')
            
            # Tunggu login selesai dan pastikan sudah masuk
            print("Menunggu login selesai...")
            await page.wait_for_timeout(5000)
            
            # Cek apakah login berhasil (tunggu sampai ada elemen yang muncul setelah login)
            try:
                # Tunggu sampai ada elemen yang menandakan sudah login (seperti search box atau home icon)
                await page.wait_for_selector('input[placeholder="Search"]', timeout=10000)
                print("Login berhasil! Sekarang di halaman utama Instagram")
            except:
                # Jika tidak ada search box, coba cek elemen lain
                try:
                    await page.wait_for_selector('svg[aria-label="Home"]', timeout=5000)
                    print("Login berhasil! Sekarang di halaman utama Instagram")
                except:
                    print("Login mungkin gagal atau masih loading...")
                    await page.wait_for_timeout(3000)
            
            # Handle popup/dialog yang mungkin muncul setelah login
            try:
                # Cek dan tutup popup "Save Login Info" jika ada
                save_login_button = await page.query_selector('button:has-text("Not Now")')
                if save_login_button:
                    await save_login_button.click()
                    print("Popup 'Save Login Info' ditutup")
                    await page.wait_for_timeout(2000)
            except:
                pass
            
            try:
                # Cek dan tutup popup "Turn on Notifications" jika ada
                not_now_button = await page.query_selector('button:has-text("Not Now")')
                if not_now_button:
                    await not_now_button.click()
                    print("Popup 'Turn on Notifications' ditutup")
                    await page.wait_for_timeout(2000)
            except:
                pass
            
            print("Siap untuk navigasi ke profile target...")
            
            # Navigasi ke profile target
            await page.goto(f"https://www.instagram.com/{target_profile}/")
            await page.wait_for_timeout(2000)
            
            # Klik tombol Followers
            followers_button = await page.wait_for_selector('a[href*="/followers/"]')
            await followers_button.click()
            await page.wait_for_timeout(2000)
            
            # Scrape followers
            followers_data = []
            last_height = 0
            
            while True:
                # Ambil semua follower yang terlihat
                follower_elements = await page.query_selector_all('a[role="link"]')
                
                for element in follower_elements:
                    try:
                        href = await element.get_attribute('href')
                        if href and href.startswith('/') and not href.startswith('/p/') and not href.startswith('/reel/'):
                            username_follower = href.strip('/')
                            if username_follower and username_follower not in [f['username'] for f in followers_data]:
                                followers_data.append({
                                    'username': username_follower,
                                    'profile_url': f"https://www.instagram.com{href}"
                                })
                                print(f"Found follower: {username_follower}")
                    except Exception as e:
                        continue
                
                # Scroll ke bawah untuk load lebih banyak
                current_height = await page.evaluate('document.body.scrollHeight')
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await page.wait_for_timeout(2000)
                
                new_height = await page.evaluate('document.body.scrollHeight')
                if new_height == last_height:
                    break
                last_height = new_height
                
                # Batasi jumlah follower yang di-scrape (opsional)
                if len(followers_data) >= 1000:
                    break
            
            return followers_data
            
        except Exception as e:
            print(f"Error during scraping: {e}")
            raise

def save_to_csv(followers_data, filename):
    """Simpan data followers ke file CSV"""
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['username', 'profile_url']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for follower in followers_data:
            writer.writerow(follower)
    
    print(f"Data berhasil disimpan ke {filename}")

async def main():
    # Ganti dengan username dan password Instagram Anda
    username = "dngfirm"
    password = "dancogige26"
    target_profile = "lioness_real"  # Profile yang mau di-scrape followers-nya
    
    try:
        print(f"Mulai scraping followers dari {target_profile}...")
        followers_data = await scrape_followers(username, password, target_profile)
        
        print(f"Berhasil scrape {len(followers_data)} followers")
        
        # Simpan ke CSV
        filename = f"{target_profile}_followers.csv"
        save_to_csv(followers_data, filename)
        
        print("Scraping selesai!")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
    