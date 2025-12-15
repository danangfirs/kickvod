# This script can unlike all instagram Activity
import asyncio
from camoufox.async_api import AsyncCamoufox
from browserforge.fingerprints import Screen
from screeninfo import get_monitors

async def login_instagram(username, password):
    async with AsyncCamoufox(humanize=2.0) as browser:
        try:
            # Get actual screen resolution
            monitor = get_monitors()[0]
            screen_width = monitor.width
            screen_height = monitor.height
            print(f"Detected screen resolution: {screen_width}x{screen_height}")
            
            # Launch browser and create page
            page = await browser.new_page()
            
            # Set viewport to match actual screen size
            await page.set_viewport_size({"width": screen_width, "height": screen_height})
            
            # Navigate to Instagram
            await page.goto("https://www.instagram.com")
            
            # Wait for the login form to be visible
            await page.wait_for_selector('input[name="username"]')
            
            # Fill in login credentials
            await page.fill('input[name="username"]', username)
            await page.fill('input[name="password"]', password)
            
            # Click login button
            await page.click('button[type="submit"]')
            
            # Wait for navigation after login
            await page.wait_for_load_state('networkidle')
            
            # Handle 'Save login info' dialog
            try:
                await page.get_by_role("button", name="Not now").click(timeout=5000)
                print("Clicked 'Not now' on save login info dialog.")
            except Exception:
                print("'Save login info' dialog did not appear or could not be clicked.")
            
            # Handle 'Turn on notifications' dialog
            try:
                await page.get_by_role("button", name="Not Now").click(timeout=5000)
                print("Clicked 'Not Now' on turn on notifications dialog.")
            except Exception:
                print("'Turn on notifications' dialog did not appear or could not be clicked.")
            
            # Navigate to Your Activity -> Likes to unlike posts
            print("Navigating to Your Activity > Likes...")
            # Using get_by_text is a reliable way to find these navigation elements
            await page.get_by_text("More").last.click()
            await page.wait_for_timeout(1000) # Wait for the menu to appear
            await page.get_by_text("Your activity").last.click()
            await page.wait_for_load_state("networkidle")
            
            # Loop to continuously scroll, select, and unlike until no more items are left.
            while True:
                print("\n--- Starting New Batch: Scrolling to find more items... ---")
                
                # Check if page is still valid
                if page.is_closed():
                    print("Page has been closed. Exiting...")
                    break
                
                # Scroll to the bottom of the page to load new items. This is key.
                await page.keyboard.press('End')
                # Wait for content to load after scrolling
                await page.wait_for_timeout(3000) 
                
                # Now, try to enter 'Select' mode.
                try:
                    await page.get_by_text("Select").last.click()
                    await page.wait_for_timeout(1000)
                except Exception:
                    print("Could not find 'Select' button after scrolling. Assuming process is finished.")
                    break

                checkboxes = page.locator('div[aria-label="Toggle checkbox"]')
                count = await checkboxes.count()

                if count == 0:
                    print("No items found after scrolling and entering select mode. Process finished.")
                    # Try to exit selection mode cleanly if possible.
                    if await page.get_by_text("Cancel").is_visible():
                        await page.get_by_text("Cancel").click()
                    break

                print(f"Found {count} items to unlike.")
                
                # Improved checkbox clicking with better error handling
                for i in range(count):
                    try:
                        # Check if page is still valid before each click
                        if page.is_closed():
                            print("Page closed during checkbox selection. Exiting...")
                            return
                        
                        checkbox = checkboxes.nth(i)
                        
                        # Wait for checkbox to be visible and stable
                        await checkbox.wait_for(state="visible", timeout=5000)
                        
                        # Try multiple click methods if one fails
                        try:
                            await checkbox.click(force=True)
                        except Exception as click_error:
                            print(f"Standard click failed for checkbox {i}, trying alternative method...")
                            try:
                                # Try using JavaScript click as fallback
                                await page.evaluate("(element) => element.click()", checkbox)
                            except Exception as js_error:
                                print(f"JavaScript click also failed for checkbox {i}: {js_error}")
                                continue
                        
                        await asyncio.sleep(0.5)  # Increased delay between clicks
                        
                    except Exception as e:
                        print(f"Error clicking checkbox {i}: {e}")
                        continue

                print("All items on this page selected. Clicking 'Unlike'.")
                try:
                    await page.get_by_text("Unlike").last.click()
                    await page.wait_for_timeout(1000)

                    print("Confirming unlike action in the dialog...")
                    await page.get_by_role("dialog").locator(':is(button, [role="button"]):has-text("Unlike")').last.click()
                    print(f"Successfully unliked {count} items. Preparing for next batch...")
                except Exception as unlike_error:
                    print(f"Error during unlike process: {unlike_error}")
                    # Try to cancel selection if unlike fails
                    try:
                        if await page.get_by_text("Cancel").is_visible():
                            await page.get_by_text("Cancel").click()
                    except:
                        pass
                    break
                
                # Wait for the page to settle before the next scroll.
                await page.wait_for_timeout(3000)

            print("Automation finished.")
            await asyncio.sleep(5)

        except Exception as e:
            print(f"An error occurred: {e}")

async def main():
    # Replace these with your Instagram credentials
    USERNAME = "dngfirm"
    PASSWORD = "dancogige26"
    
    await login_instagram(USERNAME, PASSWORD)

if __name__ == "__main__":
    asyncio.run(main())
    